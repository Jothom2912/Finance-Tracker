import { useQuery } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import { gqlRequest } from '../api/graphqlClient';

// Samlet read-side for kontoens budgetmåned via gateway'ens GraphQL.
// Både forbrug og budget bruger dermed samme start_day-aware interval.
const PERIOD_OVERVIEW_QUERY = gql`
  query PeriodOverview($month: Int!, $year: Int!) {
    periodOverview(month: $month, year: $year) {
      startDate
      endDate
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
  }
`;

export function periodOverviewQueryKey(accountId, month, year) {
  return ['periodOverview', { accountId, month, year }];
}

export function usePeriodOverview({ month, year, enabled = true }) {
  const accountId = localStorage.getItem('account_id');

  const query = useQuery({
    queryKey: periodOverviewQueryKey(accountId, month, year),
    queryFn: () => gqlRequest(PERIOD_OVERVIEW_QUERY, { month, year }),
    enabled: enabled && !!accountId,
  });

  return {
    overview: query.data?.periodOverview ?? null,
    budgetSummary: query.data?.budgetSummary ?? null,
    loading: query.isLoading,
    error: query.error ? query.error.message || 'Kunne ikke hente data.' : null,
    refetch: query.refetch,
  };
}
