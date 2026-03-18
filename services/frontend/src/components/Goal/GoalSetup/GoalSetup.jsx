// frontend/src/components/Goal/GoalSetup/GoalSetup.js
import React, { useState, useEffect, useCallback } from 'react';
import MessageDisplay from '../../MessageDisplay';
import apiClient from '../../../utils/apiClient';
import './GoalSetup.css';

function GoalSetup({
    onGoalAdded,
    onGoalUpdated,
    onGoalDeleted,
    setError,
    setSuccessMessage,
    onCloseModal,
    initialGoal
}) {
    const [goalName, setGoalName] = useState('');
    const [targetAmount, setTargetAmount] = useState('');
    const [currentAmount, setCurrentAmount] = useState('');
    const [targetDate, setTargetDate] = useState('');
    const [status, setStatus] = useState('active');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [goals, setGoals] = useState([]);
    const [, setLoading] = useState(false);
    const [localError, setLocalError] = useState(null);
    const [localSuccessMessage, setLocalSuccessMessage] = useState(null);

    // Reset form når vi skifter mellem editing og create mode
    useEffect(() => {
        if (initialGoal) {
            setGoalName(initialGoal.name || '');
            setTargetAmount(String(initialGoal.target_amount || ''));
            setCurrentAmount(String(initialGoal.current_amount || '0'));
            setTargetDate(initialGoal.target_date || '');
            setStatus(initialGoal.status || 'active');
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

    // Hent eksisterende goals
    const fetchGoals = useCallback(async () => {
        setLoading(true);
        setLocalError(null);
        try {
            // Backend henter account_id automatisk fra X-Account-ID header
            const response = await apiClient.get('/goals/');
            if (!response.ok) {
                if (response.status === 404) {
                    setGoals([]);
                    return;
                }
                const errorDetail = await response.json();
                throw new Error(`Kunne ikke hente mål: ${errorDetail.detail || 'Ukendt fejl'}`);
            }
            const data = await response.json();
            setGoals(data);
        } catch (err) {
            console.error("Fejl ved hentning af mål:", err);
            setLocalError(err.message);
            setError?.(err.message);
            setGoals([]);
        } finally {
            setLoading(false);
        }
    }, [setError]);

    useEffect(() => {
        fetchGoals();
    }, [fetchGoals]);

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
            // Hent account_id fra localStorage (samme som apiClient bruger)
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

            let response;
            if (initialGoal?.idGoal) {
                // Update existing goal
                response = await apiClient.put(`/goals/${initialGoal.idGoal}`, goalData);
                if (!response.ok) {
                    const errorData = await response.json();
                    const errorMessage = Array.isArray(errorData.detail)
                        ? errorData.detail.map(e => e.msg || JSON.stringify(e)).join(', ')
                        : (typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail)) || 'Kunne ikke opdatere mål';
                    throw new Error(errorMessage);
                }
                await response.json();
                setLocalSuccessMessage('Mål opdateret succesfuldt!');
                setSuccessMessage?.('Mål opdateret succesfuldt!');
                onGoalUpdated?.();
            } else {
                // Create new goal
                response = await apiClient.post('/goals/', goalData);
                if (!response.ok) {
                    const errorData = await response.json();
                    const errorMessage = Array.isArray(errorData.detail)
                        ? errorData.detail.map(e => e.msg || JSON.stringify(e)).join(', ')
                        : (typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail)) || 'Kunne ikke oprette mål';
                    throw new Error(errorMessage);
                }
                await response.json();
                setLocalSuccessMessage('Mål oprettet succesfuldt!');
                setSuccessMessage?.('Mål oprettet succesfuldt!');
                onGoalAdded?.();
            }

            // Reset form
            setGoalName('');
            setTargetAmount('');
            setCurrentAmount('0');
            setTargetDate('');
            setStatus('active');

            // Refresh goals list
            await fetchGoals();
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
        if (!initialGoal?.idGoal) return;

        if (!window.confirm('Er du sikker på, at du vil slette dette mål?')) {
            return;
        }

        clearMessages();
        setIsSubmitting(true);

        try {
            const response = await apiClient.delete(`/goals/${initialGoal.idGoal}`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Kunne ikke slette mål');
            }

            setLocalSuccessMessage('Mål slettet succesfuldt!');
            setSuccessMessage?.('Mål slettet succesfuldt!');
            onGoalDeleted?.();

            // Reset form
            setGoalName('');
            setTargetAmount('');
            setCurrentAmount('0');
            setTargetDate('');
            setStatus('active');

            // Refresh goals list
            await fetchGoals();
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
                            <option value="completed">Fuldført</option>
                            <option value="paused">Pauset</option>
                        </select>
                    </div>
                </div>

                <div className="form-actions">
                    {initialGoal?.idGoal && (
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
                            {isSubmitting ? 'Gemmer...' : (initialGoal?.idGoal ? 'Opdater Mål' : 'Opret Mål')}
                        </button>
                    </div>
                </div>
            </form>

            {/* Eksisterende Goals Liste */}
            {goals.length > 0 && (
                <div className="existing-goals">
                    <h3>Eksisterende Mål ({goals.length})</h3>
                    <div className="goals-list">
                        {goals.map((goal) => (
                            <div key={goal.idGoal} className="goal-list-item">
                                <div className="goal-list-info">
                                    <div className="goal-list-name">{goal.name || 'Unavngivet Mål'}</div>
                                    <div className="goal-list-amount">
                                        {new Intl.NumberFormat('da-DK', {
                                            style: 'currency',
                                            currency: 'DKK',
                                            minimumFractionDigits: 0
                                        }).format(goal.current_amount || 0)} / {new Intl.NumberFormat('da-DK', {
                                            style: 'currency',
                                            currency: 'DKK',
                                            minimumFractionDigits: 0
                                        }).format(goal.target_amount || 0)}
                                    </div>
                                </div>
                                <div className="goal-list-status">
                                    <span className={`status-badge ${goal.status || 'active'}`}>
                                        {goal.status || 'active'}
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

