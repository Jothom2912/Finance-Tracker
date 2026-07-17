import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useDashboardData } from './useDashboardData';
import { createQueryClientWrapper } from '../../test-utils/renderWithQueryClient';

vi.mock('../../api/graphqlClient', () => ({
  gqlRequest: vi.fn(),
}));

vi.mock('../../api/goals', () => ({
  fetchGoals: vi.fn(),
  createGoal: vi.fn(),
  updateGoal: vi.fn(),
  deleteGoal: vi.fn(),
}));

import { gqlRequest } from '../../api/graphqlClient';
import { fetchGoals } from '../../api/goals';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  fetchGoals.mockResolvedValue([]);
});

const mockGraphQLResponse = {
  periodOverview: {
    startDate: '2026-03-01',
    endDate: '2026-03-31',
    isCurrent: false,
    trend: {
      incomeChangePercent: 12.5,
      expenseChangePercent: -8.0,
      netChangeDiff: 1500,
      previousMonthIncome: 8000,
      previousMonthExpenses: 6500,
    },
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
  cashflowByMonth: [
    { month: '2026-02', totalIncome: 8000, totalExpenses: 6500, net: 1500 },
    { month: '2026-03', totalIncome: 10000, totalExpenses: 6000, net: 4000 },
  ],
  monthComparison: {
    previousMonth: 2,
    previousYear: 2026,
    totalCurrent: 6000,
    totalPrevious: 6500,
    deltas: [
      {
        categoryId: 1,
        categoryName: 'Food',
        currentAmount: 3000,
        previousAmount: 2500,
        changeAmount: 500,
        changePercent: 20.0,
      },
    ],
  },
};

describe('useDashboardData', () => {
  it('fetches all dashboard data via GraphQL on mount', async () => {
    localStorage.setItem('account_id', 'account-1');
    gqlRequest.mockResolvedValue(mockGraphQLResponse);
    fetchGoals.mockResolvedValue([
      {
        idGoal: 1,
        name: 'Ferie',
        target_amount: 10000,
        current_amount: 2500,
        target_date: '2026-12-01',
        status: 'active',
        effective_status: 'active',
        progress_percent: 25,
      },
    ]);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.overview).toEqual(mockGraphQLResponse.periodOverview);
    expect(result.current.budgetSummary).toEqual(mockGraphQLResponse.budgetSummary);
    expect(result.current.goals).toEqual([
      {
        id: 1,
        name: 'Ferie',
        targetAmount: 10000,
        currentAmount: 2500,
        targetDate: '2026-12-01',
        status: 'active',
        storedStatus: 'active',
        percentComplete: 25,
        isDefaultSavingsGoal: false,
      },
    ]);
    expect(result.current.recentTransactions).toEqual(mockGraphQLResponse.transactions);
    expect(result.current.error).toBeNull();
  });

  it('refetches GraphQL when account changes', async () => {
    const accountOneResponse = {
      ...mockGraphQLResponse,
      periodOverview: {
        ...mockGraphQLResponse.periodOverview,
        totalIncome: 100,
      },
    };
    const accountTwoResponse = {
      ...mockGraphQLResponse,
      periodOverview: {
        ...mockGraphQLResponse.periodOverview,
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
      periodOverview: {
        ...mockGraphQLResponse.periodOverview,
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
      periodOverview: {
        ...mockGraphQLResponse.periodOverview,
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

  it('exposes cashflow, comparison and server-driven isCurrentMonth', async () => {
    gqlRequest.mockResolvedValue(mockGraphQLResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.cashflowByMonth).toHaveLength(2);
    expect(result.current.monthComparison.deltas[0].categoryName).toBe('Food');
    // isCurrent kommer fra serveren (budgetperiode-semantik), ikke klient-uret.
    expect(result.current.isCurrentMonth).toBe(false);
  });

  it('exposes trend for historic months too', async () => {
    gqlRequest.mockResolvedValue(mockGraphQLResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData({ month: 3, year: 2026 }), { wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.overview.trend.expenseChangePercent).toBe(-8.0);
  });

  it('exposes formatAmount and formatDate utilities', async () => {
    gqlRequest.mockResolvedValue(mockGraphQLResponse);

    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDashboardData(), { wrapper });

    expect(typeof result.current.formatAmount).toBe('function');
    expect(typeof result.current.formatDate).toBe('function');
  });
});
