import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { gqlRequest } from '../api/graphqlClient';
import { createQueryClientWrapper } from '../test-utils/renderWithQueryClient';
import { usePeriodOverview } from './usePeriodOverview';

vi.mock('../api/graphqlClient', () => ({
  gqlRequest: vi.fn(),
}));

describe('usePeriodOverview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('account_id', '1');
  });

  it('uses the same budget period for category spend and budget summary', async () => {
    gqlRequest.mockResolvedValue({
      periodOverview: {
        startDate: '2026-07-26',
        endDate: '2026-08-25',
        totalIncome: 13717,
        totalExpenses: 2872.82,
        netChangeInPeriod: 10844.18,
        expensesByCategory: [],
      },
      budgetSummary: { month: 8, year: 2026, items: [] },
    });
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(
      () => usePeriodOverview({ month: 8, year: 2026 }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(gqlRequest).toHaveBeenCalledWith(
      expect.stringContaining('periodOverview(month: $month, year: $year)'),
      { month: 8, year: 2026 },
    );
    expect(gqlRequest.mock.calls[0][0]).not.toContain('financialOverview');
    expect(result.current.overview.startDate).toBe('2026-07-26');
    expect(result.current.overview.endDate).toBe('2026-08-25');
  });
});
