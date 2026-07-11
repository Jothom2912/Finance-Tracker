import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import MonthComparison from './MonthComparison';
import { formatAmount } from '../../lib/formatters';

const comparison = {
  previousMonth: 5,
  previousYear: 2026,
  totalCurrent: 7284.83,
  totalPrevious: 44367.47,
  deltas: [
    {
      categoryId: 10,
      categoryName: 'Mad & drikke',
      currentAmount: 325,
      previousAmount: 100,
      changeAmount: 225,
      changePercent: 225.0,
    },
    {
      categoryId: 11,
      categoryName: 'Transport',
      currentAmount: 50,
      previousAmount: 200,
      changeAmount: -150,
      changePercent: -75.0,
    },
    {
      categoryId: null,
      categoryName: 'Ukategoriseret',
      currentAmount: 50,
      previousAmount: 0,
      changeAmount: 50,
      changePercent: null,
    },
  ],
};

describe('MonthComparison', () => {
  it('renders category names with signed change amounts', () => {
    render(<MonthComparison comparison={comparison} formatAmount={formatAmount} />);

    expect(screen.getByText('Mad & drikke')).toBeInTheDocument();
    expect(screen.getByText('Transport')).toBeInTheDocument();
    // Stigende forbrug markeres som stigning (rød konvention fra TrendBadge).
    expect(screen.getByLabelText('Stigning')).toBeInTheDocument();
    expect(screen.getByLabelText('Fald')).toBeInTheDocument();
  });

  it('shows "Ny" badge when the category had no previous spending', () => {
    render(<MonthComparison comparison={comparison} formatAmount={formatAmount} />);
    expect(screen.getByText('Ny')).toBeInTheDocument();
  });

  it('shows the from → to detail with percent', () => {
    render(<MonthComparison comparison={comparison} formatAmount={formatAmount} />);
    expect(screen.getByText(/\(\+225%\)/)).toBeInTheDocument();
    expect(screen.getByText(/\(-75%\)/)).toBeInTheDocument();
  });

  it('renders empty state when there is nothing to compare against', () => {
    render(
      <MonthComparison
        comparison={{ ...comparison, totalPrevious: 0 }}
        formatAmount={formatAmount}
      />,
    );
    expect(screen.getByText('Ingen data at sammenligne med endnu.')).toBeInTheDocument();
  });

  it('renders empty state when comparison is missing', () => {
    render(<MonthComparison comparison={null} formatAmount={formatAmount} />);
    expect(screen.getByText('Ingen data at sammenligne med endnu.')).toBeInTheDocument();
  });
});
