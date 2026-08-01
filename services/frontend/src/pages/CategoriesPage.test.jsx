import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CategoriesPage from './CategoriesPage';
import { usePeriodOverview } from '../hooks/usePeriodOverview';

vi.mock('../hooks/useCategories', () => ({
  useCategories: () => ({
    categories: [
      { id: 2, name: 'Transport', type: 'expense' },
      { id: 7, name: 'Indkomst', type: 'income' },
    ],
  }),
}));

vi.mock('../hooks/usePeriodOverview', () => ({
  usePeriodOverview: vi.fn(),
}));

vi.mock('../components/CategoryFilterPanel/CategoryFilterPanel', () => ({
  default: ({ selectedMonth, selectedYear, selectedCategoryIds }) => (
    <div data-testid="filter-state">
      {selectedMonth}/{selectedYear}/{selectedCategoryIds.join(',') || 'all'}
    </div>
  ),
}));

vi.mock('../components/CategorySpendingOverview/CategorySpendingOverview', () => ({
  default: ({ selectedCategoryIds }) => (
    <div data-testid="overview-filter">{selectedCategoryIds.join(',') || 'all'}</div>
  ),
}));

function renderPage(url) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <CategoriesPage />
    </MemoryRouter>,
  );
}

describe('CategoriesPage URL period and category state', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('account_id', '1');
    usePeriodOverview.mockReturnValue({
      overview: {
        startDate: '2026-07-26',
        endDate: '2026-08-25',
        expensesByCategory: [],
      },
      budgetSummary: { month: 8, year: 2026, items: [] },
      loading: false,
      error: null,
    });
  });

  it('opens the linked budget month and expense category', () => {
    renderPage('/categories?month=8&year=2026&category=2');

    expect(usePeriodOverview).toHaveBeenCalledWith({ month: 8, year: 2026, enabled: true });
    expect(screen.getByTestId('filter-state')).toHaveTextContent('08/2026/2');
    expect(screen.getByTestId('overview-filter')).toHaveTextContent('2');
    expect(screen.getByText(/26\.07\.2026.*25\.08\.2026/)).toBeInTheDocument();
  });

  it('ignores a category that is not an expense category', () => {
    renderPage('/categories?month=8&year=2026&category=7');

    expect(screen.getByTestId('filter-state')).toHaveTextContent('08/2026/all');
    expect(screen.getByTestId('overview-filter')).toHaveTextContent('all');
  });
});
