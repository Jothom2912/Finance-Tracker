import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { gql } from 'graphql-request';
import { gqlRequest } from '../api/graphqlClient';
import { PAGE_SIZE } from '../lib/pagination';

// offset er Int! i gateway-skemaet (resolveren har default 0, men Strawberry
// giver et non-null felt): dokumentet SKAL erklære $offset: Int! og altid sende
// en værdi — offset: null fejler validering frem for at falde tilbage på
// default'en. Verificeret ved introspektion mod den kørende gateway 2026-07-26.
const SEARCH_QUERY = gql`
  query SearchTransactions(
    $query: String!
    $startDate: Date
    $endDate: Date
    $categoryId: Int
    $limit: Int!
    $offset: Int!
  ) {
    searchTransactions(
      query: $query
      startDate: $startDate
      endDate: $endDate
      categoryId: $categoryId
      limit: $limit
      offset: $offset
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
// page hører i nøglen af samme grund som i useTransactions: uden den serverer
// cachen side 1 for evigt, fordi alle sider deler nøgle.
export function transactionSearchQueryKey(accountId, query, filters, page) {
  return ['transactionSearch', { accountId, query, filters, page }];
}

const MIN_QUERY_LENGTH = 2;

export function useTransactionSearch(query, filters = {}, page = 1) {
  const accountId = localStorage.getItem('account_id');
  const trimmed = (query ?? '').trim();
  const enabled = trimmed.length >= MIN_QUERY_LENGTH;

  const result = useQuery({
    queryKey: transactionSearchQueryKey(accountId, trimmed, filters, page),
    queryFn: () =>
      gqlRequest(SEARCH_QUERY, {
        query: trimmed,
        startDate: filters.startDate || null,
        endDate: filters.endDate || null,
        categoryId: filters.categoryId ? Number(filters.categoryId) : null,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
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
    // null, ikke 0 — symmetrisk med useTransactions: 0 betyder "ingen hits", og
    // siden må kunne holde clampen tilbage indtil søgningen HAR svaret.
    totalCount: result.data?.searchTransactions?.totalCount ?? null,
    loading: enabled && result.isLoading,
    // Sand mens en tidligere sides (eller et tidligere søgeords) rækker står på
    // skærmen under en ny nøgle. Samme begrundelse som i useTransactions.
    isPaging: result.isPlaceholderData,
    error: result.error ? result.error.message || 'Søgningen fejlede.' : null,
  };
}
