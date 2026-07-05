import { useMemo, useState } from 'react';
import CategoryBarChart from '../../Charts/CategoryBarChart';
import CategoryDrilldown from '../CategoryDrilldown/CategoryDrilldown';
import { formatAmount } from '../../lib/formatters';
import { CHART_COLORS as COLORS } from '../../lib/chartColors';
import './CategorySpendingOverview.css';

// Filter-sentinel for 'Ukategoriseret' (categoryId er null i data).
export const UNCATEGORIZED_FILTER_ID = 'uncategorized';

function CategorySpendingOverview({
  expensesByCategory,
  budgetSummary,
  selectedCategoryIds,
  loading,
}) {
  const [drilldownKey, setDrilldownKey] = useState(null);

  // Gateway'en leverer allerede id-baserede buckets — ingen navn→id
  // reverse-mapping længere.
  const categoryData = useMemo(() => {
    if (!expensesByCategory?.length) return [];
    return expensesByCategory
      .map((entry) => ({
        categoryId: entry.categoryId,
        filterId: entry.categoryId ?? UNCATEGORIZED_FILTER_ID,
        name: entry.categoryName,
        value: Math.abs(Number(entry.amount)),
        subcategories: (entry.subcategories ?? []).map((sub) => ({
          id: sub.subcategoryId,
          name: sub.subcategoryName,
          value: Math.abs(Number(sub.amount)),
        })),
      }))
      .filter((item) => item.value > 0)
      .filter((item) => {
        if (selectedCategoryIds.length === 0) return true;
        return selectedCategoryIds.includes(item.filterId);
      })
      .sort((a, b) => b.value - a.value);
  }, [expensesByCategory, selectedCategoryIds]);

  const totalExpenses = useMemo(
    () => categoryData.reduce((sum, item) => sum + item.value, 0),
    [categoryData],
  );

  const categoryDataWithMeta = useMemo(() => {
    if (totalExpenses === 0) return [];
    return categoryData.map((item, index) => ({
      ...item,
      percentage: ((item.value / totalExpenses) * 100).toFixed(1),
      color: COLORS[index % COLORS.length],
    }));
  }, [categoryData, totalExpenses]);

  const drilldownCategory = useMemo(() => {
    if (drilldownKey == null) return null;
    return (
      categoryDataWithMeta.find((c) => c.filterId === drilldownKey) ?? null
    );
  }, [categoryDataWithMeta, drilldownKey]);

  const budgetItems = useMemo(() => {
    if (!budgetSummary?.items) return [];
    return budgetSummary.items
      .filter((item) => {
        if (selectedCategoryIds.length === 0) return true;
        return selectedCategoryIds.includes(item.categoryId);
      })
      .filter((item) => item.budgetAmount > 0 || item.spentAmount > 0);
  }, [budgetSummary, selectedCategoryIds]);

  const stats = useMemo(() => {
    const totalBudget = budgetItems.reduce((sum, i) => sum + (i.budgetAmount || 0), 0);
    const budgetedSpent = budgetItems
      .filter((i) => i.budgetAmount > 0)
      .reduce((sum, i) => sum + (i.spentAmount || 0), 0);
    const overBudgetCount = budgetItems.filter((i) => i.remainingAmount < 0).length;
    const withinBudgetCount = budgetItems.filter(
      (i) => i.budgetAmount > 0 && i.remainingAmount >= 0,
    ).length;

    return {
      totalExpenses,
      totalBudget,
      budgetedSpent,
      overBudgetCount,
      withinBudgetCount,
      categoryCount: categoryData.length,
    };
  }, [totalExpenses, budgetItems, categoryData.length]);

  if (loading) {
    return (
      <div className="spending-overview loading-state">
        <div className="loading-spinner" />
        <p>Indlæser kategori-overblik...</p>
      </div>
    );
  }

  if (categoryData.length === 0) {
    return (
      <div className="spending-overview empty-state">
        <h3>Ingen udgifter fundet</h3>
        <p>Der er ingen transaktioner i den valgte periode og filtrering.</p>
      </div>
    );
  }

  return (
    <div className="spending-overview">
      {/* Summary stats */}
      <div className="spending-stats-grid">
        <div className="spending-stat-card">
          <div className="spending-stat-value expense">
            {formatAmount(stats.totalExpenses)}
          </div>
          <div className="spending-stat-label">Samlet forbrug</div>
        </div>
        <div className="spending-stat-card">
          <div className="spending-stat-value">{stats.categoryCount}</div>
          <div className="spending-stat-label">Kategorier</div>
        </div>
        {stats.totalBudget > 0 && (
          <>
            <div className="spending-stat-card">
              <div className="spending-stat-value">
                {formatAmount(stats.totalBudget)}
              </div>
              <div className="spending-stat-label">Samlet budget</div>
            </div>
            <div className="spending-stat-card">
              <div className={`spending-stat-value ${stats.overBudgetCount > 0 ? 'over-budget' : 'within-budget'}`}>
                {stats.withinBudgetCount} / {stats.withinBudgetCount + stats.overBudgetCount}
              </div>
              <div className="spending-stat-label">Budgetter overholdt</div>
            </div>
          </>
        )}
      </div>

      {/* Bar chart: spending vs budget — eller subkategori-drilldown */}
      <div className="spending-chart-full">
        {drilldownCategory ? (
          <CategoryDrilldown
            category={drilldownCategory}
            totalExpenses={totalExpenses}
            onBack={() => setDrilldownKey(null)}
            formatAmount={formatAmount}
          />
        ) : (
          <>
            <h3>Forbrug vs. budget pr. kategori</h3>
            <div className="chart-legend">
              <span className="legend-item">
                <span className="legend-swatch" style={{ backgroundColor: '#0088FE' }} />
                Forbrug
              </span>
              <span className="legend-item">
                <span className="legend-swatch budget" />
                Budget
              </span>
            </div>
            <CategoryBarChart
              categoryData={categoryDataWithMeta}
              budgetItems={budgetItems}
            />
            <div className="spending-drilldown-hint">
              {categoryDataWithMeta.map((item) => (
                <button
                  key={item.filterId}
                  type="button"
                  className="drilldown-chip"
                  style={{ borderColor: item.color }}
                  onClick={() => setDrilldownKey(item.filterId)}
                  title={`Se underkategorier for ${item.name}`}
                >
                  <span className="drilldown-chip-dot" style={{ backgroundColor: item.color }} />
                  {item.name}
                </button>
              ))}
            </div>
            <div className="spending-total-row">
              <strong>Samlet forbrug: {formatAmount(totalExpenses)}</strong>
            </div>
          </>
        )}
      </div>

      {/* Budget compliance section */}
      {budgetItems.length > 0 && !drilldownCategory && (
        <div className="budget-compliance-section">
          <h3>Budget-overholdelse</h3>
          <div className="budget-compliance-list">
            {budgetItems
              .filter((item) => item.budgetAmount > 0)
              .sort((a, b) => (b.percentageUsed || 0) - (a.percentageUsed || 0))
              .map((item) => (
                <BudgetComplianceRow key={item.categoryId} item={item} />
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BudgetComplianceRow({ item }) {
  const pct = item.percentageUsed || 0;
  const isOver = item.remainingAmount < 0;
  const isClose = pct >= 80 && !isOver;

  let statusClass = 'ok';
  let statusText = 'Inden for budget';
  if (isOver) {
    statusClass = 'over';
    statusText = 'Overskredet';
  } else if (isClose) {
    statusClass = 'warning';
    statusText = 'Tæt på grænsen';
  }

  return (
    <div className={`compliance-row ${statusClass}`}>
      <div className="compliance-info">
        <span className="compliance-name">{item.categoryName}</span>
        <span className={`compliance-status ${statusClass}`}>{statusText}</span>
      </div>
      <div className="compliance-bar-wrapper">
        <div className="compliance-bar">
          <div
            className={`compliance-fill ${statusClass}`}
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
      </div>
      <div className="compliance-amounts">
        <span className="compliance-spent">{formatAmount(item.spentAmount)}</span>
        <span className="compliance-divider">/</span>
        <span className="compliance-budget">{formatAmount(item.budgetAmount)}</span>
        <span className={`compliance-remaining ${isOver ? 'over' : ''}`}>
          ({isOver ? '' : '+'}{formatAmount(item.remainingAmount)})
        </span>
      </div>
    </div>
  );
}

export default CategorySpendingOverview;
