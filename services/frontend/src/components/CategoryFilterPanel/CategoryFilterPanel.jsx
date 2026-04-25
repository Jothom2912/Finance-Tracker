import React, { useMemo } from 'react';
import { MONTH_OPTIONS, getYearOptions, getMonthLabel } from '../../lib/formatters';
import './CategoryFilterPanel.css';

function CategoryFilterPanel({
  selectedMonth,
  setSelectedMonth,
  selectedYear,
  setSelectedYear,
  categories,
  selectedCategoryIds,
  setSelectedCategoryIds,
  typeFilter,
  setTypeFilter,
}) {
  const yearOptions = useMemo(() => getYearOptions(3), []);

  const filteredCategories = useMemo(() => {
    if (typeFilter === 'all') return categories;
    return categories.filter((cat) => cat.type === typeFilter);
  }, [categories, typeFilter]);

  const allSelected = filteredCategories.length > 0
    && filteredCategories.every((cat) => selectedCategoryIds.includes(cat.idCategory ?? cat.id));

  const handleToggleCategory = (catId) => {
    setSelectedCategoryIds((prev) =>
      prev.includes(catId) ? prev.filter((id) => id !== catId) : [...prev, catId],
    );
  };

  const handleToggleAll = () => {
    if (allSelected) {
      setSelectedCategoryIds([]);
    } else {
      setSelectedCategoryIds(filteredCategories.map((cat) => cat.idCategory ?? cat.id));
    }
  };

  return (
    <div className="category-filter-panel">
      <div className="filter-row">
        <div className="period-selector">
          <label htmlFor="cf-month">Måned:</label>
          <select
            id="cf-month"
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="period-select"
          >
            {MONTH_OPTIONS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>

          <label htmlFor="cf-year">År:</label>
          <select
            id="cf-year"
            value={selectedYear}
            onChange={(e) => setSelectedYear(e.target.value)}
            className="period-select"
          >
            {yearOptions.map((y) => (
              <option key={y} value={String(y)}>{y}</option>
            ))}
          </select>
        </div>

        <div className="type-filter">
          <label htmlFor="cf-type">Type:</label>
          <select
            id="cf-type"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="period-select"
          >
            <option value="expense">Udgifter</option>
            <option value="income">Indtægter</option>
            <option value="all">Alle</option>
          </select>
        </div>
      </div>

      <div className="category-multi-select">
        <div className="multi-select-header">
          <span className="multi-select-label">
            Kategorier ({selectedCategoryIds.length} af {filteredCategories.length} valgt)
          </span>
          <button
            type="button"
            className="toggle-all-btn"
            onClick={handleToggleAll}
          >
            {allSelected ? 'Fravælg alle' : 'Vælg alle'}
          </button>
        </div>

        <div className="category-chips">
          {filteredCategories.map((cat) => {
            const catId = cat.idCategory ?? cat.id;
            const isSelected = selectedCategoryIds.includes(catId);
            return (
              <button
                key={catId}
                type="button"
                className={`category-chip ${isSelected ? 'selected' : ''} ${cat.type}`}
                onClick={() => handleToggleCategory(catId)}
                title={`${cat.name} (${cat.type === 'expense' ? 'Udgift' : 'Indtægt'})`}
              >
                {cat.name}
              </button>
            );
          })}
          {filteredCategories.length === 0 && (
            <span className="no-categories-msg">Ingen kategorier fundet</span>
          )}
        </div>
      </div>

      <div className="active-filter-summary">
        {getMonthLabel(selectedMonth)} {selectedYear}
        {selectedCategoryIds.length > 0 && selectedCategoryIds.length < filteredCategories.length && (
          <span className="filter-badge">{selectedCategoryIds.length} kategorier filtreret</span>
        )}
      </div>
    </div>
  );
}

export default CategoryFilterPanel;
