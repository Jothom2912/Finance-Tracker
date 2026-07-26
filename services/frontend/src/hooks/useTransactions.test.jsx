import { vi, describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useTransactions, transactionsQueryKey } from './useTransactions';
import * as transactionsApi from '../api/transactions';
import { PAGE_SIZE } from '../lib/pagination';
import { createQueryClientWrapper } from '../test-utils/renderWithQueryClient';

vi.mock('../api/transactions');

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

const filters = { startDate: '2025-01-01', endDate: '2025-01-31' };

/** Svaret fra fetchTransactions efter P1-14 step 6: {items, totalCount}. */
function page(items, totalCount = items.length) {
  return { items, totalCount };
}

describe('useTransactions', () => {
  describe('query', () => {
    it('fetches transactions on mount with given filters', async () => {
      const items = [{ id: 1, amount: 100 }, { id: 2, amount: 200 }];
      transactionsApi.fetchTransactions.mockResolvedValue(page(items));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });

      expect(result.current.loading).toBe(true);
      expect(result.current.transactions).toEqual([]);

      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(result.current.transactions).toEqual(items);
      expect(result.current.error).toBeNull();
      expect(transactionsApi.fetchTransactions).toHaveBeenCalledWith({
        ...filters,
        skip: 0,
        limit: PAGE_SIZE,
      });
    });

    it('refetches automatically when filters change (queryKey change)', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([]));

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
      expect(transactionsApi.fetchTransactions).toHaveBeenLastCalledWith({
        ...newFilters,
        skip: 0,
        limit: PAGE_SIZE,
      });
    });

    it('refetches instead of reusing cache when account changes', async () => {
      localStorage.setItem('account_id', 'account-1');
      transactionsApi.fetchTransactions.mockResolvedValueOnce(page([{ id: 1, amount: 100 }]));

      const { wrapper } = createQueryClientWrapper();
      const { result, rerender } = renderHook(() => useTransactions(filters), { wrapper });

      await waitFor(() => {
        expect(result.current.transactions).toEqual([{ id: 1, amount: 100 }]);
      });

      localStorage.setItem('account_id', 'account-2');
      transactionsApi.fetchTransactions.mockResolvedValueOnce(page([{ id: 2, amount: 200 }]));
      rerender();

      await waitFor(() => {
        expect(result.current.transactions).toEqual([{ id: 2, amount: 200 }]);
      });
      expect(transactionsApi.fetchTransactions).toHaveBeenCalledTimes(2);
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

  describe('paginering', () => {
    it('defaulter til side 1, altså skip=0', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([]));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(transactionsApi.fetchTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ skip: 0, limit: PAGE_SIZE }),
      );
    });

    it('oversætter sidetal til skip = (page - 1) * PAGE_SIZE', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([]));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters, 3), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      expect(transactionsApi.fetchTransactions).toHaveBeenCalledWith(
        expect.objectContaining({ skip: 2 * PAGE_SIZE, limit: PAGE_SIZE }),
      );
    });

    it('henter igen når sidetallet ændrer sig — sidetallet er i nøglen', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([{ id: 1 }]));

      const { wrapper } = createQueryClientWrapper();
      const { result, rerender } = renderHook(
        ({ p }) => useTransactions(filters, p),
        { wrapper, initialProps: { p: 1 } },
      );

      await waitFor(() => expect(result.current.loading).toBe(false));
      expect(transactionsApi.fetchTransactions).toHaveBeenCalledTimes(1);

      rerender({ p: 2 });

      await waitFor(() =>
        expect(transactionsApi.fetchTransactions).toHaveBeenCalledTimes(2),
      );
      expect(transactionsApi.fetchTransactions).toHaveBeenLastCalledWith(
        expect.objectContaining({ skip: PAGE_SIZE }),
      );
    });

    it('beholder forrige sides rækker mens den nye henter, og markerer isPaging', async () => {
      const first = [{ id: 1, amount: 100 }];
      const second = [{ id: 2, amount: 200 }];
      transactionsApi.fetchTransactions.mockResolvedValueOnce(page(first, 93));

      const { wrapper } = createQueryClientWrapper();
      const { result, rerender } = renderHook(
        ({ p }) => useTransactions(filters, p),
        { wrapper, initialProps: { p: 1 } },
      );

      await waitFor(() => expect(result.current.transactions).toEqual(first));
      expect(result.current.isPaging).toBe(false);

      let resolveSecond;
      transactionsApi.fetchTransactions.mockReturnValueOnce(
        new Promise((resolve) => {
          resolveSecond = resolve;
        }),
      );
      rerender({ p: 2 });

      // Side 2 er undervejs: side 1's rækker står stadig, loading er falsk.
      await waitFor(() => expect(result.current.isPaging).toBe(true));
      expect(result.current.transactions).toEqual(first);
      expect(result.current.loading).toBe(false);

      await act(async () => {
        resolveSecond(page(second, 93));
      });

      await waitFor(() => expect(result.current.transactions).toEqual(second));
      expect(result.current.isPaging).toBe(false);
    });

    // Dette er forskellen mellem isPlaceholderData og isFetching. Begge er sande
    // ved et sideskift; kun isFetching er sand her, hvor rækkerne på skærmen
    // hører til den nøgle vi henter — et dæmp ville være støj.
    it('markerer ikke isPaging under baggrunds-refetch efter en mutation', async () => {
      transactionsApi.fetchTransactions.mockResolvedValueOnce(page([{ id: 1 }], 1));
      transactionsApi.deleteTransaction.mockResolvedValue(undefined);

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });
      await waitFor(() => expect(result.current.transactions).toHaveLength(1));

      let resolveRefetch;
      transactionsApi.fetchTransactions.mockReturnValueOnce(
        new Promise((resolve) => {
          resolveRefetch = resolve;
        }),
      );

      await act(async () => {
        await result.current.remove(1);
      });

      await waitFor(() =>
        expect(transactionsApi.fetchTransactions).toHaveBeenCalledTimes(2),
      );
      expect(result.current.isPaging).toBe(false);

      await act(async () => {
        resolveRefetch(page([], 0));
      });
    });
  });

  describe('totalCount', () => {
    it('videregiver serverens total', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([{ id: 1 }], 93));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });

      await waitFor(() => expect(result.current.totalCount).toBe(93));
    });

    it('er null før serveren har svaret — ikke 0', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([]));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });

      expect(result.current.loading).toBe(true);
      expect(result.current.totalCount).toBeNull();
    });

    it('er null, ikke 0, når API-laget ikke kender totalen', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue({ items: [{ id: 1 }], totalCount: null });

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });

      await waitFor(() => expect(result.current.transactions).toHaveLength(1));
      expect(result.current.totalCount).toBeNull();
    });

    it('er 0 når perioden faktisk er tom', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([], 0));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });

      await waitFor(() => expect(result.current.loading).toBe(false));
      expect(result.current.totalCount).toBe(0);
    });
  });

  describe('transactionsQueryKey', () => {
    it('har sidetallet med, så to sider ikke deler cache-indgang', () => {
      expect(transactionsQueryKey('1', filters, 1)).not.toEqual(
        transactionsQueryKey('1', filters, 2),
      );
    });

    it('starter med "transactions", så prefix-invalidering rammer alle sider', () => {
      expect(transactionsQueryKey('1', filters, 4)[0]).toBe('transactions');
    });
  });

  describe('enabled', () => {
    it('henter ikke når enabled er false', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([{ id: 1 }]));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(
        () => useTransactions(filters, 1, { enabled: false }),
        { wrapper },
      );

      // Ingen fetch, og ingen falsk "indlæser"-tilstand som siden ville vise.
      expect(transactionsApi.fetchTransactions).not.toHaveBeenCalled();
      expect(result.current.loading).toBe(false);
      expect(result.current.transactions).toEqual([]);
      expect(result.current.totalCount).toBeNull();
    });

    it('henter ikke ved sideskift mens den er slået fra — det var hele pointen', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([{ id: 1 }]));

      const { wrapper } = createQueryClientWrapper();
      const { rerender } = renderHook(
        ({ p }) => useTransactions(filters, p, { enabled: false }),
        { wrapper, initialProps: { p: 1 } },
      );

      rerender({ p: 2 });
      rerender({ p: 3 });

      expect(transactionsApi.fetchTransactions).not.toHaveBeenCalled();
    });

    it('henter når den slås til igen (søgning forlades)', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([{ id: 1 }]));

      const { wrapper } = createQueryClientWrapper();
      const { result, rerender } = renderHook(
        ({ e }) => useTransactions(filters, 1, { enabled: e }),
        { wrapper, initialProps: { e: false } },
      );

      expect(transactionsApi.fetchTransactions).not.toHaveBeenCalled();

      rerender({ e: true });

      await waitFor(() => expect(result.current.loading).toBe(false));
      expect(transactionsApi.fetchTransactions).toHaveBeenCalledTimes(1);
      expect(result.current.transactions).toEqual([{ id: 1 }]);
    });

    // Kun queryen pauses. Ville mutationerne også slå fra, kunne man ikke gemme
    // eller CSV-importere mens en søgning står aktiv.
    it('lader mutationer virke selv om queryen er slået fra', async () => {
      transactionsApi.deleteTransaction.mockResolvedValue(undefined);

      const { wrapper, client } = createQueryClientWrapper();
      const invalidateSpy = vi.spyOn(client, 'invalidateQueries');
      const { result } = renderHook(
        () => useTransactions(filters, 1, { enabled: false }),
        { wrapper },
      );

      await act(async () => {
        await result.current.remove(1);
      });

      expect(transactionsApi.deleteTransaction.mock.calls[0][0]).toBe(1);
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['transactions'] });
      expect(transactionsApi.fetchTransactions).not.toHaveBeenCalled();
    });

    it('henter som standard når options udelades', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([]));

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters, 1), { wrapper });

      await waitFor(() => expect(result.current.loading).toBe(false));
      expect(transactionsApi.fetchTransactions).toHaveBeenCalledTimes(1);
    });
  });

  describe('remove', () => {
    it('delegates to API and invalidates transactions + dashboard caches', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([]));
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
      transactionsApi.fetchTransactions.mockResolvedValue(page([]));
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
    it('delegates to API with file and bankFormat, returns result, and invalidates caches', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([]));
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
        returnValue = await result.current.uploadCsv({ file, bankFormat: 'nordea' });
      });

      expect(transactionsApi.uploadTransactionsCsv).toHaveBeenCalledWith({
        file,
        bankFormat: 'nordea',
      });
      expect(returnValue).toEqual(uploadResult);
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['transactions'] });
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['dashboard'] });
    });

    it('defaults bankFormat to internal when not specified', async () => {
      transactionsApi.fetchTransactions.mockResolvedValue(page([]));
      transactionsApi.uploadTransactionsCsv.mockResolvedValue({ imported_count: 1 });
      const file = new File(['csv,data'], 'test.csv');

      const { wrapper } = createQueryClientWrapper();
      const { result } = renderHook(() => useTransactions(filters), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      await act(async () => {
        await result.current.uploadCsv({ file, bankFormat: 'internal' });
      });

      expect(transactionsApi.uploadTransactionsCsv).toHaveBeenCalledWith({
        file,
        bankFormat: 'internal',
      });
    });
  });
});
