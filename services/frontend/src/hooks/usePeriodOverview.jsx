import { useQuery } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import { gqlRequest } from '../api/graphqlClient';

// Samlet read-side for en kalendermåned via gateway'ens GraphQL —
// erstatter CategoriesPage's tidligere dobbelte REST-sti (snake_case
// dashboard/overview + budget-service summary), så dashboard og
// kategoriside læser samme felter fra samme kilde.
const PERIOD_OVERVIEW_QUERY = gql`
  query PeriodOverview($month: Int!, $year: Int!, $startDate: Date!, $endDate: Date!) {
    financialOverview(startDate: $startDate, endDate: $endDate) {
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

  const startDate = `${year}-${String(month).padStart(2, '0')}-01`;
  const lastDay = new Date(year, month, 0).getDate();
  const endDate = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;

  const query = useQuery({
    queryKey: periodOverviewQueryKey(accountId, month, year),
    queryFn: () => gqlRequest(PERIOD_OVERVIEW_QUERY, { month, year, startDate, endDate }),
    enabled: enabled && !!accountId,
  });

  return {
    overview: query.data?.financialOverview ?? null,
    budgetSummary: query.data?.budgetSummary ?? null,
    loading: query.isLoading,
    error: query.error ? query.error.message || 'Kunne ikke hente data.' : null,
    refetch: query.refetch,
  };
}
