import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import { gqlRequest } from '../../api/graphqlClient';
import { fetchGoals } from '../../api/goals';
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

export function dashboardQueryKey(accountId, month, year) {
  return ['dashboard', { accountId, month, year }];
}

function mapGoalFromRest(g) {
  return {
    id: g.idGoal,
    name: g.name,
    targetAmount: g.target_amount,
    currentAmount: g.current_amount,
    targetDate: g.target_date,
    status: g.effective_status,
    percentComplete: g.progress_percent,
  };
}

export function useDashboardData() {
  const accountId = localStorage.getItem('account_id');
  const now = new Date();
  const month = now.getMonth() + 1;
  const year = now.getFullYear();

  const { data, isLoading, error } = useQuery({
    queryKey: dashboardQueryKey(accountId, month, year),
    queryFn: () => gqlRequest(DASHBOARD_QUERY, { month, year }),
  });

  const { data: goalsData, isLoading: goalsLoading, error: goalsError } = useQuery({
    queryKey: ['goals', accountId],
    queryFn: () => fetchGoals(),
    select: (data) => (data ?? []).map(mapGoalFromRest),
  });

  const overview = data?.currentMonthOverview ?? null;
  const budgetSummary = data?.budgetSummary ?? null;
  const goals = goalsData ?? [];
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
    loading: isLoading || goalsLoading,
    error: (error || goalsError) ? (error?.message || goalsError?.message || 'Kunne ikke hente dashboard-data.') : null,
    processedCategoryData,
    categoryDataWithPercentages,
    formatAmount,
    formatDate,
  };
}
