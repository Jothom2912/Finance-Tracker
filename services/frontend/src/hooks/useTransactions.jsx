import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import * as transactionsApi from '../api/transactions';
import { invalidateFinancialData } from '../lib/invalidateFinancialData';
import { PAGE_SIZE } from '../lib/pagination';

// page er et selvstændigt argument, ikke et medlem af filters: filters sendes
// også til useTransactionSearch, så et REST-sidetal derinde ville forurene
// søgningens nøgle (og omvendt). filters er rent semantisk — *hvilket udsnit* —
// mens page er *hvilket vindue*.
// Prefix-invalidering (invalidateFinancialData) rammer stadig alle sider, fordi
// den matcher på ['transactions'] alene.
export function transactionsQueryKey(accountId, filters, page) {
  return ['transactions', { accountId, filters, page }];
}

export function useTransactions(filters, page = 1) {
  const queryClient = useQueryClient();
  const accountId = localStorage.getItem('account_id');

  const query = useQuery({
    queryKey: transactionsQueryKey(accountId, filters, page),
    queryFn: () =>
      transactionsApi.fetchTransactions({
        ...filters,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    // Behold forrige sides rækker mens den nye henter — tabellen kollapser ikke
    // i højden ved sideskift. Samme mønster som useTransactionSearch.
    placeholderData: keepPreviousData,
  });

  const invalidateTransactionViews = () => {
    invalidateFinancialData(queryClient, { scope: 'transactions' });
  };

  const createMutation = useMutation({
    mutationFn: transactionsApi.createTransaction,
    onSuccess: invalidateTransactionViews,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => transactionsApi.updateTransaction(id, data),
    onSuccess: invalidateTransactionViews,
  });

  const removeMutation = useMutation({
    mutationFn: transactionsApi.deleteTransaction,
    onSuccess: invalidateTransactionViews,
  });

  const uploadCsvMutation = useMutation({
    mutationFn: ({ file, bankFormat }) =>
      transactionsApi.uploadTransactionsCsv({ file, bankFormat }),
    onSuccess: invalidateTransactionViews,
  });

  return {
    transactions: query.data?.items ?? [],
    // null, ikke 0: 0 betyder "tom periode". Med null kan siden se forskel på
    // "serveren har svaret, der er ingen rækker" og "vi ved det ikke endnu",
    // og step 9's clamp mod pageCount kan holdes tilbage indtil vi ved det.
    totalCount: query.data?.totalCount ?? null,
    loading: query.isLoading,
    // isPlaceholderData, ikke isFetching: den er sand præcis mens en ældre
    // sides rækker står på skærmen under en ny nøgle. isFetching er også sand
    // under en baggrunds-refetch efter en mutation, hvor et dæmp ville være støj.
    isPaging: query.isPlaceholderData,
    error: query.error
      ? query.error.message || 'Kunne ikke hente transaktioner.'
      : null,
    create: createMutation.mutateAsync,
    update: updateMutation.mutateAsync,
    remove: removeMutation.mutateAsync,
    uploadCsv: uploadCsvMutation.mutateAsync,
    isSaving: createMutation.isPending || updateMutation.isPending,
  };
}
