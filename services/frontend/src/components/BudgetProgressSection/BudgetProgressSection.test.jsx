
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BudgetProgressSection from './BudgetProgressSection';

const mockBudgetSummary = {
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

describe('BudgetProgressSection', () => {
  it('renders budget totals', () => {
    render(<BudgetProgressSection budgetSummary={mockBudgetSummary} />);

    expect(screen.getByText('Budget status')).toBeInTheDocument();
    expect(screen.getByText(/8.000,00 kr\./)).toBeInTheDocument();
    expect(screen.getByText(/5.500,00 kr\./)).toBeInTheDocument();
    expect(screen.getByText(/% brugt/)).toBeInTheDocument();
  });

  it('renders progress bars for categories with budget', () => {
    render(<BudgetProgressSection budgetSummary={mockBudgetSummary} />);

    expect(screen.getByText('Mad')).toBeInTheDocument();
    expect(screen.getByText('Transport')).toBeInTheDocument();
  });

  it('shows over-budget warning', () => {
    render(<BudgetProgressSection budgetSummary={mockBudgetSummary} />);

    expect(screen.getByText(/1 kategori over budget/)).toBeInTheDocument();
  });

  it('shows remaining text for under-budget categories', () => {
    render(<BudgetProgressSection budgetSummary={mockBudgetSummary} />);

    expect(screen.getByText(/tilbage/)).toBeInTheDocument();
  });

  it('shows over-budget text for exceeded categories', () => {
    render(<BudgetProgressSection budgetSummary={mockBudgetSummary} />);

    const matches = screen.getAllByText(/over budget/);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders empty state when no budget data', () => {
    render(<BudgetProgressSection budgetSummary={null} />);

    expect(screen.getByText(/Intet budget opsat/)).toBeInTheDocument();
  });

  it('renders empty state when items array is empty', () => {
    render(
      <BudgetProgressSection
        budgetSummary={{ ...mockBudgetSummary, items: [] }}
      />,
    );

    expect(screen.getByText(/Intet budget opsat/)).toBeInTheDocument();
  });
});
