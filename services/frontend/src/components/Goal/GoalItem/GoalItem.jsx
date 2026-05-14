import { Pencil } from 'lucide-react';
import './GoalItem.css';

const STATUS_CONFIG = {
  completed: { label: 'Opfyldt', color: '#48bb78', badgeClass: 'completed' },
  expired:   { label: 'Udløbet', color: '#e53e3e', badgeClass: 'expired' },
  paused:    { label: 'Pauseret', color: '#a0aec0', badgeClass: 'paused' },
  active:    { label: 'Aktiv', color: '#4299e1', badgeClass: 'active' },
};

function GoalItem({ goal, onEdit, formatAmount, formatDate }) {
  const progress = goal.progress_percent ?? (
    goal.target_amount > 0
      ? Math.min((goal.current_amount / goal.target_amount) * 100, 100)
      : 0
  );

  const effectiveStatus = goal.effective_status || goal.status || 'active';
  const config = STATUS_CONFIG[effectiveStatus] || STATUS_CONFIG.active;
  const remaining = Math.max(goal.target_amount - goal.current_amount, 0);
  const daysRemaining = goal.target_date
    ? Math.ceil((new Date(goal.target_date) - new Date()) / (1000 * 60 * 60 * 24))
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
        </div>
        <button
          className="edit-goal-button"
          onClick={() => onEdit?.(goal)}
          title="Rediger mål"
          aria-label="Rediger mål"
        >
          <Pencil aria-hidden="true" size={16} />
        </button>
      </div>

      <div className="goal-progress-section">
        <div className="progress-info">
          <div className="amount-info">
            <span className="current-amount">{formatAmount(goal.current_amount)}</span>
            <span className="separator">/</span>
            <span className="target-amount">{formatAmount(goal.target_amount)}</span>
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

        {goal.target_date && (
          <div className="detail-item">
            <span className="detail-label">Deadline:</span>
            <span className={`detail-value ${daysRemaining < 0 ? 'overdue' : daysRemaining <= 30 ? 'warning' : ''}`}>
              {formatDate(goal.target_date)}
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
    </div>
  );
}

export default GoalItem;
