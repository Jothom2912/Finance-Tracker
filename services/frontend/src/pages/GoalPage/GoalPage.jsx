import { useState } from 'react';
import { Target, Settings } from 'lucide-react';
import GoalOverview from '../../components/Goal/GoalOverview/GoalOverview';
import GoalSetup from '../../components/Goal/GoalSetup/GoalSetup';
import Modal from '../../components/Modal/Modal';
import { useNotifications } from '../../hooks/useNotifications';
import './GoalPage.css';

function GoalPage() {
  const { showError, showSuccess } = useNotifications();

  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [activeView, setActiveView] = useState('overview');
  const [showGoalModal, setShowGoalModal] = useState(false);
  const [editingGoal, setEditingGoal] = useState(null);

  const handleGoalChange = () => setRefreshTrigger((prev) => prev + 1);

  const handleViewChange = (view) => {
    setActiveView(view);
  };

  const handleEditGoal = (goal) => {
    setEditingGoal(goal);
    setShowGoalModal(true);
  };

  const handleGoalSaved = () => {
    handleGoalChange();
    setShowGoalModal(false);
    setEditingGoal(null);
  };

  const handleCancelEdit = () => {
    setEditingGoal(null);
    setShowGoalModal(false);
  };

  const views = [
    { id: 'overview', label: 'Mål Oversigt', Icon: Target, description: 'Se alle dine mål og fremgang' },
    { id: 'setup', label: 'Administrer', Icon: Settings, description: 'Opret og rediger mål' },
  ];

  return (
    <div className="goal-page">
      <div className="goal-page-header">
        <div className="header-content">
          <h1>Mål</h1>
          <p className="header-subtitle">Sæt og opnå dine sparemål</p>
        </div>
      </div>

      <div className="view-toggle">
        {views.map((view) => (
          <button
            key={view.id}
            className={`toggle-button ${activeView === view.id ? 'active' : ''}`}
            onClick={() => handleViewChange(view.id)}
            title={view.description}
          >
            <span className="button-icon"><view.Icon aria-hidden="true" size={18} /></span>
            <span className="button-label">{view.label}</span>
          </button>
        ))}
      </div>

      <div className={`goal-content ${activeView}`}>
        {activeView === 'overview' && (
          <div className="single-panel">
            <GoalOverview
              refreshTrigger={refreshTrigger}
              setError={showError}
              setSuccessMessage={showSuccess}
              onEditGoal={handleEditGoal}
            />
          </div>
        )}
        {activeView === 'setup' && (
          <div className="single-panel">
            <GoalSetup
              onGoalAdded={handleGoalChange}
              onGoalUpdated={handleGoalChange}
              onGoalDeleted={handleGoalChange}
              setError={showError}
              setSuccessMessage={showSuccess}
            />
          </div>
        )}
      </div>

      <Modal
        isOpen={showGoalModal}
        onClose={handleCancelEdit}
        title={editingGoal?.idGoal ? 'Rediger Mål' : 'Opret Nyt Mål'}
      >
        <GoalSetup
          onGoalAdded={handleGoalSaved}
          onGoalUpdated={handleGoalSaved}
          onGoalDeleted={handleGoalSaved}
          setError={showError}
          setSuccessMessage={showSuccess}
          onCloseModal={handleCancelEdit}
          initialGoal={editingGoal}
        />
      </Modal>
    </div>
  );
}

export default GoalPage;
