import React from 'react';
import { formatLocalISODate } from '../../lib/formatters';

// Presets describe a start/end date range relative to "today". Evaluated at
// click time, not at module load, so the "current month" preset stays correct
// across day/month rollovers without requiring a remount.
const DATE_PRESETS = [
  {
    id: 'this-month',
    label: 'Denne måned',
    range: () => {
      const now = new Date();
      return [
        new Date(now.getFullYear(), now.getMonth(), 1),
        new Date(now.getFullYear(), now.getMonth() + 1, 0),
      ];
    },
  },
  {
    id: 'last-30-days',
    label: 'Seneste 30 dage',
    range: () => {
      const end = new Date();
      const start = new Date();
      start.setDate(start.getDate() - 29);
      return [start, end];
    },
  },
  {
    id: 'last-month',
    label: 'Sidste måned',
    range: () => {
      const now = new Date();
      return [
        new Date(now.getFullYear(), now.getMonth() - 1, 1),
        new Date(now.getFullYear(), now.getMonth(), 0),
      ];
    },
  },
  {
    id: 'year-to-date',
    label: 'År til dato',
    range: () => {
      const now = new Date();
      return [new Date(now.getFullYear(), 0, 1), now];
    },
  },
];

function isActivePreset(preset, startISO, endISO) {
  const [start, end] = preset.range();
  return formatLocalISODate(start) === startISO && formatLocalISODate(end) === endISO;
}

function FilterComponent({
  filterStartDate,
  setFilterStartDate,
  filterEndDate,
  setFilterEndDate,
  selectedCategory,
  setSelectedCategory,
  categories,
  onFilter,
}) {
  const applyPreset = (preset) => {
    const [start, end] = preset.range();
    setFilterStartDate(formatLocalISODate(start));
    setFilterEndDate(formatLocalISODate(end));
  };

  return (
    <div className="filter-component-container">
      <h4>Filtrer Transaktioner</h4>

      <div
        className="filter-presets"
        role="group"
        aria-label="Hurtigt-valg af datoperiode"
      >
        {DATE_PRESETS.map((preset) => {
          const active = isActivePreset(preset, filterStartDate, filterEndDate);
          return (
            <button
              key={preset.id}
              type="button"
              className={`filter-preset-chip${active ? ' active' : ''}`}
              aria-pressed={active}
              onClick={() => applyPreset(preset)}
            >
              {preset.label}
            </button>
          );
        })}
      </div>

      <div className="filter-inputs">
        <div className="form-group">
          <label htmlFor="startDate">Fra dato:</label>
          <input
            type="date"
            id="startDate"
            value={filterStartDate}
            onChange={(e) => setFilterStartDate(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor="endDate">Til dato:</label>
          <input
            type="date"
            id="endDate"
            value={filterEndDate}
            onChange={(e) => setFilterEndDate(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor="filterCategory">Kategori:</label>
          <select
            id="filterCategory"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
          >
            <option value="">Alle Kategorier</option>
            {categories.map((cat, index) => (
              <option
                key={cat.idCategory || cat.id || `category-${index}`}
                value={cat.idCategory || cat.id}
              >
                {cat.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <button className="button secondary" onClick={onFilter}>
        Anvend Filter
      </button>
    </div>
  );
}

export default FilterComponent;
