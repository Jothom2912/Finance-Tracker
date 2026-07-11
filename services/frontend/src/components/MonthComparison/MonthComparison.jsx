import { TrendingUp, TrendingDown } from 'lucide-react';
import './MonthComparison.css';

// Samme inversionskonvention som TrendBadge: stigende forbrug = rød (op),
// faldende forbrug = grøn (ned). Identitet bæres af ikon + tekst, ikke
// farve alene.
function DeltaBadge({ delta, formatAmount }) {
  if (delta.changePercent == null) {
    return <span className="comparison-badge comparison-new">Ny</span>;
  }

  const isUp = delta.changeAmount > 0;
  const IconComp = isUp ? TrendingUp : TrendingDown;
  const label = isUp ? 'Stigning' : 'Fald';

  return (
    <span className={`comparison-badge ${isUp ? 'comparison-up' : 'comparison-down'}`}>
      <IconComp size={13} aria-label={label} />
      {formatAmount(Math.abs(delta.changeAmount))}
    </span>
  );
}

function MonthComparison({ comparison, formatAmount }) {
  const deltas = comparison?.deltas ?? [];

  return (
    <div className="month-comparison-section">
      <div className="month-comparison-header">
        <h3>Største ændringer siden sidste måned</h3>
      </div>

      {deltas.length === 0 || comparison?.totalPrevious === 0 ? (
        <div className="month-comparison-empty">
          <p>Ingen data at sammenligne med endnu.</p>
        </div>
      ) : (
        <ul className="month-comparison-list">
          {deltas.map((delta) => (
            <li key={delta.categoryId ?? 'uncategorized'} className="month-comparison-item">
              <div className="comparison-item-main">
                <span className="comparison-category">{delta.categoryName}</span>
                <DeltaBadge delta={delta} formatAmount={formatAmount} />
              </div>
              <div className="comparison-item-detail">
                {formatAmount(delta.previousAmount)} → {formatAmount(delta.currentAmount)}
                {delta.changePercent != null && (
                  <span className="comparison-percent">
                    {' '}({delta.changePercent > 0 ? '+' : ''}{delta.changePercent}%)
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default MonthComparison;
