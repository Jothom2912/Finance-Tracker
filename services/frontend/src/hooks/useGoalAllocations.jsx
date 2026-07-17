import { useQuery } from '@tanstack/react-query';
import * as goalsApi from '../api/goals';

/**
 * Allocation-historik for ét mål. Lazy: hentes først når `enabled` er true
 * (fx når brugeren folder historik-sektionen ud), så GoalOverview ikke
 * N+1-fetcher for alle mål ved load.
 */
export function useAllocationHistory(goalId, { enabled = true } = {}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['goals', 'allocation-history', goalId],
    queryFn: () => goalsApi.fetchAllocationHistory(goalId),
    enabled: enabled && goalId != null,
  });

  return {
    history: data ?? [],
    loading: isLoading,
    error: error ? (error.message || 'Kunne ikke hente historik.') : null,
  };
}

/** Uallokeret budget-overskud for den aktive konto (X-Account-ID). */
export function useUnallocatedSurplus() {
  const accountId = localStorage.getItem('account_id');

  const { data, isLoading, error } = useQuery({
    queryKey: ['goals', 'unallocated-surplus', accountId],
    queryFn: () => goalsApi.fetchUnallocatedSurplus(),
  });

  return {
    total: data?.total ?? 0,
    entries: data?.entries ?? [],
    loading: isLoading,
    error: error ? (error.message || 'Kunne ikke hente uallokeret overskud.') : null,
  };
}
