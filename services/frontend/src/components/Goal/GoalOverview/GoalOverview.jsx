// frontend/src/components/Goal/GoalOverview/GoalOverview.js
import React, { useState, useEffect, useMemo } from 'react';
import apiClient from '../../../utils/apiClient';
import MessageDisplay from '../../MessageDisplay';
import GoalItem from '../GoalItem/GoalItem';
import './GoalOverview.css';

function GoalOverview({ refreshTrigger, setError, setSuccessMessage, onEditGoal }) {
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [localError, setLocalError] = useState(null);

  // Fetch goals
  useEffect(() => {
    const fetchGoals = async () => {
      setLoading(true);
      setLocalError(null);
      setError?.(null);

      try {
        // Backend henter account_id automatisk fra X-Account-ID header
        const response = await apiClient.get('/goals/');
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Kunne ikke hente mål');
        }

        const data = await response.json();
        setGoals(data);
      } catch (err) {
        console.error('Fejl ved hentning af mål:', err);
        const errorMessage = err.message || 'Der opstod en fejl ved hentning af mål.';
        setLocalError(errorMessage);
        setError?.(errorMessage);
      } finally {
        setLoading(false);
      }
    };

    fetchGoals();
  }, [refreshTrigger, setError]);

  // Beregn statistikker
  const stats = useMemo(() => {
    if (!goals || goals.length === 0) {
      return {
        total: 0,
        completed: 0,
        active: 0,
        totalTarget: 0,
        totalCurrent: 0,
        totalProgress: 0
      };
    }

    const completed = goals.filter(g => g.status === 'completed' || g.current_amount >= g.target_amount).length;
    const active = goals.filter(g => g.status !== 'completed' && g.current_amount < g.target_amount).length;
    const totalTarget = goals.reduce((sum, g) => sum + (g.target_amount || 0), 0);
    const totalCurrent = goals.reduce((sum, g) => sum + (g.current_amount || 0), 0);
    const totalProgress = totalTarget > 0 ? (totalCurrent / totalTarget) * 100 : 0;

    return {
      total: goals.length,
      completed,
      active,
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

      {/* Statistikker */}
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

          <div className="stat-card">
            <div className="stat-label">I Alt</div>
            <div className="stat-value">{stats.total}</div>
          </div>
        </div>
      )}

      {/* Goals Liste */}
      {goals.length === 0 ? (
        <div className="no-goals">
          <div className="no-goals-icon">🎯</div>
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
              key={goal.idGoal}
              goal={goal}
              onEdit={onEditGoal}
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

