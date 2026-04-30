import { vi, describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useCategories } from './useCategories';
import { fetchCategories } from '../api/categories';
import { createQueryClientWrapper } from '../test-utils/renderWithQueryClient';

vi.mock('../api/categories');

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('useCategories', () => {
  it('fetches categories on mount', async () => {
    const data = [{ id: 1, name: 'Food' }, { id: 2, name: 'Transport' }];
    fetchCategories.mockResolvedValue(data);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useCategories(), { wrapper });

    expect(result.current.loading).toBe(true);
    expect(result.current.categories).toEqual([]);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.categories).toEqual(data);
    expect(result.current.error).toBeNull();
    expect(fetchCategories).toHaveBeenCalledTimes(1);
  });

  it('sets error on fetch failure', async () => {
    fetchCategories.mockRejectedValue(new Error('Network error'));

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useCategories(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.categories).toEqual([]);
    expect(result.current.error).toBe('Network error');
  });

  it('uses fallback error message when error has no message', async () => {
    fetchCategories.mockRejectedValue({});

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useCategories(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Kunne ikke hente kategorier.');
  });

  it('re-fetches when refresh is called', async () => {
    const initial = [{ id: 1, name: 'Food' }];
    const refreshed = [{ id: 1, name: 'Food' }, { id: 3, name: 'Rent' }];

    fetchCategories.mockResolvedValueOnce(initial).mockResolvedValueOnce(refreshed);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useCategories(), { wrapper });

    await waitFor(() => {
      expect(result.current.categories).toEqual(initial);
    });

    await act(async () => {
      result.current.refresh();
    });

    await waitFor(() => {
      expect(result.current.categories).toEqual(refreshed);
    });

    expect(fetchCategories).toHaveBeenCalledTimes(2);
  });

  it('refetches when account changes', async () => {
    localStorage.setItem('account_id', 'account-1');
    fetchCategories.mockResolvedValueOnce([{ id: 1, name: 'Food' }]);

    const { wrapper } = createQueryClientWrapper();
    const { result, rerender } = renderHook(() => useCategories(), { wrapper });

    await waitFor(() => {
      expect(result.current.categories).toEqual([{ id: 1, name: 'Food' }]);
    });

    localStorage.setItem('account_id', 'account-2');
    fetchCategories.mockResolvedValueOnce([{ id: 2, name: 'Transport' }]);
    rerender();

    await waitFor(() => {
      expect(result.current.categories).toEqual([{ id: 2, name: 'Transport' }]);
    });
    expect(fetchCategories).toHaveBeenCalledTimes(2);
  });

  it('invalidates categories cache on refresh', async () => {
    fetchCategories.mockResolvedValue([]);

    const { wrapper, client } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useCategories(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    invalidateSpy.mockClear();

    await act(async () => {
      result.current.refresh();
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['categories'] });
  });
});
