import { vi, describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTransactions } from './useTransactions';
import * as transactionsApi from '../api/transactions';

vi.mock('../api/transactions');

beforeEach(() => vi.clearAllMocks());

describe('useTransactions', () => {
  it('starts with empty state', () => {
    const { result } = renderHook(() => useTransactions());

    expect(result.current.transactions).toEqual([]);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  describe('fetch', () => {
    it('fetches transactions and updates state', async () => {
      const data = [{ id: 1, amount: 100 }, { id: 2, amount: 200 }];
      transactionsApi.fetchTransactions.mockResolvedValue(data);

      const { result } = renderHook(() => useTransactions());

      await act(async () => {
        await result.current.fetch({ startDate: '2025-01-01', endDate: '2025-01-31' });
      });

      expect(result.current.transactions).toEqual(data);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
      expect(transactionsApi.fetchTransactions).toHaveBeenCalledWith({
        startDate: '2025-01-01',
        endDate: '2025-01-31',
      });
    });

    it('sets error message on failure', async () => {
      transactionsApi.fetchTransactions.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useTransactions());

      await act(async () => {
        await result.current.fetch();
      });

      expect(result.current.transactions).toEqual([]);
      expect(result.current.error).toBe('Network error');
      expect(result.current.loading).toBe(false);
    });

    it('uses fallback error message when error has no message', async () => {
      transactionsApi.fetchTransactions.mockRejectedValue({});

      const { result } = renderHook(() => useTransactions());

      await act(async () => {
        await result.current.fetch();
      });

      expect(result.current.error).toBe('Kunne ikke hente transaktioner.');
    });
  });

  describe('create', () => {
    it('delegates to API and returns result', async () => {
      const created = { id: 3, amount: 300 };
      transactionsApi.createTransaction.mockResolvedValue(created);

      const { result } = renderHook(() => useTransactions());
      let returnValue;

      await act(async () => {
        returnValue = await result.current.create({ amount: 300 });
      });

      expect(transactionsApi.createTransaction).toHaveBeenCalledWith({ amount: 300 });
      expect(returnValue).toEqual(created);
    });
  });

  describe('update', () => {
    it('delegates to API and returns result', async () => {
      const updated = { id: 1, amount: 150 };
      transactionsApi.updateTransaction.mockResolvedValue(updated);

      const { result } = renderHook(() => useTransactions());
      let returnValue;

      await act(async () => {
        returnValue = await result.current.update(1, { amount: 150 });
      });

      expect(transactionsApi.updateTransaction).toHaveBeenCalledWith(1, { amount: 150 });
      expect(returnValue).toEqual(updated);
    });
  });

  describe('remove', () => {
    it('delegates to API', async () => {
      transactionsApi.deleteTransaction.mockResolvedValue(undefined);

      const { result } = renderHook(() => useTransactions());

      await act(async () => {
        await result.current.remove(1);
      });

      expect(transactionsApi.deleteTransaction).toHaveBeenCalledWith(1);
    });
  });

  describe('uploadCsv', () => {
    it('delegates to API and returns result', async () => {
      const uploadResult = { imported: 5 };
      transactionsApi.uploadTransactionsCsv.mockResolvedValue(uploadResult);
      const file = new File(['csv,data'], 'test.csv');

      const { result } = renderHook(() => useTransactions());
      let returnValue;

      await act(async () => {
        returnValue = await result.current.uploadCsv(file);
      });

      expect(transactionsApi.uploadTransactionsCsv).toHaveBeenCalledWith(file);
      expect(returnValue).toEqual(uploadResult);
    });
  });
});
