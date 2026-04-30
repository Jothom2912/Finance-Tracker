
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RecentTransactions from './RecentTransactions';

const mockTransactions = [
  {
    id: 1,
    amount: -500,
    description: 'Netto',
    date: '2026-03-04',
    type: 'expense',
  },
  {
    id: 2,
    amount: 10000,
    description: 'Løn',
    date: '2026-03-01',
    type: 'income',
  },
];

function renderWithRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('RecentTransactions', () => {
  it('renders transaction descriptions', () => {
    renderWithRouter(<RecentTransactions transactions={mockTransactions} />);

    expect(screen.getByText('Netto')).toBeInTheDocument();
    expect(screen.getByText('Løn')).toBeInTheDocument();
  });

  it('renders "Se alle" link', () => {
    renderWithRouter(<RecentTransactions transactions={mockTransactions} />);

    expect(screen.getByText('Se alle')).toBeInTheDocument();
  });

  it('applies expense styling for negative amounts', () => {
    renderWithRouter(<RecentTransactions transactions={mockTransactions} />);

    const expenseAmount = screen.getByText((content, element) =>
      element?.classList?.contains('expense') && content.includes('500'),
    );
    expect(expenseAmount).toBeInTheDocument();
  });

  it('applies income styling for positive amounts', () => {
    renderWithRouter(<RecentTransactions transactions={mockTransactions} />);

    const incomeAmount = screen.getByText((content, element) =>
      element?.classList?.contains('income') && content.includes('10'),
    );
    expect(incomeAmount).toBeInTheDocument();
  });

  it('shows fallback for missing description', () => {
    renderWithRouter(
      <RecentTransactions
        transactions={[{ id: 1, amount: -100, description: null, date: '2026-03-01', type: 'expense' }]}
      />,
    );

    expect(screen.getByText('Ingen beskrivelse')).toBeInTheDocument();
  });

  it('renders empty state when no transactions', () => {
    renderWithRouter(<RecentTransactions transactions={[]} />);

    expect(screen.getByText(/Ingen transaktioner endnu/)).toBeInTheDocument();
    expect(screen.getByText(/Tilføj din første/)).toBeInTheDocument();
  });

  it('renders empty state when transactions is null', () => {
    renderWithRouter(<RecentTransactions transactions={null} />);

    expect(screen.getByText(/Ingen transaktioner endnu/)).toBeInTheDocument();
  });
});
