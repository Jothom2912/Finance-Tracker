/**
 * Centraliseret cache-invalidering for de finansielle query-nøgler.
 *
 * Query-nøgle-prefixer i appen (defineret i de respektive hooks):
 *
 *   ['transactions', ...]      useTransactions
 *   ['transactionSearch', ...] useTransactionSearch (analytics-læsesiden)
 *   ['dashboard', ...]         useDashboardData (GraphQL-aggregat)
 *   ['periodOverview', ...]    usePeriodOverview (CategoriesPage)
 *   ['goals', ...]             useGoals
 *   ['categories', ...]        useCategories
 *   ['subcategories', ...]     useSubcategories
 *
 * Scopes grupperer nøglerne efter hvilken domæne-mutation der skete, så
 * hvert kald-sted ikke selv skal vide hvilke afledte views der findes.
 * Invalidering af en ikke-mounted query markerer den blot stale — den
 * refetches først når en komponent abonnerer igen — så det er billigt at
 * invalidere bredt inden for et scope.
 */
const FINANCIAL_QUERY_SCOPES = {
  // En transaktion er oprettet/ændret/slettet (manuelt, CSV eller bank-sync).
  transactions: [
    ['transactions'],
    ['transactionSearch'],
    ['dashboard'],
    ['periodOverview'],
  ],
  // Et opsparingsmål er oprettet/ændret/slettet. Dashboardets mål-sektion
  // læser via useGoals (samme ['goals']-cache), så én nøgle dækker begge views.
  goals: [['goals']],
  // Kategorier/subkategorier er ændret — påvirker også de views der
  // grupperer beløb pr. kategori.
  categories: [
    ['categories'],
    ['subcategories'],
    ['dashboard'],
    ['periodOverview'],
  ],
};

FINANCIAL_QUERY_SCOPES.all = [
  ...new Map(
    Object.values(FINANCIAL_QUERY_SCOPES)
      .flat()
      .map((key) => [key[0], key]),
  ).values(),
];

/**
 * Invalider de finansielle queries for et givet scope.
 *
 * @param {import('@tanstack/react-query').QueryClient} queryClient
 * @param {{ scope?: 'transactions' | 'goals' | 'categories' | 'all' }} options
 */
export function invalidateFinancialData(queryClient, { scope = 'all' } = {}) {
  const keys = FINANCIAL_QUERY_SCOPES[scope];
  if (!keys) {
    throw new Error(`Ukendt invalidation scope: ${scope}`);
  }
  keys.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }));
}

/**
 * Bank-sync-sagaens "completed" betyder at skrivningerne er accepteret —
 * ikke at analytics-læsesiden (ES-projektionen bag dashboard/search) har
 * indhentet dem. Én invalidering nu + én opfølgende efter det typiske
 * propagerings-vindue er det simpleste ærlige svar: kaldet blokerer ikke
 * (ingen sleep i click-handleren), og mounted queries refetcher to gange
 * med bounded afstand i stedet for at polle i det uendelige.
 */
export const BANK_SYNC_PROPAGATION_MS = 2500;

export function invalidateAfterBankSync(queryClient) {
  invalidateFinancialData(queryClient, { scope: 'transactions' });
  setTimeout(() => {
    invalidateFinancialData(queryClient, { scope: 'transactions' });
  }, BANK_SYNC_PROPAGATION_MS);
}
