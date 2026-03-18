import { vi, describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useCategories } from './useCategories';
import { fetchCategories } from '../api/categories';

vi.mock('../api/categories');

beforeEach(() => vi.clearAllMocks());

describe('useCategories', () => {
  it('fetches categories on mount', async () => {
    const data = [{ id: 1, name: 'Food' }, { id: 2, name: 'Transport' }];
    fetchCategories.mockResolvedValue(data);

    const { result } = renderHook(() => useCategories());

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.categories).toEqual(data);
    expect(result.current.error).toBeNull();
    expect(fetchCategories).toHaveBeenCalledTimes(1);
  });

  it('sets error on fetch failure', async () => {
    fetchCategories.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useCategories());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.categories).toEqual([]);
    expect(result.current.error).toBe('Network error');
  });

  it('uses fallback error message when error has no message', async () => {
    fetchCategories.mockRejectedValue({});

    const { result } = renderHook(() => useCategories());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Kunne ikke hente kategorier.');
  });

  it('re-fetches when refresh is called', async () => {
    const initial = [{ id: 1, name: 'Food' }];
    const refreshed = [{ id: 1, name: 'Food' }, { id: 3, name: 'Rent' }];

    fetchCategories.mockResolvedValueOnce(initial).mockResolvedValueOnce(refreshed);

    const { result } = renderHook(() => useCategories());

    await waitFor(() => {
      expect(result.current.categories).toEqual(initial);
    });

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.categories).toEqual(refreshed);
    expect(fetchCategories).toHaveBeenCalledTimes(2);
  });
});
