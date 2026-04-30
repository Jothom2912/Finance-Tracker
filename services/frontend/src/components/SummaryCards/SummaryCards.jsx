
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import './SummaryCards.css';

function TrendBadge({ changePercent, invertColor }) {
  if (changePercent == null) return null;

  const isUp = changePercent > 0;
  const isDown = changePercent < 0;
  const isFlat = changePercent === 0;

  let colorClass;
  if (isFlat) {
    colorClass = 'trend-neutral';
  } else if (invertColor) {
    colorClass = isUp ? 'trend-negative' : 'trend-positive';
  } else {
    colorClass = isUp ? 'trend-positive' : 'trend-negative';
  }

  const IconComp = isUp ? TrendingUp : isDown ? TrendingDown : Minus;
  const trendLabel = isUp ? 'Stigning' : isDown ? 'Fald' : 'Uændret';
  const label = isFlat ? '0%' : `${Math.abs(changePercent)}%`;

  return (
    <span className={`trend-badge ${colorClass}`} title="vs. forrige måned">
      <IconComp className="trend-arrow" aria-label={trendLabel} size={14} />
      <span className="trend-value">{label}</span>
    </span>
  );
}

function SummaryCards({ totalIncome, totalExpenses, netChange, currentBalance, trend, formatAmount }) {
  return (
    <div className="dashboard-summary-cards">
      <div className="summary-card income-card">
        <h3>Samlet indkomst</h3>
        <p className="amount income-amount">{formatAmount(totalIncome)}</p>
        <TrendBadge changePercent={trend?.incomeChangePercent} invertColor={false} />
      </div>
      <div className="summary-card expenses-card">
        <h3>Samlede udgifter</h3>
        <p className="amount expenses-amount">{formatAmount(totalExpenses)}</p>
        <TrendBadge changePercent={trend?.expenseChangePercent} invertColor={true} />
      </div>
      <div className="summary-card net-change-card">
        <h3>Nettoændring</h3>
        <p className={`amount net-change-amount ${netChange >= 0 ? 'positive' : 'negative'}`}>
          {formatAmount(netChange)}
        </p>
      </div>
      <div className="summary-card balance-card">
        <h3>Nuværende saldo</h3>
        <p className={`amount balance-amount ${currentBalance >= 0 ? 'positive' : 'negative'}`}>
          {formatAmount(currentBalance)}
        </p>
      </div>
    </div>
  );
}

export default SummaryCards;
