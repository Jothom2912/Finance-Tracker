/**
 * BudgetSetup Component (Refactored with Hexagonal Architecture)
 * Apenas presenter, detaljer til hooks
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { AlertTriangle } from 'lucide-react';
import MessageDisplay from '../../MessageDisplay';
import { useBudgetService } from '../adapters/inbound/useBudgetService';
import { Budget } from '../domain/Budget';
import { useConfirm } from '../../ConfirmDialog/ConfirmDialog';
import './BudgetSetup.css';

function BudgetSetup({
    categories,
    onBudgetAdded,
    onBudgetUpdated,
    onBudgetDeleted,
    setError,
    setSuccessMessage,
    onCloseModal,
    initialBudget
}) {
    const confirm = useConfirm();

    // Use the hexagonal architecture hook
    const {
        budgets,
        loading: fetchingBudgets,
        error: serviceError,
        successMessage: serviceSuccess,
        fetchBudgetsByYear,
        createBudget,
        updateBudget,
        deleteBudget,
        clearError,
        clearSuccessMessage
    } = useBudgetService();

    // Local form state
    const [editingBudget, setEditingBudget] = useState(null);
    const [selectedCategoryId, setSelectedCategoryId] = useState('');
    const [budgetAmountInput, setBudgetAmountInput] = useState('');
    const [budgetMonth, setBudgetMonth] = useState('');
    const [budgetYear, setBudgetYear] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [selectedViewYear, setSelectedViewYear] = useState(() =>
        String(new Date().getFullYear())
    );

    const expenseCategories = categories.filter(cat => cat.type === 'expense');

    // Memoized options
    const monthOptions = useMemo(() => [
        { value: '01', label: 'Januar' },
        { value: '02', label: 'Februar' },
        { value: '03', label: 'Marts' },
        { value: '04', label: 'April' },
        { value: '05', label: 'Maj' },
        { value: '06', label: 'Juni' },
        { value: '07', label: 'Juli' },
        { value: '08', label: 'August' },
        { value: '09', label: 'September' },
        { value: '10', label: 'Oktober' },
        { value: '11', label: 'November' },
        { value: '12', label: 'December' }
    ], []);

    const yearOptions = useMemo(() => {
        const currentYear = new Date().getFullYear();
        const years = [];
        for (let i = currentYear - 2; i <= currentYear + 2; i++) {
            years.push(i);
        }
        return years;
    }, []);

    // Fetch budgets on year change
    useEffect(() => {
        fetchBudgetsByYear(selectedViewYear).catch(() => {
            // Error is handled by the hook
        });
    }, [selectedViewYear, fetchBudgetsByYear]);

    // Sync service messages to parent
    useEffect(() => {
        if (serviceError) {
            setError?.(serviceError);
        }
    }, [serviceError, setError]);

    useEffect(() => {
        if (serviceSuccess) {
            setSuccessMessage?.(serviceSuccess);
            clearSuccessMessage();
        }
    }, [serviceSuccess, setSuccessMessage, clearSuccessMessage]);

    // Handle initialBudget prop
    useEffect(() => {
        if (initialBudget) {
            const budget = Budget.fromApiResponse(initialBudget);
            setEditingBudget(budget);
        }
    }, [initialBudget]);

    // Reset form on edit state change
    useEffect(() => {
        const now = new Date();
        const currentMonth = String(now.getMonth() + 1).padStart(2, '0');
        const currentYear = String(now.getFullYear());

        if (editingBudget) {
            setSelectedCategoryId(String(editingBudget.category_id || ''));
            setBudgetAmountInput(String(editingBudget.amount || ''));
            setBudgetMonth(editingBudget.month || currentMonth);
            setBudgetYear(editingBudget.year || currentYear);
        } else {
            setSelectedCategoryId('');
            setBudgetAmountInput('');
            setBudgetMonth(currentMonth);
            setBudgetYear(currentYear);
        }

        clearError();
    }, [editingBudget, clearError]);

    // Check for duplicates
    const hasDuplicate = useMemo(() => {
        if (!selectedCategoryId || !budgetMonth || !budgetYear) return false;

        const categoryId = parseInt(selectedCategoryId, 10);
        return budgets.some(b =>
            b.category_id === categoryId &&
            b.month === budgetMonth &&
            b.year === budgetYear &&
            (!editingBudget || b.id !== editingBudget.id)
        );
    }, [selectedCategoryId, budgetMonth, budgetYear, budgets, editingBudget]);

    const getCategoryName = useCallback((categoryId) => {
        const category = categories.find(cat => cat.id === categoryId);
        return category ? category.name : 'Ukendt kategori';
    }, [categories]);

    // Group budgets by period
    const groupedBudgets = useMemo(() => {
        const grouped = budgets.reduce((acc, budget) => {
            const key = `${budget.year}-${budget.month}`;
            if (!acc[key]) acc[key] = [];
            acc[key].push(budget);
            return acc;
        }, {});

        return Object.keys(grouped)
            .sort((a, b) => b.localeCompare(a))
            .map(key => ({
                period: key,
                budgets: grouped[key].sort((a, b) =>
                    getCategoryName(a.category_id).localeCompare(
                        getCategoryName(b.category_id)
                    )
                )
            }));
    }, [budgets, getCategoryName]);

    const handleSubmitBudget = async (e) => {
        e.preventDefault();

        const categoryId = parseInt(selectedCategoryId, 10);
        if (isNaN(categoryId) || categoryId <= 0) {
            setError?.('Vælg venligst en kategori.');
            return;
        }

        const amount = parseFloat(budgetAmountInput);
        if (isNaN(amount) || amount <= 0) {
            setError?.('Beløb skal være et positivt tal.');
            return;
        }

        const budget = new Budget({
            id: editingBudget?.id,
            category_id: categoryId,
            amount: amount,
            month: budgetMonth,
            year: budgetYear
        });

        setIsSubmitting(true);

        try {
            if (editingBudget) {
                await updateBudget(budget);
                onBudgetUpdated?.();
            } else {
                await createBudget(budget);
                onBudgetAdded?.();
            }
            resetForm();
        } catch {
            // Errors are handled by the hook
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDeleteBudget = async (budgetId) => {
        const ok = await confirm({
            title: 'Slet budget?',
            message: 'Budgetposten slettes permanent.',
            confirmLabel: 'Slet',
            variant: 'danger',
        });
        if (!ok) return;

        setIsSubmitting(true);

        try {
            await deleteBudget(budgetId, selectedViewYear);
            onBudgetDeleted?.();
        } catch {
            // Errors are handled by the hook
        } finally {
            setIsSubmitting(false);
        }
    };

    const resetForm = () => {
        setEditingBudget(null);
        setSelectedCategoryId('');
        setBudgetAmountInput('');
        const now = new Date();
        setBudgetMonth(String(now.getMonth() + 1).padStart(2, '0'));
        setBudgetYear(String(now.getFullYear()));
    };

    const handleCancelBudgetEdit = () => {
        resetForm();
        clearError();
        onCloseModal?.();
    };

    const formatAmount = (amount) => {
        return new Intl.NumberFormat('da-DK', {
            style: 'currency',
            currency: 'DKK',
            minimumFractionDigits: 2
        }).format(amount);
    };

    const getPeriodLabel = (period) => {
        const [year, month] = period.split('-');
        const monthLabel = monthOptions.find(m => m.value === month)?.label || month;
        return `${monthLabel} ${year}`;
    };

    return (
        <div className="budget-setup-container">
            <div className="budget-setup-header">
                <h2>{editingBudget ? 'Rediger Budget' : 'Opret Nyt Budget'}</h2>
            </div>

            <MessageDisplay message={serviceError} type="error" />
            <MessageDisplay message={serviceSuccess} type="success" />

            <form onSubmit={handleSubmitBudget} className="budget-form">
                <div className="form-group">
                    <label htmlFor="category-select">
                        Kategori:
                        <select
                            id="category-select"
                            value={selectedCategoryId}
                            onChange={(e) => setSelectedCategoryId(e.target.value)}
                            required
                            disabled={isSubmitting}
                        >
                            <option value="">Vælg kategori</option>
                            {expenseCategories.map(cat => {
                                const catId = cat.id || cat.idCategory;
                                return (
                                    <option key={catId} value={String(catId)}>
                                        {cat.name}
                                    </option>
                                );
                            })}
                        </select>
                    </label>
                </div>

                <div className="form-group">
                    <label htmlFor="amount-input">
                        Budget beløb (DKK):
                        <input
                            id="amount-input"
                            type="number"
                            step="0.01"
                            min="0"
                            value={budgetAmountInput}
                            onChange={(e) => setBudgetAmountInput(e.target.value)}
                            required
                            disabled={isSubmitting}
                            placeholder="0.00"
                        />
                    </label>
                </div>

                <div className="form-row">
                    <div className="form-group">
                        <label htmlFor="month-select">
                            Måned:
                            <select
                                id="month-select"
                                value={budgetMonth}
                                onChange={(e) => setBudgetMonth(e.target.value)}
                                required
                                disabled={isSubmitting}
                            >
                                {monthOptions.map(month => (
                                    <option key={month.value} value={month.value}>
                                        {month.label}
                                    </option>
                                ))}
                            </select>
                        </label>
                    </div>

                    <div className="form-group">
                        <label htmlFor="year-select">
                            År:
                            <select
                                id="year-select"
                                value={budgetYear}
                                onChange={(e) => setBudgetYear(e.target.value)}
                                required
                                disabled={isSubmitting}
                            >
                                {yearOptions.map(year => (
                                    <option key={year} value={year}>
                                        {year}
                                    </option>
                                ))}
                            </select>
                        </label>
                    </div>
                </div>

                {hasDuplicate && (
                    <div className="duplicate-warning">
                        <AlertTriangle aria-hidden="true" size={16} />
                        Der findes allerede et budget for denne kategori i den valgte periode.
                    </div>
                )}

                <div className="form-actions">
                    <button
                        type="submit"
                        disabled={isSubmitting || hasDuplicate}
                        className="submit-button"
                    >
                        {isSubmitting
                            ? 'Gemmer...'
                            : editingBudget
                                ? 'Opdater Budget'
                                : 'Opret Budget'}
                    </button>
                    {(editingBudget || onCloseModal) && (
                        <button
                            type="button"
                            onClick={handleCancelBudgetEdit}
                            className="cancel-button"
                            disabled={isSubmitting}
                        >
                            Annuller
                        </button>
                    )}
                </div>
            </form>

            <div className="existing-budgets">
                <div className="budgets-header">
                    <h3>Eksisterende Budgetter</h3>
                    <div className="year-selector">
                        <label htmlFor="view-year-select">År:</label>
                        <select
                            id="view-year-select"
                            value={selectedViewYear}
                            onChange={(e) => setSelectedViewYear(e.target.value)}
                            className="period-select-small"
                        >
                            {yearOptions.map(year => (
                                <option key={`view-year-${year}`} value={year}>
                                    {year}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {fetchingBudgets ? (
                    <div className="loading-message">
                        <div className="loading-spinner"></div>
                        <p>Indlæser budgetter for {selectedViewYear}...</p>
                    </div>
                ) : groupedBudgets.length > 0 ? (
                    <div className="budget-groups">
                        {groupedBudgets.map(group => (
                            <div key={group.period} className="budget-group">
                                <h4 className="period-header">
                                    {getPeriodLabel(group.period)}
                                </h4>
                                <div className="budget-list">
                                    {group.budgets.map(budget => (
                                        <div key={budget.id} className="budget-item">
                                            <div className="budget-info">
                                                <span className="category-name">
                                                    {getCategoryName(budget.category_id)}
                                                </span>
                                                <span className="budget-amount">
                                                    {formatAmount(budget.amount)}
                                                </span>
                                            </div>
                                            <div className="budget-actions">
                                                <button
                                                    onClick={() => setEditingBudget(budget)}
                                                    className="edit-button"
                                                    disabled={isSubmitting}
                                                >
                                                    Rediger
                                                </button>
                                                <button
                                                    onClick={() => handleDeleteBudget(budget.id)}
                                                    className="delete-button"
                                                    disabled={isSubmitting}
                                                >
                                                    Slet
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="no-budgets">
                        <p>Ingen budgetter fundet for {selectedViewYear}.</p>
                        <p>Opret dit første budget ovenfor!</p>
                    </div>
                )}
            </div>
        </div>
    );
}

export default BudgetSetup;
