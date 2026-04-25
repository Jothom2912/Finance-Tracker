import { QueryClient } from '@tanstack/react-query';

/**
 * Application-wide TanStack Query client.
 *
 * Configured as a module-level singleton so the same instance is used
 * by the QueryClientProvider in App.jsx and by any code path that
 * needs to call queryClient.invalidateQueries directly (for example
 * after a mutation that bypasses useMutation).
 *
 * Defaults reasoning:
 *
 * - staleTime: 30s. Query results are considered fresh for 30 seconds
 *   after fetch. Within that window, remounting a component or
 *   navigating back to the same view will reuse cached data without
 *   triggering a new request. This keeps the UI snappy without
 *   showing data that is meaningfully out of date.
 *
 * - retry: 1. The library default of 3 is too aggressive for a small
 *   app talking to local services - one retry is enough to ride out a
 *   transient blip without burying the user under retry latency when
 *   the backend is genuinely down.
 *
 * - refetchOnWindowFocus: false. Refetching every time the window
 *   regains focus is noisy for a finance dashboard where the user
 *   often tabs away to look something up. They can refresh
 *   explicitly when they want to.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
