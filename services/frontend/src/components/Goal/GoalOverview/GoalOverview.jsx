import { useEffect, useMemo } from 'react';
import { PiggyBank, Target } from 'lucide-react';
import { useGoals } from '../../../hooks/useGoals';
import { useUnallocatedSurplus } from '../../../hooks/useGoalAllocations';
import MessageDisplay from '../../MessageDisplay';
import GoalItem from '../GoalItem/GoalItem';
import './GoalOverview.css';

function GoalOverview({ setError, setSuccessMessage, onEditGoal }) {
  const { goals, loading, error: localError, setDefault } = useGoals();
  const { total: unallocatedTotal, entries: unallocatedEntries } = useUnallocatedSurplus();
  const hasDefaultGoal = goals.some((goal) => goal.isDefaultSavingsGoal);

  const handleSetDefault = async (goal) => {
    try {
      await setDefault(goal.id, !goal.isDefaultSavingsGoal);
      setSuccessMessage?.(
        goal.isDefaultSavingsGoal
          ? `"${goal.name}" er ikke længere standardmål.`
          : `"${goal.name}" er nu dit standardopsparingsmål — budgetoverskud opspares her.`
      );
    } catch (mutationError) {
      setError?.(mutationError.message || 'Kunne ikke opdatere standardmål.');
    }
  };

  // Løft fetch-fejlen til side-niveau (toast) — den lokale visning
  // nedenfor beholdes, så siden aldrig står tom uden forklaring.
  useEffect(() => {
    if (localError) setError?.(localError);
  }, [localError, setError]);

  const stats = useMemo(() => {
    if (!goals || goals.length === 0) {
      return { total: 0, completed: 0, active: 0, expired: 0, totalTarget: 0, totalCurrent: 0, totalProgress: 0 };
    }

    const completed = goals.filter(g => g.status === 'completed').length;
    const expired = goals.filter(g => g.status === 'expired').length;
    const active = goals.filter(g => g.status === 'active' || g.status === 'paused').length;
    const totalTarget = goals.reduce((sum, g) => sum + (g.targetAmount || 0), 0);
    const totalCurrent = goals.reduce((sum, g) => sum + (g.currentAmount || 0), 0);
    const totalProgress = totalTarget > 0 ? (totalCurrent / totalTarget) * 100 : 0;

    return {
      total: goals.length,
      completed,
      active,
      expired,
      totalTarget,
      totalCurrent,
      totalProgress: Math.min(totalProgress, 100)
    };
  }, [goals]);

  const formatAmount = (amount) => {
    return new Intl.NumberFormat('da-DK', {
      style: 'currency',
      currency: 'DKK',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount || 0);
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Ingen dato';
    const date = new Date(dateString);
    return date.toLocaleDateString('da-DK', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="goal-overview-loading">
        <div className="loading-spinner"></div>
        <p>Henter mål...</p>
      </div>
    );
  }

  if (localError) {
    return (
      <div className="goal-overview-container">
        <MessageDisplay message={localError} type="error" />
      </div>
    );
  }

  return (
    <div className="goal-overview-container">
      <div className="goal-overview-header">
        <h2>Mine Mål</h2>
        {goals.length > 0 && (
          <button
            className="add-goal-button"
            onClick={() => onEditGoal?.(null)}
            title="Opret nyt mål"
          >
            + Tilføj Mål
          </button>
        )}
      </div>

      {goals.length > 0 && (
        <div className="goal-stats">
          <div className="stat-card">
            <div className="stat-label">Samlet Fremskridt</div>
            <div className="stat-value-large">{stats.totalProgress.toFixed(1)}%</div>
            <div className="progress-bar-container">
              <div
                className="progress-bar"
                style={{ width: `${stats.totalProgress}%` }}
              ></div>
            </div>
            <div className="stat-details">
              {formatAmount(stats.totalCurrent)} / {formatAmount(stats.totalTarget)}
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Aktive Mål</div>
            <div className="stat-value">{stats.active}</div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Fuldførte Mål</div>
            <div className="stat-value">{stats.completed}</div>
          </div>

          {stats.expired > 0 && (
            <div className="stat-card stat-card-expired">
              <div className="stat-label">Udløbne Mål</div>
              <div className="stat-value">{stats.expired}</div>
            </div>
          )}

          <div className="stat-card">
            <div className="stat-label">I Alt</div>
            <div className="stat-value">{stats.total}</div>
          </div>
        </div>
      )}

      {unallocatedTotal > 0 && (
        <div className="unallocated-surplus-card">
          <div className="unallocated-surplus-header">
            <PiggyBank aria-hidden="true" size={20} />
            <span className="unallocated-surplus-title">Uallokeret overskud</span>
            <span className="unallocated-surplus-total">{formatAmount(unallocatedTotal)}</span>
          </div>
          <p className="unallocated-surplus-hint">
            {hasDefaultGoal
              ? 'Overskud fra tidligere månedslukninger, som ikke kunne opspares automatisk.'
              : 'Vælg et standardmål (stjernen på et mål), så fremtidigt budgetoverskud opspares automatisk.'}
          </p>
          <ul className="unallocated-surplus-list">
            {unallocatedEntries.map((entry) => (
              <li key={`${entry.observed_at}-${entry.amount}`}>
                <span>{formatAmount(entry.amount)}</span>
                <span className="unallocated-reason">
                  {entry.reason === 'goal_already_complete'
                    ? 'standardmålet var allerede opfyldt'
                    : 'intet standardmål valgt'}
                </span>
                <span>{formatDate(entry.observed_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {goals.length === 0 ? (
        <div className="no-goals">
          <div className="no-goals-icon"><Target aria-hidden="true" size={48} /></div>
          <h3>Ingen mål endnu</h3>
          <p>Opret dit første mål for at komme i gang!</p>
          <button
            className="create-first-goal-button"
            onClick={() => onEditGoal?.(null)}
          >
            Opret Mål
          </button>
        </div>
      ) : (
        <div className="goals-list">
          {goals.map((goal) => (
            <GoalItem
              key={goal.id}
              goal={goal}
              onEdit={onEditGoal}
              onSetDefault={handleSetDefault}
              formatAmount={formatAmount}
              formatDate={formatDate}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default GoalOverview;
