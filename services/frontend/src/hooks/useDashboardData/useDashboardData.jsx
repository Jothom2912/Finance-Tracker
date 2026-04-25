import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import { gqlRequest } from '../../api/graphqlClient';
import { formatAmount, formatDate } from '../../lib/formatters';
import { CHART_COLORS as COLORS } from '../../lib/chartColors';

const DASHBOARD_QUERY = gql`
  query DashboardData($month: Int!, $year: Int!) {
    currentMonthOverview {
      startDate
      endDate
      totalIncome
      totalExpenses
      netChangeInPeriod
      expensesByCategory {
        categoryName
        amount
      }
      currentAccountBalance
      averageMonthlyExpenses
      trend {
        incomeChangePercent
        expenseChangePercent
        netChangeDiff
        previousMonthIncome
        previousMonthExpenses
      }
    }
    budgetSummary(month: $month, year: $year) {
      month
      year
      items {
        categoryId
        categoryName
        budgetAmount
        spentAmount
        remainingAmount
        percentageUsed
      }
      totalBudget
      totalSpent
      totalRemaining
      overBudgetCount
    }
    goalProgress {
      id
      name
      targetAmount
      currentAmount
      targetDate
      status
      percentComplete
    }
    transactions(limit: 10) {
      id
      amount
      description
      date
      type
      categoryId
      categorizationTier
    }
    expensesByMonth {
      month
      totalExpenses
    }
  }
`;

export function dashboardQueryKey(month, year) {
  return ['dashboard', { month, year }];
}

export function useDashboardData() {
  const now = new Date();
  const month = now.getMonth() + 1;
  const year = now.getFullYear();

  const { data, isLoading, error } = useQuery({
    queryKey: dashboardQueryKey(month, year),
    queryFn: () => gqlRequest(DASHBOARD_QUERY, { month, year }),
  });

  const overview = data?.currentMonthOverview ?? null;
  const budgetSummary = data?.budgetSummary ?? null;
  const goals = data?.goalProgress ?? [];
  const recentTransactions = data?.transactions ?? [];
  const expensesByMonth = data?.expensesByMonth ?? [];

  const processedCategoryData = useMemo(() => {
    if (!overview?.expensesByCategory?.length) return [];
    return overview.expensesByCategory
      .map((entry) => ({
        name: entry.categoryName,
        value: Math.abs(entry.amount),
      }))
      .filter((item) => item.value > 0)
      .sort((a, b) => b.value - a.value);
  }, [overview]);

  const categoryDataWithPercentages = useMemo(() => {
    if (!processedCategoryData.length) return [];
    const total = processedCategoryData.reduce((sum, item) => sum + item.value, 0);
    if (total === 0) return [];

    return processedCategoryData.map((item, index) => ({
      ...item,
      percentage: ((item.value / total) * 100).toFixed(1),
      color: COLORS[index % COLORS.length],
    }));
  }, [processedCategoryData]);

  return {
    overview,
    budgetSummary,
    goals,
    recentTransactions,
    expensesByMonth,
    loading: isLoading,
    error: error ? error.message || 'Kunne ikke hente dashboard-data.' : null,
    processedCategoryData,
    categoryDataWithPercentages,
    formatAmount,
    formatDate,
  };
}
