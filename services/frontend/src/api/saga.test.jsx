import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

vi.mock('../utils/handleUnauthorized', () => ({
  handleUnauthorized: vi.fn(),
}));

import {
  getSagaProgressLabel,
  buildBankSyncResultMessage,
  pollSagaUntilComplete,
} from './saga';

function mockFetchSequence(responses) {
  let call = 0;
  return vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
    const body = responses[Math.min(call, responses.length - 1)];
    call += 1;
    return Promise.resolve({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: () => Promise.resolve(body),
    });
  });
}

describe('getSagaProgressLabel', () => {
  it('returns starter label when saga is missing', () => {
    expect(getSagaProgressLabel(null)).toBe('Starter sync...');
  });

  it('maps active bank sync steps to Danish labels', () => {
    expect(getSagaProgressLabel({
      status: 'started',
      current_step_name: 'fetch_transactions',
    })).toBe('Henter transaktioner fra bank...');

    expect(getSagaProgressLabel({
      status: 'started',
      current_step_name: 'import_transactions',
    })).toBe('Importerer transaktioner...');
  });

  it('returns compensation and failure labels', () => {
    expect(getSagaProgressLabel({ status: 'pending' })).toBe('Starter sync...');
    expect(getSagaProgressLabel({ status: 'compensating' })).toBe(
      'Ruller import tilbage...',
    );
    expect(getSagaProgressLabel({
      status: 'failed',
      error_detail: 'Bank API nede',
    })).toBe('Bank API nede');
  });
});

describe('buildBankSyncResultMessage', () => {
  it('builds summary from saga context', () => {
    const result = buildBankSyncResultMessage({
      context: {
        new_imported: 5,
        duplicates_skipped: 2,
        total_fetched: 7,
      },
    });

    expect(result.message).toBe('5 nye, 2 duplikater');
    expect(result.detail).toBe('7 transaktioner hentet');
  });
});

describe('pollSagaUntilComplete', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('polls until saga reaches terminal status', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: () => Promise.resolve({ detail: 'Saga not found' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: () => Promise.resolve({
          status: 'started',
          current_step_name: 'fetch_transactions',
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: 'OK',
        json: () => Promise.resolve({ status: 'completed', context: { new_imported: 1 } }),
      });

    const progress = [];
    const promise = pollSagaUntilComplete('saga-1', {
      intervalMs: 1000,
      onProgress: (saga) => progress.push(saga.status),
    });

    await vi.advanceTimersByTimeAsync(2000);
    const saga = await promise;

    expect(saga.status).toBe('completed');
    expect(progress).toEqual(['pending', 'started', 'completed']);
    fetchMock.mockRestore();
  });
});
