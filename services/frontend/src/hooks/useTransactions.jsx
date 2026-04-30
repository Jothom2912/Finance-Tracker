import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as transactionsApi from '../api/transactions';

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
    queryClient.invalidateQueries({ queryKey: ['transactions'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  };

  const removeMutation = useMutation({
    mutationFn: transactionsApi.deleteTransaction,
    onSuccess: invalidateTransactionViews,
  });

  const uploadCsvMutation = useMutation({
    mutationFn: transactionsApi.uploadTransactionsCsv,
    onSuccess: invalidateTransactionViews,
  });

  return {
    transactions: query.data ?? [],
    loading: query.isLoading,
    error: query.error
      ? query.error.message || 'Kunne ikke hente transaktioner.'
      : null,
    remove: removeMutation.mutateAsync,
    uploadCsv: uploadCsvMutation.mutateAsync,
  };
}
