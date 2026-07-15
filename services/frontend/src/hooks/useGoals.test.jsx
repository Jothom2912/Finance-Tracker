import { vi, describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useGoals, mapGoalFromRest, goalsQueryKey } from './useGoals';
import * as goalsApi from '../api/goals';
import { createQueryClientWrapper } from '../test-utils/renderWithQueryClient';

vi.mock('../api/goals');

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

const restGoal = {
  idGoal: 7,
  name: 'Ferie',
  target_amount: 10000,
  current_amount: 2500,
  target_date: '2026-12-01',
  status: 'active',
  effective_status: 'active',
  progress_percent: 25,
};

const uiGoal = {
  id: 7,
  name: 'Ferie',
  targetAmount: 10000,
  currentAmount: 2500,
  targetDate: '2026-12-01',
  status: 'active',
  storedStatus: 'active',
  percentComplete: 25,
};

describe('mapGoalFromRest', () => {
  it('maps REST shape to the UI shape, keeping both effective and stored status', () => {
    expect(
      mapGoalFromRest({ ...restGoal, status: 'active', effective_status: 'completed' }),
    ).toEqual({ ...uiGoal, status: 'completed', storedStatus: 'active' });
  });
});

describe('useGoals', () => {
  describe('query', () => {
    it('fetches goals on mount and exposes the mapped UI shape', async () => {
      goalsApi.fetchGoals.mockResolvedValue([restGoal]);

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useGoals(), { wrapper });

      expect(result.current.loading).toBe(true);
      expect(result.current.goals).toEqual([]);

      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(result.current.goals).toEqual([uiGoal]);
      expect(result.current.error).toBeNull();
    });

    it('refetches instead of reusing cache when account changes', async () => {
      localStorage.setItem('account_id', 'account-1');
      goalsApi.fetchGoals.mockResolvedValueOnce([restGoal]);

      const { wrapper } = createQueryClientWrapper();
      const { result, rerender } = renderHook(() => useGoals(), { wrapper });

      await waitFor(() => expect(result.current.goals).toEqual([uiGoal]));

      localStorage.setItem('account_id', 'account-2');
      goalsApi.fetchGoals.mockResolvedValueOnce([]);
      rerender();

      await waitFor(() => expect(result.current.goals).toEqual([]));
      expect(goalsApi.fetchGoals).toHaveBeenCalledTimes(2);
    });

    it('exposes error message string on fetch failure', async () => {
      goalsApi.fetchGoals.mockRejectedValue(new Error('Network error'));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useGoals(), { wrapper });

      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(result.current.goals).toEqual([]);
      expect(result.current.error).toBe('Network error');
    });

    it('uses fallback error message when error has no message', async () => {
      goalsApi.fetchGoals.mockRejectedValue({});

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useGoals(), { wrapper });

      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(result.current.error).toBe('Kunne ikke hente mål.');
    });
  });

  describe('mutations', () => {
    it('create delegates to API and invalidates the goals cache', async () => {
      localStorage.setItem('account_id', 'account-1');
      goalsApi.fetchGoals.mockResolvedValue([]);
      goalsApi.createGoal.mockResolvedValue({ idGoal: 1 });

      const { wrapper, client } = createQueryClientWrapper();
      const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

      const { result } = renderHook(() => useGoals(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));
      invalidateSpy.mockClear();

      const goalData = { name: 'Bil', target_amount: 50000 };
      await act(async () => {
        await result.current.create(goalData);
      });

      expect(goalsApi.createGoal.mock.calls[0][0]).toEqual(goalData);
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['goals'] });
    });

    it('update delegates to API with id and data, and invalidates the goals cache', async () => {
      goalsApi.fetchGoals.mockResolvedValue([]);
      goalsApi.updateGoal.mockResolvedValue({});

      const { wrapper, client } = createQueryClientWrapper();
      const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

      const { result } = renderHook(() => useGoals(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));
      invalidateSpy.mockClear();

      const goalData = { name: 'Bil', target_amount: 60000 };
      await act(async () => {
        await result.current.update(7, goalData);
      });

      expect(goalsApi.updateGoal).toHaveBeenCalledWith(7, goalData);
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['goals'] });
    });

    it('remove delegates to API and invalidates the goals cache', async () => {
      goalsApi.fetchGoals.mockResolvedValue([]);
      goalsApi.deleteGoal.mockResolvedValue(undefined);

      const { wrapper, client } = createQueryClientWrapper();
      const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

      const { result } = renderHook(() => useGoals(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));
      invalidateSpy.mockClear();

      await act(async () => {
        await result.current.remove(7);
      });

      expect(goalsApi.deleteGoal.mock.calls[0][0]).toBe(7);
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['goals'] });
    });

    it('rejects with the underlying error when API fails', async () => {
      goalsApi.fetchGoals.mockResolvedValue([]);
      goalsApi.createGoal.mockRejectedValue(new Error('Create failed'));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useGoals(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      await expect(
        act(async () => {
          await result.current.create({ name: 'Bil' });
        }),
      ).rejects.toThrow('Create failed');
    });

    it('mutation invalidation refetches the query so consumers see fresh data', async () => {
      localStorage.setItem('account_id', 'account-1');
      goalsApi.fetchGoals
        .mockResolvedValueOnce([])
        .mockResolvedValueOnce([restGoal]);
      goalsApi.createGoal.mockResolvedValue({ idGoal: 7 });

      const { wrapper, client } = createQueryClientWrapper();
      const { result } = renderHook(() => useGoals(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));
      expect(result.current.goals).toEqual([]);

      await act(async () => {
        await result.current.create({ name: 'Ferie', target_amount: 10000 });
      });

      await waitFor(() => expect(result.current.goals).toEqual([uiGoal]));
      expect(
        client.getQueryData(goalsQueryKey('account-1')),
      ).toEqual([restGoal]);
    });
  });
});
