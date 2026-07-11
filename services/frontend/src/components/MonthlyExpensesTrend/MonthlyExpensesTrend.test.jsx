import { cloneElement } from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MonthlyExpensesTrend from './MonthlyExpensesTrend';

// Recharts' ResponsiveContainer bruger ResizeObserver og måler DOM'en
// (0×0 i jsdom) — giv barnet en fast størrelse i stedet.
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    ResponsiveContainer: ({ children }) => cloneElement(children, { width: 800, height: 280 }),
  };
});

const cashflow = [
  { month: '2026-05', totalIncome: 18624.2, totalExpenses: 44367.47, net: -25743.27 },
  { month: '2026-06', totalIncome: 4905.76, totalExpenses: 7284.83, net: -2379.07 },
  { month: '2026-07', totalIncome: 0, totalExpenses: 0, net: 0 },
];

describe('MonthlyExpensesTrend', () => {
  it('renders both series in the legend', () => {
    render(<MonthlyExpensesTrend data={cashflow} averageMonthlyExpenses={6000} />);

    expect(screen.getByText('Indtægter og udgifter over tid')).toBeInTheDocument();
    expect(screen.getByText('Indtægter')).toBeInTheDocument();
    expect(screen.getByText('Udgifter')).toBeInTheDocument();
  });

  it('renders the average expenses reference line label', () => {
    render(<MonthlyExpensesTrend data={cashflow} averageMonthlyExpenses={6000} />);
    expect(screen.getByText('Gns. udgifter')).toBeInTheDocument();
  });

  it('omits the reference line when average is missing', () => {
    render(<MonthlyExpensesTrend data={cashflow} averageMonthlyExpenses={null} />);
    expect(screen.queryByText('Gns. udgifter')).not.toBeInTheDocument();
  });

  it('renders empty state when the whole window has no activity', () => {
    render(
      <MonthlyExpensesTrend
        data={[{ month: '2026-07', totalIncome: 0, totalExpenses: 0, net: 0 }]}
        averageMonthlyExpenses={0}
      />,
    );
    expect(screen.getByText('Ingen data til trend endnu.')).toBeInTheDocument();
  });

  it('renders empty state when data is missing', () => {
    render(<MonthlyExpensesTrend data={undefined} />);
    expect(screen.getByText('Ingen data til trend endnu.')).toBeInTheDocument();
  });
});
