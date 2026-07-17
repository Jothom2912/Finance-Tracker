import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('../utils/apiClient', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import apiClient from '../utils/apiClient';
import { closeMonthlyBudget } from './monthlyBudgets';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  localStorage.setItem('account_id', '42');
});

describe('closeMonthlyBudget', () => {
  it('POSTs to /close with account, month, year and default budget_start_day', async () => {
    apiClient.post.mockResolvedValue({ ok: true, status: 204 });

    await closeMonthlyBudget({ month: 6, year: 2026 });

    const url = apiClient.post.mock.calls[0][0];
    expect(url).toContain('/monthly-budgets/close');
    expect(url).toContain('account_id=42');
    expect(url).toContain('month=6');
    expect(url).toContain('year=2026');
    expect(url).toContain('budget_start_day=1');
  });

  it('throws ApiError with status on 409 (already closed)', async () => {
    apiClient.post.mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Monthly budget already closed' }),
    });

    await expect(closeMonthlyBudget({ month: 6, year: 2026 })).rejects.toMatchObject({
      status: 409,
    });
  });

  it('throws ApiError with status on 503 (fail-closed upstream)', async () => {
    apiClient.post.mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Upstream unavailable' }),
    });

    await expect(closeMonthlyBudget({ month: 6, year: 2026 })).rejects.toMatchObject({
      status: 503,
    });
  });
});
