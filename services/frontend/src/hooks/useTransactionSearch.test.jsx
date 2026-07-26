import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useTransactionSearch, transactionSearchQueryKey } from './useTransactionSearch';
import { createQueryClientWrapper } from '../test-utils/renderWithQueryClient';
import { PAGE_SIZE } from '../lib/pagination';

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

  it('includes accountId and page in the query key', () => {
    expect(transactionSearchQueryKey('account-1', 'netto', {}, 2)).toEqual([
      'transactionSearch',
      { accountId: 'account-1', query: 'netto', filters: {}, page: 2 },
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

  it('sends PAGE_SIZE as limit and offset 0 on page one', async () => {
    gqlRequest.mockResolvedValue(mockResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useTransactionSearch('netto'), { wrapper });

    await waitFor(() => expect(result.current.totalCount).toBe(17));

    expect(gqlRequest.mock.calls[0][1]).toMatchObject({
      limit: PAGE_SIZE,
      offset: 0,
    });
  });

  // offset er Int! i skemaet: den skal altid sendes, også som 0. Derfor
  // toMatchObject ovenfor OG en eksplicit kontrol af at nøglen findes.
  it('always sends an offset value, never null or undefined', async () => {
    gqlRequest.mockResolvedValue(mockResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useTransactionSearch('netto'), { wrapper });

    await waitFor(() => expect(result.current.totalCount).toBe(17));

    const vars = gqlRequest.mock.calls[0][1];
    expect(Object.keys(vars)).toContain('offset');
    expect(vars.offset).toBe(0);
  });

  // Det eneste sted variablen kan gå galt uden at en mocket test mærker det:
  // sender vi offset uden at ERKLÆRE den, afviser gateway'en dokumentet ved
  // validering — hver søgning på hver side fejler hårdt, uden delvis
  // degradering. Dokumentet er gqlRequests første argument, så det kan pinnes
  // her uden at eksportere SEARCH_QUERY.
  it('declares $offset: Int! in the document and passes it to the field', async () => {
    gqlRequest.mockResolvedValue(mockResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useTransactionSearch('netto'), { wrapper });

    await waitFor(() => expect(result.current.totalCount).toBe(17));

    const document = gqlRequest.mock.calls[0][0];
    expect(document).toContain('$offset: Int!');
    expect(document).toContain('offset: $offset');
  });

  it('translates page into offset and refetches (page is in the key)', async () => {
    gqlRequest.mockResolvedValue(mockResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result, rerender } = renderHook(({ page }) => useTransactionSearch('netto', {}, page), {
      wrapper,
      initialProps: { page: 1 },
    });

    await waitFor(() => expect(result.current.totalCount).toBe(17));

    rerender({ page: 3 });

    await waitFor(() => expect(gqlRequest).toHaveBeenCalledTimes(2));
    expect(gqlRequest.mock.calls[1][1]).toMatchObject({
      limit: PAGE_SIZE,
      offset: 2 * PAGE_SIZE,
    });
  });

  // Den rapporterede fejl: filterpanelet stod synligt aktivt og blev ignoreret.
  it('forwards the active filters, with categoryId as a number', async () => {
    gqlRequest.mockResolvedValue(mockResponse);

    const filters = { startDate: '2026-06-01', endDate: '2026-06-30', categoryId: '10' };
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useTransactionSearch('netto', filters), { wrapper });

    await waitFor(() => expect(result.current.totalCount).toBe(17));

    expect(gqlRequest.mock.calls[0][1]).toMatchObject({
      startDate: '2026-06-01',
      endDate: '2026-06-30',
      categoryId: 10,
    });
  });

  it('sends null — not empty strings — for absent filters', async () => {
    gqlRequest.mockResolvedValue(mockResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(
      () => useTransactionSearch('netto', { startDate: '', endDate: '', categoryId: '' }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.totalCount).toBe(17));

    expect(gqlRequest.mock.calls[0][1]).toMatchObject({
      startDate: null,
      endDate: null,
      categoryId: null,
    });
  });

  it('reports totalCount as null before the server has answered', () => {
    gqlRequest.mockReturnValue(new Promise(() => {}));

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useTransactionSearch('netto'), { wrapper });

    expect(result.current.totalCount).toBeNull();
    expect(result.current.isPaging).toBe(false);
  });

  it('flags isPaging while the previous page is still on screen', async () => {
    gqlRequest.mockResolvedValue(mockResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result, rerender } = renderHook(({ page }) => useTransactionSearch('netto', {}, page), {
      wrapper,
      initialProps: { page: 1 },
    });

    await waitFor(() => expect(result.current.totalCount).toBe(17));
    expect(result.current.isPaging).toBe(false);

    // Side 2 hænger: de gamle rækker skal stå tilbage, markeret som forældede.
    let resolvePage2;
    gqlRequest.mockReturnValue(new Promise((res) => { resolvePage2 = res; }));
    rerender({ page: 2 });

    await waitFor(() => expect(result.current.isPaging).toBe(true));
    expect(result.current.results).toHaveLength(1);
    expect(result.current.loading).toBe(false);

    resolvePage2({ searchTransactions: { totalCount: 17, items: [] } });
    await waitFor(() => expect(result.current.isPaging).toBe(false));
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
