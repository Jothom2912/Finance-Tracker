import { vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { createQueryClientWrapper } from '../../../test-utils/renderWithQueryClient';

const mockStreamChat = vi.fn();
vi.mock('../api/streamChat', () => ({
  streamChat: (...args) => mockStreamChat(...args),
  AuthError: class AuthError extends Error {
    constructor(msg = 'auth') { super(msg); this.name = 'AuthError'; }
  },
  StreamError: class StreamError extends Error {
    constructor({ status, body, code, message }) {
      super(message ?? `Stream failed: ${code ?? status}`);
      this.name = 'StreamError';
      this.status = status;
      this.body = body;
      this.code = code;
    }
  },
}));

import { AuthError, StreamError } from '../api/streamChat';
import { useChatStream } from './useChatStream';

function renderChatHook() {
  const { wrapper } = createQueryClientWrapper();
  return renderHook(() => useChatStream(), { wrapper });
}

function simulateFullStream(onEvent) {
  onEvent({ type: 'intent_resolved', data: { intent: 'largest_expense', period: '2026-04', slots: {} } });
  onEvent({ type: 'data_ready', data: { kind: 'single_value', payload: { value: 288 } } });
  onEvent({ type: 'prose_chunk', data: { delta: 'Din ' } });
  onEvent({ type: 'prose_chunk', data: { delta: 'største' } });
  onEvent({ type: 'done', data: { metadata: { router_ms: 100 } } });
}

beforeEach(() => {
  vi.clearAllMocks();
  mockStreamChat.mockResolvedValue(undefined);
});

describe('useChatStream', () => {
  it('starts in idle phase', () => {
    const { result } = renderChatHook();
    expect(result.current.state.phase).toBe('idle');
    expect(result.current.isStreaming).toBe(false);
  });

  it('transitions through full stream lifecycle', async () => {
    mockStreamChat.mockImplementation(async ({ onEvent }) => {
      simulateFullStream(onEvent);
    });

    const { result } = renderChatHook();

    await act(async () => {
      result.current.send('Hvad er min største udgift?');
    });

    expect(result.current.state.phase).toBe('done');
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.state.history).toHaveLength(2);
    expect(result.current.state.history[0].role).toBe('user');
    expect(result.current.state.history[0].content).toBe('Hvad er min største udgift?');
    expect(result.current.state.history[1].role).toBe('assistant');
    expect(result.current.state.history[1].content).toBe('Din største');
    expect(result.current.state.history[1].intent.name).toBe('largest_expense');
  });

  it('guards against double-send during active stream', async () => {
    let resolveStream;
    mockStreamChat.mockImplementation(() => new Promise((resolve) => {
      resolveStream = resolve;
    }));

    const { result } = renderChatHook();

    act(() => {
      result.current.send('Første');
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.isStreaming).toBe(true);

    act(() => {
      result.current.send('Anden');
    });

    expect(mockStreamChat).toHaveBeenCalledTimes(1);
    expect(result.current.state.history).toHaveLength(1);

    await act(async () => {
      resolveStream();
    });
  });

  // Note: TanStack Querys interne mutation.status-opdatering efter abort
  // rejection sker uden for vores act-boundary og producerer act-warnings
  // i stderr. Vores reducer-state er korrekt (verificeret via waitFor),
  // og warnings reflekterer biblioteks-intern timing, ikke en race i vores kode.
  // Reference: github.com/TanStack/query/issues/270
  it('cancel aborts signal and dispatches STREAM_CANCELLED', async () => {
    let capturedSignal;
    mockStreamChat.mockImplementation(async ({ signal, onEvent }) => {
      capturedSignal = signal;
      onEvent({ type: 'intent_resolved', data: { intent: 'test', period: '2026-04', slots: {} } });
      onEvent({ type: 'prose_chunk', data: { delta: 'partial' } });
      await new Promise((_, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      });
    });

    const { result } = renderChatHook();

    act(() => {
      result.current.send('test');
    });
    await vi.waitFor(() => expect(result.current.state.phase).toBe('streaming'));

    act(() => {
      result.current.cancel();
    });
    await vi.waitFor(() => {
      expect(result.current.state.phase).toBe('idle');
    });

    expect(capturedSignal.aborted).toBe(true);
    expect(result.current.isStreaming).toBe(false);

    const partial = result.current.state.history.find((m) => m.cancelled);
    expect(partial).toBeDefined();
    expect(partial.content).toBe('partial');
  });

  // Note: Same TanStack Query act-warning caveat as cancel test above.
  it('AbortError from cancel does not transition to error phase', async () => {
    mockStreamChat.mockImplementation(async ({ signal, onEvent }) => {
      onEvent({ type: 'intent_resolved', data: { intent: 'test', period: '2026-04', slots: {} } });
      onEvent({ type: 'prose_chunk', data: { delta: 'x' } });
      await new Promise((_, reject) => {
        signal.addEventListener('abort', () =>
          reject(new DOMException('Aborted', 'AbortError')),
        );
      });
    });

    const { result } = renderChatHook();

    act(() => {
      result.current.send('test');
    });
    await vi.waitFor(() => expect(result.current.state.phase).toBe('streaming'));

    act(() => {
      result.current.cancel();
    });
    await vi.waitFor(() => {
      expect(result.current.state.phase).toBe('idle');
      expect(result.current.state.error).toBeNull();
    });
  });

  it('cancel is no-op when not streaming', () => {
    const { result } = renderChatHook();

    act(() => {
      result.current.cancel();
    });

    expect(result.current.state.phase).toBe('idle');
    expect(result.current.state.history).toHaveLength(0);
  });

  it('swallows AuthError without dispatching STREAM_ERROR', async () => {
    mockStreamChat.mockRejectedValue(new AuthError());

    const { result } = renderChatHook();

    await act(async () => {
      result.current.send('test');
    });

    expect(result.current.state.phase).not.toBe('error');
  });

  it('maps StreamError to STREAM_ERROR with code and message', async () => {
    mockStreamChat.mockRejectedValue(new StreamError({
      status: 503,
      body: 'unavailable',
      code: 'service_unavailable',
      message: 'Ollama er nede',
    }));

    const { result } = renderChatHook();

    await act(async () => {
      result.current.send('test');
    });

    expect(result.current.state.phase).toBe('error');
    expect(result.current.state.error).toEqual({
      code: 'service_unavailable',
      message: 'Ollama er nede',
    });
  });

  it('maps StreamError without code to http_<status>', async () => {
    mockStreamChat.mockRejectedValue(new StreamError({
      status: 429,
      body: 'rate limited',
      message: 'Too many requests',
    }));

    const { result } = renderChatHook();

    await act(async () => {
      result.current.send('test');
    });

    expect(result.current.state.phase).toBe('error');
    expect(result.current.state.error.code).toBe('http_429');
  });

  it('maps generic errors to network_error code', async () => {
    mockStreamChat.mockRejectedValue(new TypeError('Failed to fetch'));

    const { result } = renderChatHook();

    await act(async () => {
      result.current.send('test');
    });

    expect(result.current.state.phase).toBe('error');
    expect(result.current.state.error).toEqual({
      code: 'network_error',
      message: 'Failed to fetch',
    });
  });

  it('ignores unknown SSE event types without crashing', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    mockStreamChat.mockImplementation(async ({ onEvent }) => {
      onEvent({ type: 'heartbeat', data: {} });
      onEvent({ type: 'intent_resolved', data: { intent: 'test', period: '2026-04', slots: {} } });
      onEvent({ type: 'prose_chunk', data: { delta: 'svar' } });
      onEvent({ type: 'done', data: { metadata: {} } });
    });

    const { result } = renderChatHook();

    await act(async () => {
      result.current.send('test');
    });

    expect(result.current.state.phase).toBe('done');
    expect(warnSpy).toHaveBeenCalledWith('Unknown SSE event type:', 'heartbeat');
    warnSpy.mockRestore();
  });

  it('allows new send after done phase', async () => {
    mockStreamChat.mockImplementation(async ({ onEvent }) => {
      simulateFullStream(onEvent);
    });

    const { result } = renderChatHook();

    await act(async () => {
      result.current.send('Første spørgsmål');
    });
    expect(result.current.state.phase).toBe('done');

    await act(async () => {
      result.current.send('Andet spørgsmål');
    });
    expect(result.current.state.phase).toBe('done');
    expect(result.current.state.history).toHaveLength(4);
  });

  it('allows new send after error phase', async () => {
    mockStreamChat
      .mockRejectedValueOnce(new StreamError({ status: 500, message: 'fejl' }))
      .mockImplementation(async ({ onEvent }) => {
        simulateFullStream(onEvent);
      });

    const { result } = renderChatHook();

    await act(async () => {
      result.current.send('fejler');
    });
    expect(result.current.state.phase).toBe('error');

    await act(async () => {
      result.current.send('virker');
    });
    expect(result.current.state.phase).toBe('done');
  });
});
