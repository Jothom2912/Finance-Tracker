import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useTransactionSearch, transactionSearchQueryKey } from './useTransactionSearch';
import { createQueryClientWrapper } from '../test-utils/renderWithQueryClient';

vi.mock('../api/graphqlClient', () => ({
  gqlRequest: vi.fn(),
}));

import { gqlRequest } from '../api/graphqlClient';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

const mockResponse = {
  searchTransactions: {
    totalCount: 17,
    items: [
      {
        id: 42,
        amount: 143.28,
        description: 'Dankort-nota Netto',
        date: '2026-06-13',
        type: 'expense',
        categoryId: 10,
        categoryName: 'Mad & drikke',
        subcategoryName: 'Dagligvarer',
        categorizationTier: 'rule',
      },
    ],
  },
};

describe('useTransactionSearch', () => {
  it('is disabled below two characters — no request fires', async () => {
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useTransactionSearch('n'), { wrapper });

    expect(result.current.isSearchActive).toBe(false);
    expect(result.current.loading).toBe(false);
    expect(gqlRequest).not.toHaveBeenCalled();
  });

  it('fetches and maps GraphQL camelCase to the REST row shape', async () => {
    gqlRequest.mockResolvedValue(mockResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useTransactionSearch('netto'), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.totalCount).toBe(17);
    expect(result.current.results[0]).toMatchObject({
      id: 42,
      category_name: 'Mad & drikke',
      subcategory_name: 'Dagligvarer',
      type: 'expense',
    });
  });

  it('includes accountId in the query key (implicit X-Account-ID input)', () => {
    expect(transactionSearchQueryKey('account-1', 'netto', {})).toEqual([
      'transactionSearch',
      { accountId: 'account-1', query: 'netto', filters: {} },
    ]);
  });

  it('refetches when account changes', async () => {
    localStorage.setItem('account_id', 'account-1');
    gqlRequest.mockResolvedValue(mockResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result, rerender } = renderHook(() => useTransactionSearch('netto'), { wrapper });

    await waitFor(() => {
      expect(result.current.totalCount).toBe(17);
    });

    localStorage.setItem('account_id', 'account-2');
    gqlRequest.mockResolvedValue({
      searchTransactions: { totalCount: 3, items: [] },
    });
    rerender();

    await waitFor(() => {
      expect(result.current.totalCount).toBe(3);
    });
    expect(gqlRequest).toHaveBeenCalledTimes(2);
  });

  it('surfaces errors as a message', async () => {
    gqlRequest.mockRejectedValue(new Error('Analytics-læsesiden er utilgængelig'));

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useTransactionSearch('netto'), { wrapper });

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
    expect(result.current.error).toContain('utilgængelig');
  });
});
