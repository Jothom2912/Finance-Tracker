// frontend/src/components/Goal/GoalItem/GoalItem.js
import React from 'react';
import './GoalItem.css';

function GoalItem({ goal, onEdit, formatAmount, formatDate }) {
  const progress = goal.target_amount > 0 
    ? Math.min((goal.current_amount / goal.target_amount) * 100, 100)
    : 0;
  
  const isCompleted = goal.status === 'completed' || goal.current_amount >= goal.target_amount;
  const remaining = Math.max(goal.target_amount - goal.current_amount, 0);
  const daysRemaining = goal.target_date 
    ? Math.ceil((new Date(goal.target_date) - new Date()) / (1000 * 60 * 60 * 24))
    : null;

  const getStatusColor = () => {
    if (isCompleted) return '#48bb78'; // Green
    if (progress >= 75) return '#38a169'; // Dark green
    if (progress >= 50) return '#ed8936'; // Orange
    return '#e53e3e'; // Red
  };

  const getStatusText = () => {
    if (isCompleted) return 'Fuldført';
    if (progress >= 75) return 'Næsten der';
    if (progress >= 50) return 'Godt på vej';
    return 'Tidligt stadie';
  };

  return (
    <div className={`goal-item ${isCompleted ? 'completed' : ''}`}>
      <div className="goal-item-header">
        <div className="goal-name-section">
          <h3 className="goal-name">{goal.name || 'Unavngivet Mål'}</h3>
          {goal.status && (
            <span className={`goal-status-badge ${goal.status}`}>
              {goal.status}
            </span>
          )}
        </div>
        <button 
          className="edit-goal-button"
          onClick={() => onEdit?.(goal)}
          title="Rediger mål"
        >
          ✏️
        </button>
      </div>

      <div className="goal-progress-section">
        <div className="progress-info">
          <div className="amount-info">
            <span className="current-amount">{formatAmount(goal.current_amount)}</span>
            <span className="separator">/</span>
            <span className="target-amount">{formatAmount(goal.target_amount)}</span>
          </div>
          <div className="progress-percentage">{progress.toFixed(1)}%</div>
        </div>
        
        <div className="progress-bar-container">
          <div 
            className="progress-bar" 
            style={{ 
              width: `${progress}%`,
              backgroundColor: getStatusColor()
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
          <span className="detail-value" style={{ color: getStatusColor() }}>
            {getStatusText()}
          </span>
        </div>
      </div>
    </div>
  );
}

export default GoalItem;

