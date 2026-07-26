import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('../utils/apiClient');

import apiClient from '../utils/apiClient';
import { fetchTransactions } from './transactions';
import { PAGE_SIZE } from '../lib/pagination';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

function okResponse(body) {
  return { ok: true, status: 200, json: () => Promise.resolve(body) };
}

function requestedUrl() {
  return apiClient.get.mock.calls[0][0];
}

function requestedParams() {
  return new URLSearchParams(requestedUrl().split('?')[1] ?? '');
}

const row = (id) => ({ id, amount: 100, description: `tx ${id}`, transaction_type: 'expense' });

describe('fetchTransactions', () => {
  describe('paginerings-parametre', () => {
    it('sender skip=0 på første side — ubetinget, ikke kun når skip er truthy', async () => {
      apiClient.get.mockResolvedValue(okResponse([]));

      await fetchTransactions({ skip: 0 });

      expect(requestedParams().get('skip')).toBe('0');
    });

    it('defaulter til skip=0 og limit=PAGE_SIZE når intet er angivet', async () => {
      apiClient.get.mockResolvedValue(okResponse([]));

      await fetchTransactions();

      const params = requestedParams();
      expect(params.get('skip')).toBe('0');
      expect(params.get('limit')).toBe(String(PAGE_SIZE));
    });

    it('sender det angivne skip og limit videre', async () => {
      apiClient.get.mockResolvedValue(okResponse([]));

      await fetchTransactions({ skip: 100, limit: 25 });

      const params = requestedParams();
      expect(params.get('skip')).toBe('100');
      expect(params.get('limit')).toBe('25');
    });

    it('sender filtre med som snake_case ved siden af pagineringen', async () => {
      apiClient.get.mockResolvedValue(okResponse([]));

      await fetchTransactions({
        startDate: '2026-06-01',
        endDate: '2026-06-30',
        categoryId: 7,
        skip: 50,
      });

      const params = requestedParams();
      expect(params.get('start_date')).toBe('2026-06-01');
      expect(params.get('end_date')).toBe('2026-06-30');
      expect(params.get('category_id')).toBe('7');
      expect(params.get('skip')).toBe('50');
    });

    it('udelader tomme filtre', async () => {
      apiClient.get.mockResolvedValue(okResponse([]));

      await fetchTransactions({ startDate: '', endDate: null, categoryId: undefined });

      const params = requestedParams();
      expect(params.has('start_date')).toBe(false);
      expect(params.has('end_date')).toBe(false);
      expect(params.has('category_id')).toBe(false);
    });
  });

  describe('envelope-formen {total_count, items}', () => {
    it('pakker items ud og læser total_count', async () => {
      apiClient.get.mockResolvedValue(okResponse({ total_count: 93, items: [row(1), row(2)] }));

      const result = await fetchTransactions();

      expect(result.totalCount).toBe(93);
      expect(result.items).toHaveLength(2);
    });

    it('mapper transaction_type til type på hver række', async () => {
      apiClient.get.mockResolvedValue(
        okResponse({ total_count: 1, items: [{ id: 1, transaction_type: 'income' }] }),
      );

      const result = await fetchTransactions();

      expect(result.items[0].type).toBe('income');
      expect(result.items[0].transaction_type).toBe('income');
    });

    it('giver totalCount = null, ikke 0, når total_count mangler', async () => {
      apiClient.get.mockResolvedValue(okResponse({ items: [row(1)] }));

      const result = await fetchTransactions();

      expect(result.totalCount).toBeNull();
      expect(result.items).toHaveLength(1);
    });

    it('læser total_count = 0 som et rigtigt nul (tom periode)', async () => {
      apiClient.get.mockResolvedValue(okResponse({ total_count: 0, items: [] }));

      const result = await fetchTransactions();

      expect(result.totalCount).toBe(0);
      expect(result.items).toEqual([]);
    });
  });

  // Overgangsgrenen: fjernes sammen med Array.isArray i unpackTransactionList
  // når envelopen er deployet (P3-36). Testen findes for at sletningen bliver
  // rød i stedet for tavst adfærdsændrende.
  describe('overgangsform: bar liste fra en endnu ikke opdateret server', () => {
    it('accepterer et array og bruger længden som tilnærmet total', async () => {
      apiClient.get.mockResolvedValue(okResponse([row(1), row(2), row(3)]));

      const result = await fetchTransactions();

      expect(result.items).toHaveLength(3);
      expect(result.totalCount).toBe(3);
    });

    it('mapper også rækkerne i den bare liste', async () => {
      apiClient.get.mockResolvedValue(okResponse([{ id: 1, transaction_type: 'expense' }]));

      const result = await fetchTransactions();

      expect(result.items[0].type).toBe('expense');
    });

    it('giver tom liste og total 0 på et tomt array', async () => {
      apiClient.get.mockResolvedValue(okResponse([]));

      const result = await fetchTransactions();

      expect(result.items).toEqual([]);
      expect(result.totalCount).toBe(0);
    });
  });

  it('kaster ApiError videre fra crud-laget på fejlsvar', async () => {
    apiClient.get.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Error',
      json: () => Promise.resolve({ detail: 'Server error' }),
    });

    await expect(fetchTransactions()).rejects.toThrow('Server error');
  });
});
