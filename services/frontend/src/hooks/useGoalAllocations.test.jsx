import { vi, describe, it, expect, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAllocationHistory, useUnallocatedSurplus } from './useGoalAllocations';
import * as goalsApi from '../api/goals';
import { createQueryClientWrapper } from '../test-utils/renderWithQueryClient';

vi.mock('../api/goals');

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('useAllocationHistory', () => {
  it('fetches history for the goal when enabled', async () => {
    goalsApi.fetchAllocationHistory.mockResolvedValue([
      { amount: 250, source_key: 'budget.month_closed:1:2026:6', applied_at: '2026-07-07T12:00:00Z' },
    ]);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useAllocationHistory(7), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(goalsApi.fetchAllocationHistory).toHaveBeenCalledWith(7);
    expect(result.current.history).toHaveLength(1);
    expect(result.current.history[0].amount).toBe(250);
  });

  it('does not fetch when disabled', async () => {
    const { wrapper } = createQueryClientWrapper();
    renderHook(() => useAllocationHistory(7, { enabled: false }), { wrapper });

    expect(goalsApi.fetchAllocationHistory).not.toHaveBeenCalled();
  });

  it('exposes error message on failure', async () => {
    goalsApi.fetchAllocationHistory.mockRejectedValue(new Error('boom'));

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useAllocationHistory(7), { wrapper });

    await waitFor(() => expect(result.current.error).toBe('boom'));
    expect(result.current.history).toEqual([]);
  });
});

describe('useUnallocatedSurplus', () => {
  it('exposes total and entries', async () => {
    goalsApi.fetchUnallocatedSurplus.mockResolvedValue({
      total: 150,
      entries: [{ amount: 150, reason: 'no_default_goal', observed_at: '2026-07-07T12:00:00Z' }],
    });

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useUnallocatedSurplus(), { wrapper });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.total).toBe(150);
    expect(result.current.entries).toHaveLength(1);
  });

  it('defaults to zero/empty before data arrives', () => {
    goalsApi.fetchUnallocatedSurplus.mockReturnValue(new Promise(() => {}));

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useUnallocatedSurplus(), { wrapper });

    expect(result.current.total).toBe(0);
    expect(result.current.entries).toEqual([]);
  });
});
