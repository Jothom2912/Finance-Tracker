import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as rulesApi from '../api/rules';
import { invalidateFinancialData } from '../lib/invalidateFinancialData';

export function rulesQueryKey() {
  return ['rules'];
}

export function useRules() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: rulesQueryKey(),
    queryFn: () => rulesApi.fetchRules(),
  });

  // Regel-ændringer påvirker fremtidig kategorisering — invalider også
  // transaktions-views så evt. afledte visninger refetches.
  const invalidateRuleViews = () => {
    queryClient.invalidateQueries({ queryKey: rulesQueryKey() });
    invalidateFinancialData(queryClient, { scope: 'transactions' });
  };

  const createMutation = useMutation({
    mutationFn: (data) => rulesApi.createRule(data),
    onSuccess: invalidateRuleViews,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => rulesApi.updateRule(id, data),
    onSuccess: invalidateRuleViews,
  });

  const removeMutation = useMutation({
    mutationFn: (id) => rulesApi.deleteRule(id),
    onSuccess: invalidateRuleViews,
  });

  return {
    rules: query.data ?? [],
    loading: query.isLoading,
    error: query.error ? query.error.message || 'Kunne ikke hente regler.' : null,
    create: createMutation.mutateAsync,
    update: updateMutation.mutateAsync,
    remove: removeMutation.mutateAsync,
    isSaving: createMutation.isPending || updateMutation.isPending,
  };
}
