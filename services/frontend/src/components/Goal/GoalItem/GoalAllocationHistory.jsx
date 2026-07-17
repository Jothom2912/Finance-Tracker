import { useAllocationHistory } from '../../../hooks/useGoalAllocations';

/**
 * Udfoldet historik-sektion for ét mål. Rendres først når brugeren folder
 * sektionen ud (lazy fetch via enabled-flaget følger mount).
 */
function GoalAllocationHistory({ goalId, formatAmount, formatDate }) {
  const { history, loading, error } = useAllocationHistory(goalId);

  if (loading) return <div className="allocation-history-empty">Henter historik…</div>;
  if (error) return <div className="allocation-history-empty">{error}</div>;
  if (history.length === 0) {
    return (
      <div className="allocation-history-empty">
        Ingen automatiske opsparinger endnu — de kommer når en budgetmåned
        lukkes med overskud.
      </div>
    );
  }

  return (
    <ul className="allocation-history-list">
      {history.map((entry) => (
        <li key={entry.source_key} className="allocation-history-entry">
          <span className="allocation-amount">+{formatAmount(entry.amount)}</span>
          <span className="allocation-date">{formatDate(entry.applied_at)}</span>
        </li>
      ))}
    </ul>
  );
}

export default GoalAllocationHistory;
