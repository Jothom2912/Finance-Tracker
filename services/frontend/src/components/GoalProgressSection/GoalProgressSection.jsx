
import { formatAmount, formatDate } from '../../lib/formatters';
import './GoalProgressSection.css';

function GoalCard({ goal }) {
  const pct = Math.min(goal.percentComplete, 100);
  const isComplete = goal.status === 'completed' || pct >= 100;

  return (
    <div className={`goal-card ${isComplete ? 'goal-complete' : ''}`}>
      <div className="goal-card-header">
        <span className="goal-name">{goal.name || 'Unavngivet mål'}</span>
        {isComplete && <span className="goal-badge">Nået!</span>}
      </div>
      <div className="goal-progress-track">
        <div
          className="goal-progress-fill"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="goal-card-details">
        <span className="goal-amounts">
          {formatAmount(goal.currentAmount)} af {formatAmount(goal.targetAmount)}
        </span>
        <span className="goal-percentage">{pct.toFixed(0)}%</span>
      </div>
      {goal.targetDate && (
        <div className="goal-deadline">
          Deadline: {formatDate(goal.targetDate)}
        </div>
      )}
    </div>
  );
}

function GoalProgressSection({ goals }) {
  if (!goals || goals.length === 0) {
    return (
      <div className="goal-progress-section">
        <h3>Sparemål</h3>
        <p className="no-data-message">Ingen sparemål oprettet endnu.</p>
      </div>
    );
  }

  const activeGoals = goals.filter((g) => g.status !== 'completed');
  const completedGoals = goals.filter((g) => g.status === 'completed');

  return (
    <div className="goal-progress-section">
      <h3>Sparemål</h3>
      <div className="goal-cards-grid">
        {activeGoals.map((goal) => (
          <GoalCard key={goal.id} goal={goal} />
        ))}
        {completedGoals.map((goal) => (
          <GoalCard key={goal.id} goal={goal} />
        ))}
      </div>
    </div>
  );
}

export default GoalProgressSection;
