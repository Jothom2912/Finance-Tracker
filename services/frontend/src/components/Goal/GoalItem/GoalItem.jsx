import { useState } from 'react';
import { ChevronDown, ChevronUp, Pencil, Star } from 'lucide-react';
import GoalAllocationHistory from './GoalAllocationHistory';
import './GoalItem.css';

const STATUS_CONFIG = {
  completed: { label: 'Opfyldt', color: '#48bb78', badgeClass: 'completed' },
  expired:   { label: 'Udløbet', color: '#e53e3e', badgeClass: 'expired' },
  paused:    { label: 'Pauseret', color: '#a0aec0', badgeClass: 'paused' },
  active:    { label: 'Aktiv', color: '#4299e1', badgeClass: 'active' },
};

// Forventer UI-formen fra useGoals' mapGoalFromRest — ikke den rå REST-form.
function GoalItem({ goal, onEdit, onSetDefault, formatAmount, formatDate }) {
  const [showHistory, setShowHistory] = useState(false);
  const progress = goal.percentComplete ?? (
    goal.targetAmount > 0
      ? Math.min((goal.currentAmount / goal.targetAmount) * 100, 100)
      : 0
  );

  const effectiveStatus = goal.status || 'active';
  const config = STATUS_CONFIG[effectiveStatus] || STATUS_CONFIG.active;
  const remaining = Math.max(goal.targetAmount - goal.currentAmount, 0);
  const daysRemaining = goal.targetDate
    ? Math.ceil((new Date(goal.targetDate) - new Date()) / (1000 * 60 * 60 * 24))
    : null;

  const getProgressColor = () => {
    if (effectiveStatus === 'completed') return '#48bb78';
    if (effectiveStatus === 'expired') return '#e53e3e';
    if (progress >= 75) return '#38a169';
    if (progress >= 50) return '#ed8936';
    return '#e53e3e';
  };

  const getProgressText = () => {
    if (effectiveStatus === 'completed') return 'Fuldført';
    if (effectiveStatus === 'expired') return 'Udløbet';
    if (effectiveStatus === 'paused') return 'Pauseret';
    if (progress >= 75) return 'Næsten der';
    if (progress >= 50) return 'Godt på vej';
    return 'Tidligt stadie';
  };

  return (
    <div className={`goal-item ${effectiveStatus}`}>
      <div className="goal-item-header">
        <div className="goal-name-section">
          <h3 className="goal-name">{goal.name || 'Unavngivet Mål'}</h3>
          <span className={`goal-status-badge ${config.badgeClass}`}>
            {config.label}
          </span>
          {goal.isDefaultSavingsGoal && (
            <span className="goal-status-badge default-savings">Standardmål</span>
          )}
        </div>
        <div className="goal-item-actions">
          <button
            className={`default-goal-button ${goal.isDefaultSavingsGoal ? 'is-default' : ''}`}
            onClick={() => onSetDefault?.(goal)}
            title={
              goal.isDefaultSavingsGoal
                ? 'Fjern som standardopsparingsmål'
                : 'Sæt som standardopsparingsmål — budgetoverskud opspares her automatisk'
            }
            aria-label={
              goal.isDefaultSavingsGoal
                ? 'Fjern som standardopsparingsmål'
                : 'Sæt som standardopsparingsmål'
            }
            aria-pressed={goal.isDefaultSavingsGoal}
          >
            <Star aria-hidden="true" size={16} fill={goal.isDefaultSavingsGoal ? 'currentColor' : 'none'} />
          </button>
          <button
            className="edit-goal-button"
            onClick={() => onEdit?.(goal)}
            title="Rediger mål"
            aria-label="Rediger mål"
          >
            <Pencil aria-hidden="true" size={16} />
          </button>
        </div>
      </div>

      <div className="goal-progress-section">
        <div className="progress-info">
          <div className="amount-info">
            <span className="current-amount">{formatAmount(goal.currentAmount)}</span>
            <span className="separator">/</span>
            <span className="target-amount">{formatAmount(goal.targetAmount)}</span>
          </div>
          <div className="progress-percentage">{Math.min(progress, 100).toFixed(1)}%</div>
        </div>

        <div className="progress-bar-container">
          <div
            className="progress-bar"
            style={{
              width: `${Math.min(progress, 100)}%`,
              backgroundColor: getProgressColor()
            }}
          ></div>
        </div>
      </div>

      <div className="goal-details">
        <div className="detail-item">
          <span className="detail-label">Tilbage:</span>
          <span className="detail-value">{formatAmount(remaining)}</span>
        </div>

        {goal.targetDate && (
          <div className="detail-item">
            <span className="detail-label">Deadline:</span>
            <span className={`detail-value ${daysRemaining < 0 ? 'overdue' : daysRemaining <= 30 ? 'warning' : ''}`}>
              {formatDate(goal.targetDate)}
              {daysRemaining !== null && (
                <span className="days-remaining">
                  {daysRemaining < 0
                    ? ` (${Math.abs(daysRemaining)} dage over)`
                    : ` (${daysRemaining} dage tilbage)`
                  }
                </span>
              )}
            </span>
          </div>
        )}

        <div className="detail-item">
          <span className="detail-label">Status:</span>
          <span className="detail-value" style={{ color: getProgressColor() }}>
            {getProgressText()}
          </span>
        </div>
      </div>

      <div className="goal-allocation-section">
        <button
          className="allocation-history-toggle"
          onClick={() => setShowHistory((current) => !current)}
          aria-expanded={showHistory}
        >
          {showHistory ? <ChevronUp aria-hidden="true" size={14} /> : <ChevronDown aria-hidden="true" size={14} />}
          Automatiske opsparinger
        </button>
        {showHistory && (
          <GoalAllocationHistory goalId={goal.id} formatAmount={formatAmount} formatDate={formatDate} />
        )}
      </div>
    </div>
  );
}

export default GoalItem;
