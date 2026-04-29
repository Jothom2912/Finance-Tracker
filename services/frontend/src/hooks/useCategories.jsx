import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchCategories as apiFetchCategories } from '../api/categories';

export function categoriesQueryKey(accountId) {
  return ['categories', { accountId }];
}

export function useCategories() {
  const queryClient = useQueryClient();
  const accountId = localStorage.getItem('account_id');

  const query = useQuery({
    queryKey: categoriesQueryKey(accountId),
    queryFn: () => apiFetchCategories(),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['categories'] });
  };

  return {
    categories: query.data ?? [],
    loading: query.isLoading,
    error: query.error
      ? query.error.message || 'Kunne ikke hente kategorier.'
      : null,
    refresh,
  };
}
