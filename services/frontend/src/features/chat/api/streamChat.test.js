import { vi } from 'vitest';
import { streamChat, AuthError, StreamError } from './streamChat';

const mockFetchEventSource = vi.fn();
vi.mock('@microsoft/fetch-event-source', () => ({
  fetchEventSource: (...args) => mockFetchEventSource(...args),
}));

vi.mock('../../../utils/handleUnauthorized', () => ({
  handleUnauthorized: vi.fn(),
}));

import { handleUnauthorized } from '../../../utils/handleUnauthorized';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('access_token', 'test-jwt-token');
  localStorage.setItem('account_id', '42');
  mockFetchEventSource.mockResolvedValue(undefined);
});

afterEach(() => {
  localStorage.clear();
});

function lastCallArgs() {
  expect(mockFetchEventSource).toHaveBeenCalledTimes(1);
  return mockFetchEventSource.mock.calls[0];
}

describe('streamChat', () => {
  it('POSTs to AI_SERVICE_URL/chat/stream with correct body', async () => {
    await streamChat({ question: 'Hvad er min største udgift?', onEvent: vi.fn() });
    const [url, opts] = lastCallArgs();
    expect(url).toMatch(/\/chat\/stream$/);
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ question: 'Hvad er min største udgift?' });
  });

  it('sends auth, account-id, and content-type headers', async () => {
    await streamChat({ question: 'test', onEvent: vi.fn() });
    const [, opts] = lastCallArgs();
    expect(opts.headers).toMatchObject({
      Authorization: 'Bearer test-jwt-token',
      'X-Account-ID': '42',
      'Content-Type': 'application/json',
    });
  });

  it('passes signal for cancellation', async () => {
    const controller = new AbortController();
    await streamChat({ question: 'test', onEvent: vi.fn(), signal: controller.signal });
    const [, opts] = lastCallArgs();
    expect(opts.signal).toBe(controller.signal);
  });

  it('sets openWhenHidden to true', async () => {
    await streamChat({ question: 'test', onEvent: vi.fn() });
    const [, opts] = lastCallArgs();
    expect(opts.openWhenHidden).toBe(true);
  });

  it('throws AuthError immediately if no access_token', async () => {
    localStorage.removeItem('access_token');
    await expect(streamChat({ question: 'test', onEvent: vi.fn() }))
      .rejects.toThrow(AuthError);
    expect(mockFetchEventSource).not.toHaveBeenCalled();
  });

  it('throws AuthError immediately if no account_id', async () => {
    localStorage.removeItem('account_id');
    await expect(streamChat({ question: 'test', onEvent: vi.fn() }))
      .rejects.toThrow(AuthError);
    expect(mockFetchEventSource).not.toHaveBeenCalled();
  });

  it('calls onEvent with parsed SSE events', async () => {
    mockFetchEventSource.mockImplementation(async (_url, opts) => {
      opts.onmessage({ event: 'intent_resolved', data: '{"intent":"largest_expense","period":"2026-04","slots":{}}' });
      opts.onmessage({ event: 'prose_chunk', data: '{"delta":"Din "}' });
      opts.onmessage({ event: 'done', data: '{"metadata":{"router_ms":100}}' });
    });

    const onEvent = vi.fn();
    await streamChat({ question: 'test', onEvent });

    expect(onEvent).toHaveBeenCalledTimes(3);
    expect(onEvent).toHaveBeenNthCalledWith(1, {
      type: 'intent_resolved',
      data: { intent: 'largest_expense', period: '2026-04', slots: {} },
    });
    expect(onEvent).toHaveBeenNthCalledWith(2, {
      type: 'prose_chunk',
      data: { delta: 'Din ' },
    });
    expect(onEvent).toHaveBeenNthCalledWith(3, {
      type: 'done',
      data: { metadata: { router_ms: 100 } },
    });
  });

  it('silently skips SSE events with empty data (sse-starlette ping workaround)', async () => {
    mockFetchEventSource.mockImplementation(async (_url, opts) => {
      opts.onmessage({ event: 'intent_resolved', data: '{"intent":"largest_expense","period":"2026-04","slots":{}}' });
      opts.onmessage({ event: '', data: '' });
      opts.onmessage({ event: 'done', data: '{"metadata":{}}' });
    });

    const onEvent = vi.fn();
    await streamChat({ question: 'test', onEvent });

    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent).toHaveBeenNthCalledWith(1, expect.objectContaining({ type: 'intent_resolved' }));
    expect(onEvent).toHaveBeenNthCalledWith(2, expect.objectContaining({ type: 'done' }));
  });

  describe('onopen error handling', () => {
    it('calls handleUnauthorized and throws AuthError on 401', async () => {
      const response = new Response('Unauthorized', { status: 401 });
      mockFetchEventSource.mockImplementation(async (_url, opts) => {
        await opts.onopen(response);
      });

      await expect(
        streamChat({ question: 'test', onEvent: vi.fn() }),
      ).rejects.toThrow(AuthError);
      expect(handleUnauthorized).toHaveBeenCalledTimes(1);
    });

    it('throws StreamError with status and body on non-401 error', async () => {
      const response = new Response('{"detail":"Rate limited"}', {
        status: 429,
        headers: { 'Content-Type': 'application/json' },
      });
      mockFetchEventSource.mockImplementation(async (_url, opts) => {
        await opts.onopen(response);
      });

      const promise = streamChat({ question: 'test', onEvent: vi.fn() });
      await expect(promise).rejects.toThrow(StreamError);
      await expect(promise).rejects.toMatchObject({ status: 429, body: '{"detail":"Rate limited"}' });
    });

    it('does not throw on successful open', async () => {
      const response = new Response('', { status: 200 });
      mockFetchEventSource.mockImplementation(async (_url, opts) => {
        await opts.onopen(response);
      });

      await expect(
        streamChat({ question: 'test', onEvent: vi.fn() }),
      ).resolves.toBeUndefined();
    });
  });

  describe('onerror', () => {
    it('rethrows to disable fetchEventSource auto-retry', async () => {
      let capturedOnError;
      mockFetchEventSource.mockImplementation((_url, opts) => {
        capturedOnError = opts.onerror;
        return Promise.resolve();
      });

      await streamChat({ question: 'test', onEvent: vi.fn() });

      const networkError = new Error('fetch failed');
      expect(() => capturedOnError(networkError)).toThrow('fetch failed');
    });
  });

  describe('onclose', () => {
    it('throws StreamError if stream closes without done event', async () => {
      mockFetchEventSource.mockImplementation(async (_url, opts) => {
        opts.onmessage({ event: 'prose_chunk', data: '{"delta":"halvvejs"}' });
        opts.onclose();
      });
      await expect(streamChat({ question: 'test', onEvent: vi.fn() }))
        .rejects.toThrow(StreamError);
    });

    it('resolves normally if done event received before close', async () => {
      mockFetchEventSource.mockImplementation(async (_url, opts) => {
        opts.onmessage({ event: 'done', data: '{"metadata":{}}' });
        opts.onclose();
      });
      await expect(streamChat({ question: 'test', onEvent: vi.fn() }))
        .resolves.toBeUndefined();
    });
  });
});
