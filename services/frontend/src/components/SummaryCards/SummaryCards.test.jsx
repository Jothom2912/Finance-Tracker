
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SummaryCards from './SummaryCards';

const formatAmount = (val) => `${val?.toLocaleString('da-DK')} kr.`;

describe('SummaryCards', () => {
  it('renders all four cards', () => {
    render(
      <SummaryCards
        totalIncome={10000}
        totalExpenses={6000}
        netChange={4000}
        currentBalance={15000}
        formatAmount={formatAmount}
      />,
    );

    expect(screen.getByText('Samlet indkomst')).toBeInTheDocument();
    expect(screen.getByText('Samlede udgifter')).toBeInTheDocument();
    expect(screen.getByText('Nettoændring')).toBeInTheDocument();
    expect(screen.getByText('Nuværende saldo')).toBeInTheDocument();
  });

  it('renders formatted amounts', () => {
    render(
      <SummaryCards
        totalIncome={10000}
        totalExpenses={6000}
        netChange={4000}
        currentBalance={15000}
        formatAmount={formatAmount}
      />,
    );

    expect(screen.getByText('10.000 kr.')).toBeInTheDocument();
  });

  it('applies positive class for positive net change', () => {
    render(
      <SummaryCards
        totalIncome={10000}
        totalExpenses={6000}
        netChange={4000}
        currentBalance={15000}
        formatAmount={formatAmount}
      />,
    );

    const netEl = screen.getByText('4.000 kr.');
    expect(netEl).toHaveClass('positive');
  });

  it('applies negative class for negative net change', () => {
    render(
      <SummaryCards
        totalIncome={3000}
        totalExpenses={6000}
        netChange={-3000}
        currentBalance={-1000}
        formatAmount={formatAmount}
      />,
    );

    const netEl = screen.getByText('-3.000 kr.');
    expect(netEl).toHaveClass('negative');
  });

  it('shows trend badges when trend data is provided', () => {
    render(
      <SummaryCards
        totalIncome={10000}
        totalExpenses={6000}
        netChange={4000}
        currentBalance={15000}
        trend={{
          incomeChangePercent: 12.5,
          expenseChangePercent: -8.3,
        }}
        formatAmount={formatAmount}
      />,
    );

    expect(screen.getByText('12.5%')).toBeInTheDocument();
    expect(screen.getByText('8.3%')).toBeInTheDocument();
  });

  it('shows up arrow for positive income trend', () => {
    render(
      <SummaryCards
        totalIncome={10000}
        totalExpenses={6000}
        netChange={4000}
        currentBalance={15000}
        trend={{ incomeChangePercent: 10, expenseChangePercent: 5 }}
        formatAmount={formatAmount}
      />,
    );

    // Trend direction is communicated via aria-label on the icon, not
    // via the (identical) "10%" text -- so the test matches how screen
    // readers resolve the meaning, not the visual glyph.
    const upIcons = screen.getAllByLabelText('Stigning');
    expect(upIcons.length).toBeGreaterThanOrEqual(1);
  });

  it('shows down arrow for negative trend', () => {
    render(
      <SummaryCards
        totalIncome={10000}
        totalExpenses={6000}
        netChange={4000}
        currentBalance={15000}
        trend={{ incomeChangePercent: -15, expenseChangePercent: -5 }}
        formatAmount={formatAmount}
      />,
    );

    const downIcons = screen.getAllByLabelText('Fald');
    expect(downIcons.length).toBeGreaterThanOrEqual(1);
  });

  it('does not show trend badges when trend is null', () => {
    render(
      <SummaryCards
        totalIncome={10000}
        totalExpenses={6000}
        netChange={4000}
        currentBalance={15000}
        trend={null}
        formatAmount={formatAmount}
      />,
    );

    expect(screen.queryByLabelText('Stigning')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Fald')).not.toBeInTheDocument();
  });

  it('inverts color on expense trend (up = red, down = green)', () => {
    const { container } = render(
      <SummaryCards
        totalIncome={10000}
        totalExpenses={8000}
        netChange={2000}
        currentBalance={15000}
        trend={{ incomeChangePercent: 10, expenseChangePercent: 20 }}
        formatAmount={formatAmount}
      />,
    );

    const badges = container.querySelectorAll('.trend-badge');
    const incomeBadge = badges[0];
    const expenseBadge = badges[1];

    expect(incomeBadge).toHaveClass('trend-positive');
    expect(expenseBadge).toHaveClass('trend-negative');
  });
});
