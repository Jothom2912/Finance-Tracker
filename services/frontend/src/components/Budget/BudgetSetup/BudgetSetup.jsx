import React, { useState, useEffect, useMemo, useCallback } from 'react';
import MessageDisplay from '../../MessageDisplay';
import apiClient from '../../../utils/apiClient';
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
    // Transform initialBudget hvis den kommer fra parent
    const transformBudget = useCallback((budget) => {
        if (!budget) return null;
        
        // Hvis budget allerede har month og year, returner som den er
        if (budget.month && budget.year) {
            return {
                ...budget,
                id: budget.idBudget || budget.id,
                category_id: budget.categories?.[0]?.idCategory || 
                            budget.Category_idCategory || 
                            budget.category_id
            };
        }
        
        // Ellers transformér fra budget_date
        let month = '';
        let yearStr = '';
        if (budget.budget_date) {
            const budgetDate = new Date(budget.budget_date);
            month = String(budgetDate.getMonth() + 1).padStart(2, '0');
            yearStr = String(budgetDate.getFullYear());
        }
        
        const categoryId = budget.categories?.[0]?.idCategory || 
                          budget.Category_idCategory || 
                          budget.category_id;
        
        return {
            ...budget,
            id: budget.idBudget || budget.id,
            month: month,
            year: yearStr,
            category_id: categoryId
        };
    }, []);
    
    const [editingBudget, setEditingBudget] = useState(null);
    const [selectedCategoryId, setSelectedCategoryId] = useState('');
    const [budgetAmountInput, setBudgetAmountInput] = useState('');
    const [budgetMonth, setBudgetMonth] = useState('');
    const [budgetYear, setBudgetYear] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Lokal state til budgetter i BudgetSetup og loading state
    const [budgets, setBudgets] = useState([]);
    const [fetchingBudgets, setFetchingBudgets] = useState(false);

    // Lokal state til fejl/succesmeddelelser
    const [localError, setLocalError] = useState(null);
    const [localSuccessMessage, setLocalSuccessMessage] = useState(null);

    // Ny state for det valgte år til visning af eksisterende budgetter
    const [selectedViewYear, setSelectedViewYear] = useState(String(new Date().getFullYear()));

    // Filtrer kun expense kategorier (vi budgetterer typisk kun udgifter)
    const expenseCategories = categories.filter(cat => cat.type === 'expense');

    // Memoized hjælpefunktioner
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

    // Hjælpefunktion til at finde kategorinavn (memoized for ydeevne)
    const getCategoryName = useCallback((categoryId) => {
        const category = categories.find(cat => cat.id === categoryId);
        return category ? category.name : 'Ukendt kategori';
    }, [categories]);

    // Tjek for dubletter (bruger den lokale 'budgets' state)
    const hasDuplicate = useMemo(() => {
        if (!selectedCategoryId || !budgetMonth || !budgetYear) return false;
        
        return budgets.some(budget => 
            budget.category_id === parseInt(selectedCategoryId) &&
            budget.month === budgetMonth &&
            budget.year === budgetYear &&
            (!editingBudget || budget.id !== editingBudget.id)
        );
    }, [selectedCategoryId, budgetMonth, budgetYear, budgets, editingBudget]);

    // Gruppér budgetter efter periode for bedre visning
    const groupedBudgets = useMemo(() => {
        const grouped = budgets.reduce((acc, budget) => {
            const key = `${budget.year}-${budget.month}`;
            if (!acc[key]) acc[key] = [];
            acc[key].push(budget);
            return acc;
        }, {});

        // Sorter efter nyeste periode først
        return Object.keys(grouped)
            .sort((a, b) => b.localeCompare(a))
            .map(key => ({
                period: key,
                budgets: grouped[key].sort((a, b) => 
                    getCategoryName(a.category_id).localeCompare(getCategoryName(b.category_id))
                )
            }));
    }, [budgets, getCategoryName]);

    // Funktion til at hente alle budgetter for et givent år
    const fetchBudgetsForYear = useCallback(async (year) => {
        setFetchingBudgets(true);
        setLocalError(null);
        try {
            // Brug den eksisterende route med query parametre
            const response = await apiClient.get(`/budgets/?year=${year}`);
            if (!response.ok) {
                if (response.status === 404) {
                    // Hvis der ikke er budgetter for året, er det ok
                    setBudgets([]);
                    return;
                }
                const errorDetail = await response.json();
                throw new Error(`Kunne ikke hente budgetter for ${year}: ${errorDetail.detail || 'Ukendt fejl'}`);
            }
            const data = await response.json();
            
            // Transform data - tilføj month/year fra budget_date
            const transformedData = data.map(budget => {
                // Parse budget_date til month og year
                let month = '';
                let yearStr = '';
                if (budget.budget_date) {
                    const budgetDate = new Date(budget.budget_date);
                    month = String(budgetDate.getMonth() + 1).padStart(2, '0');
                    yearStr = String(budgetDate.getFullYear());
                }
                
                // Hent category_id fra categories array eller Category_idCategory
                const categoryId = budget.categories?.[0]?.idCategory || 
                                  budget.Category_idCategory || 
                                  budget.category_id;
                
                return {
                    ...budget,
                    id: budget.idBudget || budget.id,  // Normaliser ID
                    month: month,
                    year: yearStr,
                    category_id: categoryId
                };
            });
            
            setBudgets(transformedData);
        } catch (err) {
            setLocalError(err.message);
            setError?.(err.message);
            setBudgets([]);
        } finally {
            setFetchingBudgets(false);
        }
    }, [setError]);

    // Effect til at hente budgetter for det valgte viewYear
    useEffect(() => {
        fetchBudgetsForYear(selectedViewYear);
    }, [selectedViewYear, fetchBudgetsForYear]);

    const clearMessages = React.useCallback(() => {
        setLocalError(null);
        setLocalSuccessMessage(null);
        setError?.(null);
        setSuccessMessage?.(null);
    }, [setError, setSuccessMessage]);

    // Håndter initialBudget prop fra parent
    useEffect(() => {
        if (initialBudget) {
            const transformed = transformBudget(initialBudget);
            setEditingBudget(transformed);
        }
    }, [initialBudget, transformBudget]);
    
    // Reset form når vi skifter mellem editing og create mode
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
        
        clearMessages();
    }, [editingBudget, clearMessages]);

    const validateForm = () => {
        // Tjek at category_id er valgt (ikke tom string eller 0)
        const categoryIdNum = selectedCategoryId ? parseInt(selectedCategoryId, 10) : 0;
        if (!selectedCategoryId || selectedCategoryId === '' || isNaN(categoryIdNum) || categoryIdNum <= 0) {
            setLocalError('Vælg venligst en kategori.');
            return false;
        }

        if (!budgetAmountInput || !budgetMonth || !budgetYear) {
            setLocalError('Alle felter skal udfyldes.');
            return false;
        }

        const amount = parseFloat(budgetAmountInput);
        if (isNaN(amount) || amount <= 0) {
            setLocalError('Beløb skal være et positivt tal.');
            return false;
        }

        if (hasDuplicate) {
            setLocalError('Der findes allerede et budget for denne kategori i den valgte periode.');
            return false;
        }

        return true;
    };

    const handleSubmitBudget = async (e) => {
        e.preventDefault();
        clearMessages();

        if (!validateForm()) return;

        setIsSubmitting(true);

        // Valider og konverter category_id
        const categoryId = parseInt(selectedCategoryId, 10);
        if (isNaN(categoryId) || categoryId <= 0) {
            setLocalError('Vælg venligst en kategori.');
            setIsSubmitting(false);
            return;
        }

        const budgetData = {
            category_id: categoryId,
            amount: parseFloat(budgetAmountInput),
            month: budgetMonth,
            year: budgetYear
        };

        try {
            const isEditing = !!editingBudget;
            const response = isEditing
                ? await apiClient.put(`/budgets/${editingBudget.id}`, budgetData)
                : await apiClient.post('/budgets/', budgetData);

            const data = await response.json();

            if (!response.ok) {
                const errorMessage = data.detail 
                    ? (Array.isArray(data.detail) 
                        ? data.detail.map(d => d.msg).join(", ") 
                        : data.detail)
                    : "Ukendt fejl";
                throw new Error(errorMessage);
            }

            const successMessage = isEditing ? 'Budget opdateret!' : 'Budget oprettet!';
            setLocalSuccessMessage(successMessage);
            setSuccessMessage?.(successMessage);

            resetForm();
            
            // Genindlæs budgetter for det aktuelle visningsår
            await fetchBudgetsForYear(selectedViewYear);
            
            // Trigger parent callbacks
            if (isEditing) {
                onBudgetUpdated?.();
            } else {
                onBudgetAdded?.();
            }

        } catch (err) {
            const errorMessage = err.message || "Der opstod en uventet fejl.";
            setLocalError(errorMessage);
            setError?.(errorMessage);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDeleteBudget = async (budgetId) => {
        if (!window.confirm("Er du sikker på, at du vil slette dette budget?")) return;

        setIsSubmitting(true);
        try {
            const response = await apiClient.delete(`/budgets/${budgetId}`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            setLocalSuccessMessage('Budget slettet!');
            setSuccessMessage?.('Budget slettet!');
            
            // Genindlæs budgetter
            await fetchBudgetsForYear(selectedViewYear);
            
            // Trigger parent callback
            onBudgetDeleted?.();

        } catch (err) {
            const errorMessage = err.message || "Der opstod en uventet fejl ved sletning.";
            setLocalError(errorMessage);
            setError?.(errorMessage);
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
        clearMessages();
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

            <MessageDisplay message={localError} type="error" />
            <MessageDisplay message={localSuccessMessage} type="success" />

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
                        ⚠️ Der findes allerede et budget for denne kategori i den valgte periode.
                    </div>
                )}

                <div className="form-actions">
                    <button 
                        type="submit" 
                        disabled={isSubmitting || hasDuplicate}
                        className="submit-button"
                    >
                        {isSubmitting ? 'Gemmer...' : (editingBudget ? 'Opdater Budget' : 'Opret Budget')}
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
                                <option key={`view-year-${year}`} value={year}>{year}</option>
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
                                <h4 className="period-header">{getPeriodLabel(group.period)}</h4>
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