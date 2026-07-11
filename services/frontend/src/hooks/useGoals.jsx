import { useQuery } from '@tanstack/react-query';
import { fetchGoals } from '../api/goals';

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
    percentComplete: g.progress_percent,
  };
}

export function goalsQueryKey(accountId) {
  return ['goals', accountId];
}

export function useGoals() {
  const accountId = localStorage.getItem('account_id');

  const { data, isLoading, error } = useQuery({
    queryKey: goalsQueryKey(accountId),
    queryFn: () => fetchGoals(),
    select: (goals) => (goals ?? []).map(mapGoalFromRest),
  });

  return {
    goals: data ?? [],
    loading: isLoading,
    error: error ? (error.message || 'Kunne ikke hente mål.') : null,
  };
}
