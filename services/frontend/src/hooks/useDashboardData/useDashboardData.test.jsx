import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useDashboardData } from './useDashboardData';
import { createQueryClientWrapper } from '../../test-utils/renderWithQueryClient';

vi.mock('../../api/graphqlClient', () => ({
  gqlRequest: vi.fn(),
}));

import { gqlRequest } from '../../api/graphqlClient';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

const mockGraphQLResponse = {
  currentMonthOverview: {
    startDate: '2026-03-01',
    endDate: '2026-03-31',
    totalIncome: 10000,
    totalExpenses: 6000,
    netChangeInPeriod: 4000,
    expensesByCategory: [
      { categoryName: 'Food', amount: 3000 },
      { categoryName: 'Transport', amount: 2000 },
      { categoryName: 'Rent', amount: 1000 },
    ],
    currentAccountBalance: 15000,
    averageMonthlyExpenses: 6000,
  },
  budgetSummary: {
    month: '03',
    year: '2026',
    items: [
      {
        categoryId: 1,
        categoryName: 'Food',
        budgetAmount: 4000,
        spentAmount: 3000,
        remainingAmount: 1000,
        percentageUsed: 75,
      },
    ],
    totalBudget: 4000,
    totalSpent: 3000,
    totalRemaining: 1000,
    overBudgetCount: 0,
  },
  goalProgress: [
    {
      id: 1,
      name: 'Ferie',
      targetAmount: 10000,
      currentAmount: 3500,
      targetDate: '2026-09-01',
      status: 'active',
      percentComplete: 35.0,
    },
  ],
  transactions: [
    {
      id: 1,
      amount: -500,
      description: 'Netto',
      date: '2026-03-04',
      type: 'expense',
      categoryId: 1,
    },
  ],
};

describe('useDashboardData', () => {
  it('fetches all dashboard data via GraphQL on mount', async () => {
    localStorage.setItem('account_id', 'account-1');
    gqlRequest.mockResolvedValue(mockGraphQLResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.overview).toEqual(mockGraphQLResponse.currentMonthOverview);
    expect(result.current.budgetSummary).toEqual(mockGraphQLResponse.budgetSummary);
    expect(result.current.goals).toEqual(mockGraphQLResponse.goalProgress);
    expect(result.current.recentTransactions).toEqual(mockGraphQLResponse.transactions);
    expect(result.current.error).toBeNull();
  });

  it('refetches instead of reusing cache when account changes', async () => {
    const accountOneResponse = {
      ...mockGraphQLResponse,
      currentMonthOverview: {
        ...mockGraphQLResponse.currentMonthOverview,
        totalIncome: 100,
      },
    };
    const accountTwoResponse = {
      ...mockGraphQLResponse,
      currentMonthOverview: {
        ...mockGraphQLResponse.currentMonthOverview,
        totalIncome: 200,
      },
    };

    localStorage.setItem('account_id', 'account-1');
    gqlRequest.mockResolvedValueOnce(accountOneResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result, rerender } = renderHook(() => useDashboardData(), { wrapper });

    await waitFor(() => {
      expect(result.current.overview?.totalIncome).toBe(100);
    });

    localStorage.setItem('account_id', 'account-2');
    gqlRequest.mockResolvedValueOnce(accountTwoResponse);
    rerender();

    await waitFor(() => {
      expect(result.current.overview?.totalIncome).toBe(200);
    });
    expect(gqlRequest).toHaveBeenCalledTimes(2);
  });

  it('processes category data sorted by value descending', async () => {
    gqlRequest.mockResolvedValue(mockGraphQLResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    const names = result.current.processedCategoryData.map((c) => c.name);
    expect(names).toEqual(['Food', 'Transport', 'Rent']);
    expect(result.current.processedCategoryData[0].value).toBe(3000);
  });

  it('computes percentages and assigns colors', async () => {
    gqlRequest.mockResolvedValue(mockGraphQLResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    const { categoryDataWithPercentages } = result.current;
    expect(categoryDataWithPercentages).toHaveLength(3);

    const foodEntry = categoryDataWithPercentages.find((c) => c.name === 'Food');
    expect(foodEntry.percentage).toBe('50.0');
    expect(foodEntry.color).toBeDefined();
  });

  it('handles negative amounts by taking absolute value', async () => {
    gqlRequest.mockResolvedValue({
      ...mockGraphQLResponse,
      currentMonthOverview: {
        ...mockGraphQLResponse.currentMonthOverview,
        expensesByCategory: [{ categoryName: 'Groceries', amount: -500 }],
      },
    });

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.processedCategoryData[0].value).toBe(500);
  });

  it('filters out zero-value categories', async () => {
    gqlRequest.mockResolvedValue({
      ...mockGraphQLResponse,
      currentMonthOverview: {
        ...mockGraphQLResponse.currentMonthOverview,
        expensesByCategory: [
          { categoryName: 'Real', amount: 100 },
          { categoryName: 'Empty', amount: 0 },
        ],
      },
    });

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.processedCategoryData).toHaveLength(1);
    expect(result.current.processedCategoryData[0].name).toBe('Real');
  });

  it('sets error on fetch failure', async () => {
    gqlRequest.mockRejectedValue(new Error('Network error'));

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Network error');
    expect(result.current.overview).toBeNull();
  });

  it('returns empty arrays when data is null', async () => {
    gqlRequest.mockResolvedValue({});

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.overview).toBeNull();
    expect(result.current.budgetSummary).toBeNull();
    expect(result.current.goals).toEqual([]);
    expect(result.current.recentTransactions).toEqual([]);
    expect(result.current.processedCategoryData).toEqual([]);
  });

  it('exposes formatAmount and formatDate utilities', async () => {
    gqlRequest.mockResolvedValue(mockGraphQLResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    expect(typeof result.current.formatAmount).toBe('function');
    expect(typeof result.current.formatDate).toBe('function');
  });
});
