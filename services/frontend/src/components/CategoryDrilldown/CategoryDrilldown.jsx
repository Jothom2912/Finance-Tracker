import './CategoryDrilldown.css';

/**
 * Master/detail-panel for én kategoris subkategori-fordeling.
 * Vises i stedet for pie+liste når brugeren klikker på en kategori.
 *
 * @param {object} category - {id, name, value, percentage, color, subcategories: [{id, name, value}]}
 * @param {number} totalExpenses - periodens samlede udgifter (til andel-af-total)
 * @param {function} onBack - luk drill-down
 * @param {function} formatAmount
 */
function CategoryDrilldown({ category, totalExpenses, onBack, formatAmount }) {
  if (!category) return null;

  const subcategories = [...(category.subcategories ?? [])].sort((a, b) => b.value - a.value);
  const maxValue = subcategories.length ? subcategories[0].value : 0;
  const shareOfTotal = totalExpenses
    ? ((category.value / Math.abs(totalExpenses)) * 100).toFixed(1)
    : null;

  return (
    <div className="category-drilldown">
      <button type="button" className="drilldown-back" onClick={onBack}>
        ‹ Tilbage til alle kategorier
      </button>

      <div className="drilldown-header">
        <span
          className="drilldown-color-dot"
          style={{ backgroundColor: category.color }}
        />
        <h4 className="drilldown-title">{category.name}</h4>
        <span className="drilldown-total">{formatAmount(category.value)}</span>
        {shareOfTotal && (
          <span className="drilldown-share">({shareOfTotal}% af udgifter)</span>
        )}
      </div>

      {subcategories.length === 0 ? (
        <p className="drilldown-empty">Ingen underkategori-data for denne kategori.</p>
      ) : (
        <ul className="drilldown-list">
          {subcategories.map((sub) => {
            const pctOfCategory = category.value
              ? ((sub.value / category.value) * 100).toFixed(1)
              : '0.0';
            const barWidth = maxValue ? (sub.value / maxValue) * 100 : 0;
            return (
              <li key={sub.id ?? 'none'} className="drilldown-item">
                <div className="drilldown-item-header">
                  <span className="drilldown-item-name">{sub.name}</span>
                  <span className="drilldown-item-amount">
                    {formatAmount(sub.value)}
                    <span className="drilldown-item-pct"> ({pctOfCategory}%)</span>
                  </span>
                </div>
                <div className="drilldown-bar-track">
                  <div
                    className="drilldown-bar-fill"
                    style={{ width: `${barWidth}%`, backgroundColor: category.color }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default CategoryDrilldown;
