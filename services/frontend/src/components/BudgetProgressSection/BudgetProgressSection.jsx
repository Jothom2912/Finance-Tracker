import { useState } from 'react';
import { Link } from 'react-router-dom';
import { formatAmount } from '../../lib/formatters';
import './BudgetProgressSection.css';

const COLLAPSED_COUNT = 5;

function BudgetProgressBar({ item, compact }) {
  const pct = Math.min(item.percentageUsed, 100);
  const overBudget = item.remainingAmount < 0;

  if (compact) {
    return (
      <div className="budget-compact-row">
        <span className="budget-compact-name">{item.categoryName}</span>
        <div className="budget-compact-bar-wrap">
          <div className="budget-progress-track compact">
            <div
              className={`budget-progress-fill ${overBudget ? 'over-budget' : ''}`}
              style={{ width: `${Math.min(pct, 100)}%` }}
            />
          </div>
        </div>
        <span className="budget-compact-amount">
          {formatAmount(item.spentAmount)} / {formatAmount(item.budgetAmount)}
        </span>
      </div>
    );
  }

  return (
    <div className="budget-progress-item">
      <div className="budget-progress-header">
        <span className="budget-category-name">{item.categoryName}</span>
        <span className="budget-amounts">
          {formatAmount(item.spentAmount)} / {formatAmount(item.budgetAmount)}
        </span>
      </div>
      <div className="budget-progress-track">
        <div
          className={`budget-progress-fill ${overBudget ? 'over-budget' : ''}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <div className="budget-progress-footer">
        <span className={`budget-remaining ${overBudget ? 'over-budget-text' : ''}`}>
          {overBudget
            ? `${formatAmount(Math.abs(item.remainingAmount))} over budget`
            : `${formatAmount(item.remainingAmount)} tilbage`}
        </span>
        <span className="budget-percentage">{item.percentageUsed.toFixed(0)}%</span>
      </div>
    </div>
  );
}

function BudgetProgressSection({ budgetSummary }) {
  const [expanded, setExpanded] = useState(false);

  if (!budgetSummary || !budgetSummary.items?.length) {
    return (
      <div className="budget-progress-section">
        <h3>Budget status</h3>
        <p className="no-data-message">Intet budget opsat for denne måned.</p>
      </div>
    );
  }

  const itemsWithBudget = budgetSummary.items.filter((i) => i.budgetAmount > 0);
  const sorted = [...itemsWithBudget].sort(
    (a, b) => b.percentageUsed - a.percentageUsed
  );
  const overBudgetItems = sorted.filter((item) => item.remainingAmount < 0);
  const withinBudgetItems = sorted.filter((item) => item.remainingAmount >= 0);
  const collapsedWithinCount = Math.max(0, COLLAPSED_COUNT - overBudgetItems.length);
  const visible = expanded
    ? sorted
    : [...overBudgetItems, ...withinBudgetItems.slice(0, collapsedWithinCount)];
  const hidden = withinBudgetItems.slice(collapsedWithinCount);
  const hasMore = hidden.length > 0;

  const usedPercent = budgetSummary.totalBudget > 0
    ? Math.round((budgetSummary.totalSpent / budgetSummary.totalBudget) * 100)
    : 0;

  return (
    <div className="budget-progress-section">
      <h3>Budget status</h3>

      <div className="budget-overview-bar">
        <div className="budget-overview-header">
          <span className="budget-overview-spent">
            {formatAmount(budgetSummary.totalSpent)} af {formatAmount(budgetSummary.totalBudget)}
          </span>
          <span className="budget-overview-pct">{usedPercent}% brugt</span>
        </div>
        <div className="budget-progress-track overview">
          <div
            className={`budget-progress-fill ${usedPercent > 100 ? 'over-budget' : ''}`}
            style={{ width: `${Math.min(usedPercent, 100)}%` }}
          />
        </div>
        <span className="budget-overview-remaining">
          {formatAmount(budgetSummary.totalRemaining)} tilbage
        </span>
      </div>

      {overBudgetItems.length > 0 && (
        <div className="budget-warning">
          <strong>
            {overBudgetItems.length} kategori{overBudgetItems.length > 1 ? 'er' : ''} over budget
          </strong>
          <ul className="budget-warning-list">
            {overBudgetItems.map((item) => (
              <li key={item.categoryId}>
                <Link
                  to={`/categories?month=${budgetSummary.month}&year=${budgetSummary.year}&category=${item.categoryId}`}
                >
                  {item.categoryName} — {formatAmount(Math.abs(item.remainingAmount))} over budget
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="budget-progress-list">
        {visible.map((item) => (
          <BudgetProgressBar key={item.categoryId} item={item} compact />
        ))}
      </div>

      {hasMore && (
        <button
          className="budget-toggle-btn"
          onClick={() => setExpanded((prev) => !prev)}
        >
          {expanded
            ? 'Vis færre'
            : `Vis ${hidden.length} flere kategorier`}
        </button>
      )}
    </div>
  );
}

export default BudgetProgressSection;
