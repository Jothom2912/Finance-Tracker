import { vi, describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useTransactions } from './useTransactions';
import * as transactionsApi from '../api/transactions';
import { createQueryClientWrapper } from '../test-utils/renderWithQueryClient';

vi.mock('../api/transactions');

beforeEach(() => vi.clearAllMocks());

const filters = { startDate: '2025-01-01', endDate: '2025-01-31' };

describe('useTransactions', () => {
  describe('query', () => {
    it('fetches transactions on mount with given filters', async () => {
      const data = [{ id: 1, amount: 100 }, { id: 2, amount: 200 }];
      transactionsApi.fetchTransactions.mockResolvedValue(data);

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });

      expect(result.current.loading).toBe(true);
      expect(result.current.transactions).toEqual([]);

      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(result.current.transactions).toEqual(data);
      expect(result.current.error).toBeNull();
      expect(transactionsApi.fetchTransactions).toHaveBeenCalledWith(filters);
    });

    it('refetches automatically when filters change (queryKey change)', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue([]);

      const { wrapper } = createQueryClientWrapper();
      const { result, rerender } = renderHook(
        ({ f }) => useTransactions(f),
        { wrapper, initialProps: { f: filters } },
      );

      await waitFor(() => expect(result.current.loading).toBe(false));
      expect(transactionsApi.fetchTransactions).toHaveBeenCalledTimes(1);

      const newFilters = { startDate: '2025-02-01', endDate: '2025-02-28' };
      rerender({ f: newFilters });

      await waitFor(() =>
        expect(transactionsApi.fetchTransactions).toHaveBeenCalledTimes(2),
      );
      expect(transactionsApi.fetchTransactions).toHaveBeenLastCalledWith(newFilters);
    });

    it('exposes error message string on fetch failure', async () => {
      transactionsApi.fetchTransactions.mockRejectedValue(new Error('Network error'));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });

      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(result.current.transactions).toEqual([]);
      expect(result.current.error).toBe('Network error');
    });

    it('uses fallback error message when error has no message', async () => {
      transactionsApi.fetchTransactions.mockRejectedValue({});

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });

      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(result.current.error).toBe('Kunne ikke hente transaktioner.');
    });
  });

  describe('remove', () => {
    it('delegates to API and invalidates transactions + dashboard caches', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue([]);
      transactionsApi.deleteTransaction.mockResolvedValue(undefined);

      const { wrapper, client } = createQueryClientWrapper();
      const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

      const { result } = renderHook(() => useTransactions(filters), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));
      invalidateSpy.mockClear();

      await act(async () => {
        await result.current.remove(1);
      });

      expect(transactionsApi.deleteTransaction.mock.calls[0][0]).toBe(1);
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['transactions'] });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['dashboard'] });
    });

    it('rejects with the underlying error when API fails', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue([]);
      transactionsApi.deleteTransaction.mockRejectedValue(new Error('Delete failed'));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      await expect(
        act(async () => {
          await result.current.remove(1);
        }),
      ).rejects.toThrow('Delete failed');
    });
  });

  describe('uploadCsv', () => {
    it('delegates to API, returns result, and invalidates caches', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue([]);
      const uploadResult = { imported_count: 5, message: 'OK' };
      transactionsApi.uploadTransactionsCsv.mockResolvedValue(uploadResult);
      const file = new File(['csv,data'], 'test.csv');

      const { wrapper, client } = createQueryClientWrapper();
      const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

      const { result } = renderHook(() => useTransactions(filters), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));
      invalidateSpy.mockClear();

      let returnValue;
      await act(async () => {
        returnValue = await result.current.uploadCsv(file);
      });

      expect(transactionsApi.uploadTransactionsCsv.mock.calls[0][0]).toBe(file);
      expect(returnValue).toEqual(uploadResult);
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['transactions'] });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['dashboard'] });
    });
  });
});
