import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchMonthlyBudget,
  createMonthlyBudget,
  updateMonthlyBudget,
  deleteMonthlyBudget,
  copyMonthlyBudget,
  fetchMonthlyBudgetSummary,
} from '../../api/monthlyBudgets';
import { useCategories } from '../../hooks/useCategories';
import { useNotifications } from '../../hooks/useNotifications';
import { getMonthName, MONTH_OPTIONS } from '../../lib/formatters';
import './BudgetPage.css';

function BudgetPage() {
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());

  const { categories, loading: catsLoading } = useCategories();
  const { showError, showSuccess } = useNotifications();

  const [budget, setBudget] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [editLines, setEditLines] = useState([]);
  const [isEditing, setIsEditing] = useState(false);
  const [addCategoryId, setAddCategoryId] = useState('');

  const accountId = localStorage.getItem('account_id');

  const expenseCategories = useMemo(
    () => categories.filter((c) => c.type === 'expense'),
    [categories]
  );

  const usedCategoryIds = useMemo(
    () => new Set(editLines.map((l) => l.category_id)),
    [editLines]
  );

  const availableCategories = useMemo(
    () => expenseCategories.filter((c) => !usedCategoryIds.has(c.idCategory)),
    [expenseCategories, usedCategoryIds]
  );

  const loadData = useCallback(async () => {
    if (!accountId) return;
    setLoading(true);
    try {
      const [budgetData, summaryData] = await Promise.all([
        fetchMonthlyBudget({ month, year }),
        fetchMonthlyBudgetSummary({ month, year }),
      ]);
      setBudget(budgetData);
      setSummary(summaryData);
      if (budgetData?.lines) {
        setEditLines(
          budgetData.lines.map((l) => ({
            category_id: l.category_id,
            category_name: l.category_name,
            amount: l.amount,
          }))
        );
      } else {
        setEditLines([]);
      }
      setIsEditing(false);
    } catch (err) {
      showError(err.message || 'Kunne ikke hente budget-data.');
    } finally {
      setLoading(false);
    }
  }, [accountId, month, year, showError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const lines = editLines
        .filter((l) => l.amount > 0)
        .map((l) => ({
          category_id: l.category_id,
          amount: parseFloat(l.amount),
        }));

      if (budget?.id) {
        await updateMonthlyBudget(budget.id, { lines });
        showSuccess('Budget opdateret.');
      } else {
        await createMonthlyBudget({ month, year, lines });
        showSuccess('Budget oprettet.');
      }
      await loadData();
    } catch (err) {
      showError(err.message || 'Kunne ikke gemme budget.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!budget?.id) return;
    if (!window.confirm('Er du sikker på at du vil slette hele budgettet for denne måned?')) return;
    setSaving(true);
    try {
      await deleteMonthlyBudget(budget.id);
      showSuccess('Budget slettet.');
      await loadData();
    } catch (err) {
      showError(err.message || 'Kunne ikke slette budget.');
    } finally {
      setSaving(false);
    }
  };

  const handleCopyFromPrevious = async () => {
    const prevMonth = month === 1 ? 12 : month - 1;
    const prevYear = month === 1 ? year - 1 : year;
    setSaving(true);
    try {
      await copyMonthlyBudget({
        sourceMonth: prevMonth,
        sourceYear: prevYear,
        targetMonth: month,
        targetYear: year,
      });
      showSuccess(`Budget kopieret fra ${getMonthName(prevMonth)} ${prevYear}.`);
      await loadData();
    } catch (err) {
      showError(err.message || 'Kunne ikke kopiere budget.');
    } finally {
      setSaving(false);
    }
  };

  const handleLineAmountChange = (index, value) => {
    setEditLines((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], amount: value };
      return copy;
    });
    if (!isEditing) setIsEditing(true);
  };

  const handleRemoveLine = (index) => {
    setEditLines((prev) => prev.filter((_, i) => i !== index));
    if (!isEditing) setIsEditing(true);
  };

  const handleAddLine = () => {
    if (!addCategoryId) return;
    const cat = expenseCategories.find((c) => c.idCategory === parseInt(addCategoryId, 10));
    if (!cat) return;
    setEditLines((prev) => [
      ...prev,
      { category_id: cat.idCategory, category_name: cat.name, amount: 0 },
    ]);
    setAddCategoryId('');
    if (!isEditing) setIsEditing(true);
  };

  const handleCancelEdit = () => {
    if (budget?.lines) {
      setEditLines(
        budget.lines.map((l) => ({
          category_id: l.category_id,
          category_name: l.category_name,
          amount: l.amount,
        }))
      );
    } else {
      setEditLines([]);
    }
    setIsEditing(false);
  };

  if (!accountId) {
    return (
      <div className="budget-page">
        <div className="budget-no-account" data-cy="no-account-state">
          <div className="no-account-icon">&#128179;</div>
          <h2>Ingen konto valgt</h2>
          <p>Vælg en konto for at se og administrere dine budgetter.</p>
          <Link to="/account-selector" className="btn-primary">Gå til kontoer</Link>
        </div>
      </div>
    );
  }

  const totalEdited = editLines.reduce((s, l) => s + (parseFloat(l.amount) || 0), 0);

  return (
    <div className="budget-page" data-cy="budget-page">
      {/* Header */}
      <div className="budget-page-header">
        <div className="header-content">
          <h1>Månedligt Budget</h1>
          <p className="header-subtitle">
            Planlæg og følg dine udgifter måned for måned
          </p>
        </div>
      </div>

      {/* Period selector */}
      <div className="budget-period-selector" data-cy="period-selector">
        <button
          className="period-nav-btn"
          onClick={() => {
            if (month === 1) { setMonth(12); setYear(year - 1); }
            else setMonth(month - 1);
          }}
          title="Forrige måned"
        >
          &#8249;
        </button>

        <div className="period-selects">
          <select
            value={month}
            onChange={(e) => setMonth(parseInt(e.target.value, 10))}
            data-cy="budget-month"
          >
            {MONTH_OPTIONS.map((m) => (
              <option key={m.value} value={parseInt(m.value, 10)}>{m.label}</option>
            ))}
          </select>
          <select
            value={year}
            onChange={(e) => setYear(parseInt(e.target.value, 10))}
            data-cy="budget-year"
          >
            {Array.from({ length: 5 }, (_, i) => now.getFullYear() - 2 + i).map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        <button
          className="period-nav-btn"
          onClick={() => {
            if (month === 12) { setMonth(1); setYear(year + 1); }
            else setMonth(month + 1);
          }}
          title="Næste måned"
        >
          &#8250;
        </button>
      </div>

      {loading || catsLoading ? (
        <div className="budget-loading">Henter budget...</div>
      ) : (
        <>
          {/* Summary cards */}
          {summary && (
            <div className="budget-summary-cards" data-cy="budget-summary">
              <div className="summary-card">
                <span className="summary-label">Total budget</span>
                <span className="summary-value">{formatKr(summary.total_budget)}</span>
              </div>
              <div className="summary-card">
                <span className="summary-label">Forbrug</span>
                <span className="summary-value spent">{formatKr(summary.total_spent)}</span>
              </div>
              <div className="summary-card">
                <span className="summary-label">Resterende</span>
                <span className={`summary-value ${summary.total_remaining < 0 ? 'over' : 'under'}`}>
                  {formatKr(summary.total_remaining)}
                </span>
              </div>
              <div className="summary-card">
                <span className="summary-label">Over budget</span>
                <span className={`summary-value ${summary.over_budget_count > 0 ? 'over' : ''}`}>
                  {summary.over_budget_count} {summary.over_budget_count === 1 ? 'kategori' : 'kategorier'}
                </span>
              </div>
            </div>
          )}

          {/* Budget lines */}
          <div className="budget-lines-card" data-cy="budget-lines">
            <div className="lines-header">
              <h2>Budget-linjer</h2>
              <div className="lines-actions">
                {!budget && (
                  <button
                    className="btn-secondary"
                    onClick={handleCopyFromPrevious}
                    disabled={saving}
                    data-cy="copy-budget-btn"
                  >
                    Kopiér fra forrige måned
                  </button>
                )}
                {isEditing && (
                  <>
                    <button
                      className="btn-ghost"
                      onClick={handleCancelEdit}
                      disabled={saving}
                    >
                      Annuller
                    </button>
                    <button
                      className="btn-primary"
                      onClick={handleSave}
                      disabled={saving}
                      data-cy="save-budget-btn"
                    >
                      {saving ? 'Gemmer...' : 'Gem ændringer'}
                    </button>
                  </>
                )}
                {budget?.id && !isEditing && (
                  <button
                    className="btn-danger-ghost"
                    onClick={handleDelete}
                    disabled={saving}
                    data-cy="delete-budget-btn"
                  >
                    Slet budget
                  </button>
                )}
              </div>
            </div>

            {editLines.length === 0 && !isEditing ? (
              <div className="budget-empty" data-cy="budget-empty">
                <p>Ingen budget for {getMonthName(month)} {year}.</p>
                <p>Tilføj kategorier nedenfor, eller kopiér fra forrige måned.</p>
              </div>
            ) : (
              <div className="lines-table-wrapper">
                <table className="lines-table">
                  <thead>
                    <tr>
                      <th>Kategori</th>
                      <th className="num">Budget</th>
                      <th className="num">Forbrug</th>
                      <th className="num">Resterende</th>
                      <th className="progress-col">Status</th>
                      <th className="action-col"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {editLines.map((line, idx) => {
                      const summaryItem = summary?.items?.find(
                        (it) => it.category_id === line.category_id
                      );
                      const spent = summaryItem?.spent_amount ?? 0;
                      const budgetAmt = parseFloat(line.amount) || 0;
                      const remaining = budgetAmt - spent;
                      const pct = budgetAmt > 0 ? Math.min((spent / budgetAmt) * 100, 150) : 0;
                      const isOver = remaining < 0;

                      return (
                        <tr key={line.category_id} data-cy={`budget-line-${line.category_id}`}>
                          <td className="cat-name">{line.category_name || `Kategori #${line.category_id}`}</td>
                          <td className="num">
                            <input
                              type="number"
                              className="inline-amount"
                              value={line.amount}
                              min="0"
                              step="100"
                              onChange={(e) => handleLineAmountChange(idx, e.target.value)}
                              data-cy={`amount-input-${line.category_id}`}
                            />
                          </td>
                          <td className="num spent-cell">{formatKr(spent)}</td>
                          <td className={`num ${isOver ? 'over' : 'under'}`}>{formatKr(remaining)}</td>
                          <td className="progress-col">
                            <div className="progress-bar-bg">
                              <div
                                className={`progress-bar-fill ${isOver ? 'over' : pct > 80 ? 'warn' : 'ok'}`}
                                style={{ width: `${Math.min(pct, 100)}%` }}
                              />
                            </div>
                            <span className={`pct-label ${isOver ? 'over' : ''}`}>{Math.round(pct)}%</span>
                          </td>
                          <td className="action-col">
                            <button
                              className="remove-line-btn"
                              onClick={() => handleRemoveLine(idx)}
                              title="Fjern linje"
                            >
                              &times;
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  {editLines.length > 0 && (
                    <tfoot>
                      <tr className="totals-row">
                        <td>Total</td>
                        <td className="num">{formatKr(totalEdited)}</td>
                        <td className="num spent-cell">{formatKr(summary?.total_spent ?? 0)}</td>
                        <td className={`num ${(totalEdited - (summary?.total_spent ?? 0)) < 0 ? 'over' : 'under'}`}>
                          {formatKr(totalEdited - (summary?.total_spent ?? 0))}
                        </td>
                        <td></td>
                        <td></td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            )}

            {/* Add category row */}
            <div className="add-line-row" data-cy="add-line">
              <select
                value={addCategoryId}
                onChange={(e) => setAddCategoryId(e.target.value)}
                data-cy="add-category-select"
              >
                <option value="">Tilføj kategori...</option>
                {availableCategories.map((c) => (
                  <option key={c.idCategory} value={c.idCategory}>{c.name}</option>
                ))}
              </select>
              <button
                className="btn-secondary btn-sm"
                onClick={handleAddLine}
                disabled={!addCategoryId}
                data-cy="add-line-btn"
              >
                Tilføj
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function formatKr(amount) {
  return new Intl.NumberFormat('da-DK', {
    style: 'currency',
    currency: 'DKK',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export default BudgetPage;
