import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import { gqlRequest } from '../../api/graphqlClient';
import { useGoals } from '../useGoals';
import { formatAmount, formatDate } from '../../lib/formatters';
import { CHART_COLORS as COLORS } from '../../lib/chartColors';

// Antal budgetmåneder i cashflow-grafen (server-drevet, dense/zero-filled).
export const TREND_MONTHS = 12;

// Ét samlet query for både nuværende og historiske måneder:
// periodOverview følger altid kontoens budget-startdag og har trend for
// alle måneder (lukkede followups-punktet om månedsvælgerens
// kalender/budget-inkonsistens). transactions(month, year) bruger samme
// periodesemantik, så "Seneste transaktioner" matcher overblikket.
const DASHBOARD_QUERY = gql`
  query DashboardData($month: Int!, $year: Int!, $months: Int!) {
    periodOverview(month: $month, year: $year) {
      startDate
      endDate
      isCurrent
      totalIncome
      totalExpenses
      netChangeInPeriod
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
    transactions(month: $month, year: $year, limit: 10) {
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
    cashflowByMonth(months: $months) {
      month
      totalIncome
      totalExpenses
      net
    }
    monthComparison(month: $month, year: $year, limit: 5) {
      previousMonth
      previousYear
      totalCurrent
      totalPrevious
      deltas {
        categoryId
        categoryName
        currentAmount
        previousAmount
        changeAmount
        changePercent
      }
    }
  }
`;

export function dashboardQueryKey(accountId, month, year, months = TREND_MONTHS) {
  return ['dashboard', { accountId, month, year, months }];
}

export function useDashboardData({ month, year } = {}) {
  const accountId = localStorage.getItem('account_id');
  const now = new Date();
  const selectedMonth = month ?? now.getMonth() + 1;
  const selectedYear = year ?? now.getFullYear();

  const { data, isLoading, error } = useQuery({
    queryKey: dashboardQueryKey(accountId, selectedMonth, selectedYear),
    queryFn: () =>
      gqlRequest(DASHBOARD_QUERY, {
        month: selectedMonth,
        year: selectedYear,
        months: TREND_MONTHS,
      }),
  });

  const { goals: goalsData, loading: goalsLoading, error: goalsError } = useGoals();

  const overview = data?.periodOverview ?? null;
  const budgetSummary = data?.budgetSummary ?? null;
  const goals = goalsData ?? [];
  const recentTransactions = data?.transactions ?? [];
  const cashflowByMonth = data?.cashflowByMonth ?? [];
  const monthComparison = data?.monthComparison ?? null;
  // Serveren afgør om den valgte budgetmåned er den nuværende —
  // klient-uret kan ikke, når perioden følger budget-startdagen.
  const isCurrentMonth = overview?.isCurrent ?? false;

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
    cashflowByMonth,
    monthComparison,
    isCurrentMonth,
    loading: isLoading || goalsLoading,
    error: (error || goalsError) ? (error?.message || goalsError?.message || 'Kunne ikke hente dashboard-data.') : null,
    processedCategoryData,
    categoryDataWithPercentages,
    formatAmount,
    formatDate,
  };
}
