import { useState, useEffect, useCallback } from 'react';
import MessageDisplay from '../../MessageDisplay';
import { useGoals } from '../../../hooks/useGoals';
import { useConfirm } from '../../ConfirmDialog/ConfirmDialog';
import './GoalSetup.css';

const STATUS_LABELS = {
  active: 'Aktiv',
  paused: 'Pauseret',
  completed: 'Opfyldt',
  expired: 'Udløbet',
};

function GoalSetup({
    onGoalAdded,
    onGoalUpdated,
    onGoalDeleted,
    setError,
    setSuccessMessage,
    onCloseModal,
    initialGoal
}) {
    const confirm = useConfirm();
    // Mål-listen (UI-formen fra mapGoalFromRest) og mutationerne deler
    // react-query-cachen med resten af appen; mutationerne invaliderer
    // selv 'goals'-scope, så alle views opdateres uden parent-callbacks.
    const { goals, error: goalsError, create, update, remove } = useGoals();
    const [goalName, setGoalName] = useState('');
    const [targetAmount, setTargetAmount] = useState('');
    const [currentAmount, setCurrentAmount] = useState('');
    const [targetDate, setTargetDate] = useState('');
    const [status, setStatus] = useState('active');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [localError, setLocalError] = useState(null);
    const [localSuccessMessage, setLocalSuccessMessage] = useState(null);

    // initialGoal er UI-formen fra useGoals (id, targetAmount, storedStatus, ...).
    useEffect(() => {
        if (initialGoal) {
            setGoalName(initialGoal.name || '');
            setTargetAmount(String(initialGoal.targetAmount || ''));
            setCurrentAmount(String(initialGoal.currentAmount || '0'));
            setTargetDate(initialGoal.targetDate || '');
            setStatus(initialGoal.storedStatus || 'active');
        } else {
            setGoalName('');
            setTargetAmount('');
            setCurrentAmount('0');
            setTargetDate('');
            setStatus('active');
        }
        setLocalError(null);
        setLocalSuccessMessage(null);
    }, [initialGoal]);

    // Løft fetch-fejlen til side-niveau (toast); den vises også lokalt nedenfor.
    useEffect(() => {
        if (goalsError) setError?.(goalsError);
    }, [goalsError, setError]);

    const clearMessages = useCallback(() => {
        setLocalError(null);
        setLocalSuccessMessage(null);
        setError?.(null);
        setSuccessMessage?.(null);
    }, [setError, setSuccessMessage]);

    const validateForm = () => {
        if (!goalName || goalName.trim() === '') {
            return 'Mål navn er påkrævet';
        }
        if (!targetAmount || parseFloat(targetAmount) <= 0) {
            return 'Mål beløb skal være større end 0';
        }
        const target = parseFloat(targetAmount);
        const current = parseFloat(currentAmount || '0');
        if (current < 0) {
            return 'Nuværende beløb kan ikke være negativt';
        }
        if (current > target) {
            return 'Nuværende beløb kan ikke være større end mål beløb';
        }
        if (targetDate) {
            const date = new Date(targetDate);
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            if (date <= today) {
                return 'Deadline skal være i fremtiden';
            }
        }
        return null;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        clearMessages();

        const validationError = validateForm();
        if (validationError) {
            setLocalError(validationError);
            setError?.(validationError);
            return;
        }

        setIsSubmitting(true);

        try {
            const accountId = localStorage.getItem('account_id');
            if (!accountId) {
                throw new Error('Account ID mangler. Vælg en konto først.');
            }

            const goalData = {
                name: goalName.trim() || null,
                target_amount: parseFloat(targetAmount),
                current_amount: parseFloat(currentAmount || '0'),
                target_date: targetDate || null,
                status: status || 'active',
                Account_idAccount: parseInt(accountId)
            };

            if (initialGoal?.id) {
                await update(initialGoal.id, goalData);
                setLocalSuccessMessage('Mål opdateret succesfuldt!');
                setSuccessMessage?.('Mål opdateret succesfuldt!');
                onGoalUpdated?.();
            } else {
                await create(goalData);
                setLocalSuccessMessage('Mål oprettet succesfuldt!');
                setSuccessMessage?.('Mål oprettet succesfuldt!');
                onGoalAdded?.();
            }

            setGoalName('');
            setTargetAmount('');
            setCurrentAmount('0');
            setTargetDate('');
            setStatus('active');
        } catch (err) {
            console.error('Fejl ved oprettelse/opdatering af mål:', err);
            const errorMessage = err.message || 'Der opstod en fejl ved oprettelse/opdatering af mål.';
            setLocalError(errorMessage);
            setError?.(errorMessage);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDelete = async () => {
        if (!initialGoal?.id) return;

        const ok = await confirm({
            title: 'Slet mål?',
            message: 'Det opsparingsmål slettes permanent.',
            confirmLabel: 'Slet',
            variant: 'danger',
        });
        if (!ok) return;

        clearMessages();
        setIsSubmitting(true);

        try {
            await remove(initialGoal.id);

            setLocalSuccessMessage('Mål slettet succesfuldt!');
            setSuccessMessage?.('Mål slettet succesfuldt!');
            onGoalDeleted?.();

            setGoalName('');
            setTargetAmount('');
            setCurrentAmount('0');
            setTargetDate('');
            setStatus('active');
        } catch (err) {
            console.error('Fejl ved sletning af mål:', err);
            const errorMessage = err.message || 'Der opstod en fejl ved sletning af mål.';
            setLocalError(errorMessage);
            setError?.(errorMessage);
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="goal-setup-container">
            {goalsError && <MessageDisplay message={goalsError} type="error" />}
            {localError && <MessageDisplay message={localError} type="error" />}
            {localSuccessMessage && <MessageDisplay message={localSuccessMessage} type="success" />}

            <form onSubmit={handleSubmit} className="goal-form">
                <div className="form-group">
                    <label htmlFor="goalName">Mål Navn *</label>
                    <input
                        type="text"
                        id="goalName"
                        value={goalName}
                        onChange={(e) => setGoalName(e.target.value)}
                        placeholder="F.eks. Nyt hus, Bil, Ferie"
                        maxLength={45}
                        required
                    />
                </div>

                <div className="form-row">
                    <div className="form-group">
                        <label htmlFor="targetAmount">Mål Beløb (DKK) *</label>
                        <input
                            type="number"
                            id="targetAmount"
                            value={targetAmount}
                            onChange={(e) => setTargetAmount(e.target.value)}
                            placeholder="0.00"
                            min="0"
                            step="0.01"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="currentAmount">Nuværende Beløb (DKK)</label>
                        <input
                            type="number"
                            id="currentAmount"
                            value={currentAmount}
                            onChange={(e) => setCurrentAmount(e.target.value)}
                            placeholder="0.00"
                            min="0"
                            step="0.01"
                        />
                    </div>
                </div>

                <div className="form-row">
                    <div className="form-group">
                        <label htmlFor="targetDate">Deadline</label>
                        <input
                            type="date"
                            id="targetDate"
                            value={targetDate}
                            onChange={(e) => setTargetDate(e.target.value)}
                            min={new Date().toISOString().split('T')[0]}
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="status">Status</label>
                        <select
                            id="status"
                            value={status}
                            onChange={(e) => setStatus(e.target.value)}
                        >
                            <option value="active">Aktiv</option>
                            <option value="paused">Pauseret</option>
                        </select>
                    </div>
                </div>

                <div className="form-actions">
                    {initialGoal?.id && (
                        <button
                            type="button"
                            onClick={handleDelete}
                            className="delete-button"
                            disabled={isSubmitting}
                        >
                            Slet Mål
                        </button>
                    )}
                    <div className="form-actions-right">
                        {onCloseModal && (
                            <button
                                type="button"
                                onClick={onCloseModal}
                                className="cancel-button"
                                disabled={isSubmitting}
                            >
                                Annuller
                            </button>
                        )}
                        <button
                            type="submit"
                            className="submit-button"
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? 'Gemmer...' : (initialGoal?.id ? 'Opdater Mål' : 'Opret Mål')}
                        </button>
                    </div>
                </div>
            </form>

            {goals.length > 0 && (
                <div className="existing-goals">
                    <h3>Eksisterende Mål ({goals.length})</h3>
                    <div className="goals-list">
                        {goals.map((goal) => (
                            <div key={goal.id} className="goal-list-item">
                                <div className="goal-list-info">
                                    <div className="goal-list-name">{goal.name || 'Unavngivet Mål'}</div>
                                    <div className="goal-list-amount">
                                        {new Intl.NumberFormat('da-DK', {
                                            style: 'currency',
                                            currency: 'DKK',
                                            minimumFractionDigits: 0
                                        }).format(goal.currentAmount || 0)} / {new Intl.NumberFormat('da-DK', {
                                            style: 'currency',
                                            currency: 'DKK',
                                            minimumFractionDigits: 0
                                        }).format(goal.targetAmount || 0)}
                                    </div>
                                </div>
                                <div className="goal-list-status">
                                    <span className={`status-badge ${goal.status || 'active'}`}>
                                        {STATUS_LABELS[goal.status] || goal.status || 'Aktiv'}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

export default GoalSetup;
