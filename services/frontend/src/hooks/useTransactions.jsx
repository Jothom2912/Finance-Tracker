import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as transactionsApi from '../api/transactions';
import { invalidateFinancialData } from '../lib/invalidateFinancialData';

export function transactionsQueryKey(accountId, filters) {
  return ['transactions', { accountId, filters }];
}

export function useTransactions(filters) {
  const queryClient = useQueryClient();
  const accountId = localStorage.getItem('account_id');

  const query = useQuery({
    queryKey: transactionsQueryKey(accountId, filters),
    queryFn: () => transactionsApi.fetchTransactions(filters),
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
    transactions: query.data ?? [],
    loading: query.isLoading,
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
