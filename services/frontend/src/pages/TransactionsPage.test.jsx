import { vi, describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import TransactionsPage from './TransactionsPage';
import { useTransactions } from '../hooks/useTransactions';
import { useTransactionSearch } from '../hooks/useTransactionSearch';
import { PAGE_SIZE } from '../lib/pagination';

vi.mock('../hooks/useTransactions');
vi.mock('../hooks/useTransactionSearch');
// Siden bruger kun useNavigate af routeren, så den mockes frem for at pakke
// testen i en MemoryRouter: færre bevægelige dele, ingen router-state i spil.
vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }));
vi.mock('../hooks/useCategories', () => ({
  useCategories: () => ({ categories: [], loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock('../hooks/useSubcategories', () => ({
  useAllSubcategories: () => ({ subcategories: [] }),
}));
vi.mock('../hooks/useNotifications', () => ({
  useNotifications: () => ({ showError: vi.fn(), showSuccess: vi.fn(), clearMessages: vi.fn() }),
}));
vi.mock('../components/ConfirmDialog/ConfirmDialog', () => ({
  useConfirm: () => vi.fn().mockResolvedValue(true),
}));
// Debounce ud af billedet: søgetekst skal slå igennem synkront i testen.
vi.mock('../hooks/useDebouncedValue', () => ({
  useDebouncedValue: (value) => value,
}));

/** Rækker nok til at fylde en side, så pageren har noget at pages over. */
function rows(count, offset = 0) {
  return Array.from({ length: count }, (_, i) => ({
    id: offset + i + 1,
    date: '2026-06-15',
    description: `Transaktion ${offset + i + 1}`,
    amount: 100,
    type: 'expense',
    category_name: 'Mad',
  }));
}

/** Seneste (filters, page) useTransactions blev kaldt med. */
function lastCall() {
  return useTransactions.mock.calls[useTransactions.mock.calls.length - 1];
}

function mockList({ transactions = rows(PAGE_SIZE), totalCount = 93, isPaging = false } = {}) {
  const api = {
    transactions,
    totalCount,
    isPaging,
    loading: false,
    error: null,
    create: vi.fn().mockResolvedValue({}),
    update: vi.fn().mockResolvedValue({}),
    remove: vi.fn().mockResolvedValue(undefined),
    uploadCsv: vi.fn().mockResolvedValue({ message: 'OK' }),
  };
  // Implementation frem for returnValue: siden kalder hook'et hver render, og
  // vi vil se sidetallet i argumenterne.
  useTransactions.mockImplementation(() => api);
  return api;
}

function mockSearch({ isSearchActive = false, results = [], totalCount = 0 } = {}) {
  useTransactionSearch.mockReturnValue({
    isSearchActive,
    results,
    totalCount,
    loading: false,
    error: null,
  });
}

function renderPage() {
  return render(<TransactionsPage />);
}

const naeste = () => screen.getByRole('button', { name: 'Næste side' });
const forrige = () => screen.getByRole('button', { name: 'Forrige side' });

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mockList();
  mockSearch();
});

describe('TransactionsPage — paginering', () => {
  it('starter på side 1', () => {
    renderPage();

    expect(lastCall()[1]).toBe(1);
    expect(screen.getByText('Viser 1–50 af 93 transaktioner')).toBeInTheDocument();
  });

  it('henter næste side når Næste klikkes', async () => {
    renderPage();

    fireEvent.click(naeste());

    await waitFor(() => expect(lastCall()[1]).toBe(2));
  });

  it('går tilbage igen med Forrige', async () => {
    renderPage();

    fireEvent.click(naeste());
    await waitFor(() => expect(lastCall()[1]).toBe(2));
    fireEvent.click(forrige());

    await waitFor(() => expect(lastCall()[1]).toBe(1));
  });

  it('dæmper og aria-busy-markerer tabellen mens en ny side hentes', () => {
    mockList({ isPaging: true });
    renderPage();

    const results = document.querySelector('.transactions-results');
    expect(results).toHaveClass('is-stale');
    expect(results).toHaveAttribute('aria-busy', 'true');
  });

  it('dæmper ikke når intet sideskift er undervejs', () => {
    renderPage();

    const results = document.querySelector('.transactions-results');
    expect(results).not.toHaveClass('is-stale');
    expect(results).toHaveAttribute('aria-busy', 'false');
  });
});

describe('TransactionsPage — sidenulstilling', () => {
  it('nulstiller til side 1 når datofiltret ændres', async () => {
    renderPage();
    fireEvent.click(naeste());
    await waitFor(() => expect(lastCall()[1]).toBe(2));

    fireEvent.change(screen.getByLabelText(/fra dato/i), { target: { value: '2026-05-01' } });

    await waitFor(() => expect(lastCall()[1]).toBe(1));
  });

  it('nulstiller til side 1 når der søges', async () => {
    renderPage();
    fireEvent.click(naeste());
    await waitFor(() => expect(lastCall()[1]).toBe(2));

    mockSearch({ isSearchActive: true, results: rows(3), totalCount: 3 });
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'netto' } });

    await waitFor(() => expect(lastCall()[1]).toBe(1));
  });

  // Det er hele grunden til set-state-under-render frem for useEffect: med en
  // effekt ville der ligge mindst én render — og dermed ét request — med de nye
  // filtre og det gamle sidetal.
  it('sender ALDRIG et request med nye filtre og gammelt sidetal', async () => {
    renderPage();
    fireEvent.click(naeste());
    await waitFor(() => expect(lastCall()[1]).toBe(2));

    fireEvent.change(screen.getByLabelText(/fra dato/i), { target: { value: '2026-05-01' } });
    await waitFor(() => expect(lastCall()[1]).toBe(1));

    const offending = useTransactions.mock.calls.filter(
      ([filters, page]) => filters.startDate === '2026-05-01' && page !== 1,
    );
    expect(offending).toEqual([]);
  });
});

describe('TransactionsPage — clamp mod krympende total', () => {
  // Vigtigt at totalen krymper UDEN at filtrene røres: et filterskift ville
  // nulstille siden via resultsKey, og testen ville være grøn uden at clampen
  // fandtes. Her er clampen den eneste mekanisme der kan flytte os.
  it('flytter til sidste side når totalen falder under det aktuelle offset', async () => {
    const { rerender } = renderPage();
    fireEvent.click(naeste());
    await waitFor(() => expect(lastCall()[1]).toBe(2));

    // Rækkerne på side 2 er slettet: totalen passer nu på én side.
    mockList({ transactions: rows(12), totalCount: 12 });
    rerender(<TransactionsPage />);

    await waitFor(() => expect(lastCall()[1]).toBe(1));
    expect(screen.getByText('Viser 1–12 af 12 transaktioner')).toBeInTheDocument();
  });

  // Konvergens i ét skridt: fra side 5 til en total der kun rummer 2 sider skal
  // vi ikke igennem 4, 3 — pageCountOf giver svaret direkte.
  it('konvergerer i ét skridt fra en side langt over den nye sidste', async () => {
    mockList({ totalCount: 500 });
    const { rerender } = renderPage();
    fireEvent.click(naeste());
    fireEvent.click(naeste());
    fireEvent.click(naeste());
    fireEvent.click(naeste());
    await waitFor(() => expect(lastCall()[1]).toBe(5));

    mockList({ transactions: rows(PAGE_SIZE), totalCount: 93 });
    rerender(<TransactionsPage />);

    await waitFor(() => expect(lastCall()[1]).toBe(2));
    const pagesRequestedAfterShrink = useTransactions.mock.calls
      .slice(useTransactions.mock.calls.findIndex(([, p]) => p === 5))
      .map(([, p]) => p);
    expect(new Set(pagesRequestedAfterShrink)).toEqual(new Set([5, 2]));
  });

  it('clamper ikke før serveren har oplyst en total', () => {
    mockList({ transactions: [], totalCount: null });
    renderPage();

    expect(lastCall()[1]).toBe(1);
    expect(screen.queryByRole('button', { name: 'Næste side' })).not.toBeInTheDocument();
  });
});

describe('TransactionsPage — tomtilstanden kan ikke lyve', () => {
  it('viser ingen pager når perioden er tom', () => {
    mockList({ transactions: [], totalCount: 0 });
    renderPage();

    expect(screen.queryByRole('navigation', { name: 'Sidenavigation' })).not.toBeInTheDocument();
    expect(screen.getByText('Ingen transaktioner fundet for de valgte filtre.')).toBeInTheDocument();
  });

  it('en tom søgning taler om søgeordet, ikke om filtre, og tilbyder ikke "din første transaktion"', async () => {
    mockSearch({ isSearchActive: true, results: [], totalCount: 0 });
    renderPage();
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'xyzzy' } });

    expect(screen.getByText('Ingen transaktioner matcher “xyzzy”.')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Tilføj din første transaktion' }),
    ).not.toBeInTheDocument();
  });

  it('beholder tomtilstandens CTA på den ufiltrerede liste', () => {
    mockList({ transactions: [], totalCount: 0 });
    renderPage();

    expect(
      screen.getByRole('button', { name: 'Tilføj din første transaktion' }),
    ).toBeInTheDocument();
  });
});

describe('TransactionsPage — søgning (endnu ikke pageable)', () => {
  it('viser ingen pager over søgeresultater, så ingen knap lover noget den ikke kan', async () => {
    mockSearch({ isSearchActive: true, results: rows(50), totalCount: 400 });
    renderPage();
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'netto' } });

    expect(screen.queryByRole('navigation', { name: 'Sidenavigation' })).not.toBeInTheDocument();
  });
});
