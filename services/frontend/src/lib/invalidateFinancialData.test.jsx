import { vi, describe, it, expect, afterEach } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import {
  invalidateFinancialData,
  invalidateAfterBankSync,
  BANK_SYNC_PROPAGATION_MS,
} from './invalidateFinancialData';

function createClientWithSpy() {
  const client = new QueryClient();
  const spy = vi.spyOn(client, 'invalidateQueries');
  return { client, spy };
}

function invalidatedPrefixes(spy) {
  return spy.mock.calls.map(([{ queryKey }]) => queryKey[0]);
}

afterEach(() => {
  vi.useRealTimers();
});

describe('invalidateFinancialData', () => {
  it('scope transactions invalidates all transaction-derived views', () => {
    const { client, spy } = createClientWithSpy();

    invalidateFinancialData(client, { scope: 'transactions' });

    expect(invalidatedPrefixes(spy).sort()).toEqual(
      ['dashboard', 'periodOverview', 'transactionSearch', 'transactions'],
    );
  });

  it('scope goals invalidates only the shared goals cache', () => {
    const { client, spy } = createClientWithSpy();

    invalidateFinancialData(client, { scope: 'goals' });

    expect(invalidatedPrefixes(spy)).toEqual(['goals']);
  });

  it('scope categories invalidates category-derived views', () => {
    const { client, spy } = createClientWithSpy();

    invalidateFinancialData(client, { scope: 'categories' });

    expect(invalidatedPrefixes(spy).sort()).toEqual(
      ['categories', 'dashboard', 'periodOverview', 'subcategories'],
    );
  });

  it('defaults to scope all covering every financial key exactly once', () => {
    const { client, spy } = createClientWithSpy();

    invalidateFinancialData(client);

    const prefixes = invalidatedPrefixes(spy);
    expect(prefixes.sort()).toEqual([
      'categories',
      'dashboard',
      'goals',
      'periodOverview',
      'subcategories',
      'transactionSearch',
      'transactions',
    ]);
  });

  it('throws on unknown scope instead of silently invalidating nothing', () => {
    const { client } = createClientWithSpy();

    expect(() => invalidateFinancialData(client, { scope: 'budgets' })).toThrow(
      /Ukendt invalidation scope/,
    );
  });
});

describe('invalidateAfterBankSync', () => {
  it('invalidates immediately and once more after the propagation window, without blocking', () => {
    vi.useFakeTimers();
    const { client, spy } = createClientWithSpy();

    invalidateAfterBankSync(client);

    // Første runde sker synkront — click-handleren blokerer ikke.
    expect(spy.mock.calls.length).toBeGreaterThan(0);
    const firstRoundCalls = spy.mock.calls.length;
    expect(invalidatedPrefixes(spy)).toContain('transactions');
    expect(invalidatedPrefixes(spy)).toContain('dashboard');

    // Lige før vinduet udløber: ingen ekstra invalidering.
    vi.advanceTimersByTime(BANK_SYNC_PROPAGATION_MS - 1);
    expect(spy.mock.calls.length).toBe(firstRoundCalls);

    // Efter vinduet: præcis én opfølgende runde — ingen uendelig polling.
    vi.advanceTimersByTime(1);
    expect(spy.mock.calls.length).toBe(firstRoundCalls * 2);

    vi.advanceTimersByTime(60_000);
    expect(spy.mock.calls.length).toBe(firstRoundCalls * 2);
  });
});
