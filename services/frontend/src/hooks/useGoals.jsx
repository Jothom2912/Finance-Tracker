import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as goalsApi from '../api/goals';
import { invalidateFinancialData } from '../lib/invalidateFinancialData';

/**
 * Single source of truth for the REST -> UI goal shape. Any consumer that
 * needs goals should go through `useGoals` so there is exactly one mapping
 * and one cache entry per account, instead of each screen fetching and
 * shaping the data independently.
 */
export function mapGoalFromRest(g) {
  return {
    id: g.idGoal,
    name: g.name,
    targetAmount: g.target_amount,
    currentAmount: g.current_amount,
    targetDate: g.target_date,
    status: g.effective_status,
    // Redigeringsformularen skal bruge den *gemte* status (active/paused) —
    // effective_status kan være beregnet (completed/expired) og findes ikke
    // som valgmulighed i formularen.
    storedStatus: g.status,
    percentComplete: g.progress_percent,
  };
}

export function goalsQueryKey(accountId) {
  return ['goals', accountId];
}

export function useGoals() {
  const queryClient = useQueryClient();
  const accountId = localStorage.getItem('account_id');

  const { data, isLoading, error } = useQuery({
    queryKey: goalsQueryKey(accountId),
    queryFn: () => goalsApi.fetchGoals(),
    select: (goals) => (goals ?? []).map(mapGoalFromRest),
  });

  const invalidateGoalViews = () => {
    invalidateFinancialData(queryClient, { scope: 'goals' });
  };

  const createMutation = useMutation({
    mutationFn: goalsApi.createGoal,
    onSuccess: invalidateGoalViews,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data: goalData }) => goalsApi.updateGoal(id, goalData),
    onSuccess: invalidateGoalViews,
  });

  const removeMutation = useMutation({
    mutationFn: goalsApi.deleteGoal,
    onSuccess: invalidateGoalViews,
  });

  return {
    goals: data ?? [],
    loading: isLoading,
    error: error ? (error.message || 'Kunne ikke hente mål.') : null,
    create: createMutation.mutateAsync,
    update: (id, goalData) => updateMutation.mutateAsync({ id, data: goalData }),
    remove: removeMutation.mutateAsync,
  };
}
