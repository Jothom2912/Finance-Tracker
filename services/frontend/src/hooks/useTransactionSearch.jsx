import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import { gqlRequest } from '../api/graphqlClient';

const SEARCH_QUERY = gql`
  query SearchTransactions(
    $query: String!
    $startDate: Date
    $endDate: Date
    $categoryId: Int
    $limit: Int!
  ) {
    searchTransactions(
      query: $query
      startDate: $startDate
      endDate: $endDate
      categoryId: $categoryId
      limit: $limit
    ) {
      totalCount
      items {
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
    }
  }
`;

// accountId SKAL i nøglen: gqlRequest sender X-Account-ID implicit, og
// implicitte inputs der ændrer serverens svar hører i query-keyen
// (jf. reglen i docs/followups.md).
export function transactionSearchQueryKey(accountId, query, filters) {
  return ['transactionSearch', { accountId, query, filters }];
}

const MIN_QUERY_LENGTH = 2;

export function useTransactionSearch(query, filters = {}) {
  const accountId = localStorage.getItem('account_id');
  const trimmed = (query ?? '').trim();
  const enabled = trimmed.length >= MIN_QUERY_LENGTH;

  const result = useQuery({
    queryKey: transactionSearchQueryKey(accountId, trimmed, filters),
    queryFn: () =>
      gqlRequest(SEARCH_QUERY, {
        query: trimmed,
        startDate: filters.startDate || null,
        endDate: filters.endDate || null,
        categoryId: filters.categoryId ? Number(filters.categoryId) : null,
        limit: 100,
      }),
    enabled,
    // Behold forrige resultat mens et nyt søgeord henter — listen
    // blinker ikke tom for hvert (debouncet) tastetryk.
    placeholderData: keepPreviousData,
  });

  // GraphQL svarer camelCase; TransactionsList (og resten af
  // transaktions-UI'et) forventer REST-nøglerne fra transaction-service.
  const results = (result.data?.searchTransactions?.items ?? []).map((t) => ({
    id: t.id,
    amount: t.amount,
    description: t.description,
    date: t.date,
    type: t.type,
    category_id: t.categoryId,
    category_name: t.categoryName,
    subcategory_name: t.subcategoryName,
    categorization_tier: t.categorizationTier,
  }));

  return {
    isSearchActive: enabled,
    results,
    totalCount: result.data?.searchTransactions?.totalCount ?? 0,
    loading: enabled && result.isLoading,
    error: result.error ? result.error.message || 'Søgningen fejlede.' : null,
  };
}
