
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BudgetProgressSection from './BudgetProgressSection';

const mockBudgetSummary = {
  month: 8,
  year: 2026,
  totalBudget: 8000,
  totalSpent: 5500,
  totalRemaining: 2500,
  overBudgetCount: 1,
  items: [
    {
      categoryId: 1,
      categoryName: 'Mad',
      budgetAmount: 4000,
      spentAmount: 3000,
      remainingAmount: 1000,
      percentageUsed: 75,
    },
    {
      categoryId: 2,
      categoryName: 'Transport',
      budgetAmount: 2000,
      spentAmount: 2500,
      remainingAmount: -500,
      percentageUsed: 125,
    },
  ],
};

function renderSection(summary = mockBudgetSummary) {
  return render(
    <MemoryRouter>
      <BudgetProgressSection budgetSummary={summary} />
    </MemoryRouter>,
  );
}

describe('BudgetProgressSection', () => {
  it('renders budget totals', () => {
    renderSection();

    expect(screen.getByText('Budget status')).toBeInTheDocument();
    expect(screen.getByText(/8.000,00 kr\./)).toBeInTheDocument();
    expect(screen.getByText(/5.500,00 kr\./)).toBeInTheDocument();
    expect(screen.getByText(/% brugt/)).toBeInTheDocument();
  });

  it('renders progress bars for categories with budget', () => {
    renderSection();

    expect(screen.getByText('Mad')).toBeInTheDocument();
    expect(screen.getByText('Transport')).toBeInTheDocument();
  });

  it('shows over-budget warning', () => {
    renderSection();

    expect(screen.getByText(/1 kategori over budget/)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /Transport.*500,00.*over budget/ });
    expect(link).toHaveAttribute('href', '/categories?month=8&year=2026&category=2');
  });

  it('shows remaining text for under-budget categories', () => {
    renderSection();

    expect(screen.getByText(/tilbage/)).toBeInTheDocument();
  });

  it('shows over-budget text for exceeded categories', () => {
    renderSection();

    const matches = screen.getAllByText(/over budget/);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders empty state when no budget data', () => {
    renderSection(null);

    expect(screen.getByText(/Intet budget opsat/)).toBeInTheDocument();
  });

  it('renders empty state when items array is empty', () => {
    renderSection({ ...mockBudgetSummary, items: [] });

    expect(screen.getByText(/Intet budget opsat/)).toBeInTheDocument();
  });

  it('does not mark a category with zero remaining as over budget', () => {
    renderSection({
      ...mockBudgetSummary,
      overBudgetCount: 0,
      items: [{
        ...mockBudgetSummary.items[0],
        spentAmount: 4000,
        remainingAmount: 0,
        percentageUsed: 100,
      }],
    });

    expect(screen.queryByText(/kategori over budget/)).not.toBeInTheDocument();
  });
});
