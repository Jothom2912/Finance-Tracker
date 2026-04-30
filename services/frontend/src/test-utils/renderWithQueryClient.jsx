/**
 * Test helpers for components/hooks that use TanStack Query.
 *
 * IMPORTANT: This file deliberately does NOT import the production
 * singleton from `src/lib/queryClient.js`. Each test gets its own fresh
 * QueryClient instance to guarantee:
 *
 *   1. Tests cannot leak cache state into each other (no test ordering bugs).
 *   2. Tests cannot accidentally share cache with the production singleton
 *      (which would only matter in fully wired-up integration tests, but the
 *      principle of isolation is the same).
 *
 * Default options here are tuned for tests, NOT for production:
 *   - retry: false     -> errors surface immediately, no retry delays
 *   - gcTime: 0        -> queries are garbage-collected the moment a test
 *                         tears down, so the next test starts truly clean
 *   - refetchOnWindowFocus: false -> jsdom doesn't focus, but explicit > implicit
 *
 * If you ever feel tempted to `import { queryClient } from '../lib/queryClient'`
 * inside a test "for consistency" — DO NOT. That would re-introduce shared
 * mutable state across tests and cause subtle flakiness that is painful to
 * debug. The runtime singleton and the test-time clients are intentionally
 * different instances; the abstraction boundary is the QueryClientProvider.
 */
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

/**
 * Render a component tree with a fresh QueryClientProvider.
 * Returns the standard React Testing Library result plus the `client` so
 * tests can call `client.invalidateQueries(...)` etc. if needed.
 */
export function renderWithQueryClient(ui, options = {}) {
  const client = createTestQueryClient();
  const result = render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
    options,
  );
  return { ...result, client };
}

/**
 * Build a wrapper component for `renderHook` (or for use as the
 * `wrapper` option in `render`). Returns both the wrapper and the
 * underlying client so tests can inspect/invalidate cache.
 *
 * Usage:
 *   const { wrapper, client } = createQueryClientWrapper();
 *   const { result } = renderHook(() => useMyHook(), { wrapper });
 */
export function createQueryClientWrapper() {
  const client = createTestQueryClient();
  function Wrapper({ children }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return { wrapper: Wrapper, client };
}
