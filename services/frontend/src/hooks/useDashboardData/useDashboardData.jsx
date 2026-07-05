import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import { gqlRequest } from '../../api/graphqlClient';
import { fetchGoals } from '../../api/goals';
import { formatAmount, formatDate } from '../../lib/formatters';
import { CHART_COLORS as COLORS } from '../../lib/chartColors';

const EXPENSES_BY_CATEGORY_FIELDS = `
      expensesByCategory {
        categoryId
        categoryName
        amount
        subcategories {
          subcategoryId
          subcategoryName
          amount
        }
      }
`;

const SHARED_FIELDS = `
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
    expensesByMonth {
      month
      totalExpenses
    }
`;

// Nuværende måned: currentMonthOverview har trend + respekterer kontoens
// budget-startdag.
const CURRENT_MONTH_QUERY = gql`
  query DashboardData($month: Int!, $year: Int!) {
    currentMonthOverview {
      startDate
      endDate
      totalIncome
      totalExpenses
      netChangeInPeriod
      ${EXPENSES_BY_CATEGORY_FIELDS}
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
    transactions(limit: 10) {
      id
      amount
      description
      date
      type
      categoryId
      categoryName
      subcategoryName
      categorizationTier
    }
    ${SHARED_FIELDS}
  }
`;

// Historisk måned: financialOverview over kalendermåneden (ingen trend).
const PERIOD_QUERY = gql`
  query DashboardPeriod($month: Int!, $year: Int!, $startDate: Date!, $endDate: Date!) {
    financialOverview(startDate: $startDate, endDate: $endDate) {
      startDate
      endDate
      totalIncome
      totalExpenses
      netChangeInPeriod
      ${EXPENSES_BY_CATEGORY_FIELDS}
      currentAccountBalance
      averageMonthlyExpenses
    }
    transactions(startDate: $startDate, endDate: $endDate, limit: 10) {
      id
      amount
      description
      date
      type
      categoryId
      categoryName
      subcategoryName
      categorizationTier
    }
    ${SHARED_FIELDS}
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

function periodBounds(month, year) {
  const startDate = `${year}-${String(month).padStart(2, '0')}-01`;
  const lastDay = new Date(year, month, 0).getDate();
  const endDate = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
  return { startDate, endDate };
}

export function useDashboardData({ month, year } = {}) {
  const accountId = localStorage.getItem('account_id');
  const now = new Date();
  const selectedMonth = month ?? now.getMonth() + 1;
  const selectedYear = year ?? now.getFullYear();
  const isCurrentMonth =
    selectedMonth === now.getMonth() + 1 && selectedYear === now.getFullYear();

  const { data, isLoading, error } = useQuery({
    queryKey: dashboardQueryKey(accountId, selectedMonth, selectedYear),
    queryFn: () => {
      if (isCurrentMonth) {
        return gqlRequest(CURRENT_MONTH_QUERY, { month: selectedMonth, year: selectedYear });
      }
      const { startDate, endDate } = periodBounds(selectedMonth, selectedYear);
      return gqlRequest(PERIOD_QUERY, {
        month: selectedMonth,
        year: selectedYear,
        startDate,
        endDate,
      });
    },
  });

  const { data: goalsData, isLoading: goalsLoading, error: goalsError } = useQuery({
    queryKey: ['goals', accountId],
    queryFn: () => fetchGoals(),
    select: (data) => (data ?? []).map(mapGoalFromRest),
  });

  const overview = useMemo(() => {
    if (data?.currentMonthOverview) return data.currentMonthOverview;
    if (data?.financialOverview) return { ...data.financialOverview, trend: null };
    return null;
  }, [data]);

  const budgetSummary = data?.budgetSummary ?? null;
  const goals = goalsData ?? [];
  const recentTransactions = data?.transactions ?? [];
  const expensesByMonth = data?.expensesByMonth ?? [];

  const processedCategoryData = useMemo(() => {
    if (!overview?.expensesByCategory?.length) return [];
    return overview.expensesByCategory
      .map((entry) => ({
        id: entry.categoryId,
        name: entry.categoryName,
        value: Math.abs(entry.amount),
        subcategories: (entry.subcategories ?? []).map((sub) => ({
          id: sub.subcategoryId,
          name: sub.subcategoryName,
          value: Math.abs(sub.amount),
        })),
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
    isCurrentMonth,
    loading: isLoading || goalsLoading,
    error: (error || goalsError) ? (error?.message || goalsError?.message || 'Kunne ikke hente dashboard-data.') : null,
    processedCategoryData,
    categoryDataWithPercentages,
    formatAmount,
    formatDate,
  };
}
