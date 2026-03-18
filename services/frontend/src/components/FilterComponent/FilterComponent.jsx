// src/components/FilterComponent/FilterComponent.js
import React from 'react';
// import './FilterComponent.css'; // Opret denne fil for specifik styling

function FilterComponent({
    filterStartDate,
    setFilterStartDate,
    filterEndDate,
    setFilterEndDate,
    selectedCategory,
    setSelectedCategory,
    categories,
    onFilter
}) {
    return (
        <div className="filter-component-container"> {/* Ny container klasse */}
            <h4>Filtrer Transaktioner</h4>
            <div className="filter-inputs"> {/* Gruppe for filter inputs */}
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
                            <option key={cat.idCategory || cat.id || `category-${index}`} value={cat.idCategory || cat.id}>
                                {cat.name}
                            </option>
                        ))}
                    </select>
                </div>
            </div>
            <button className="button secondary" onClick={onFilter}>Anvend Filter</button>
        </div>
    );
}

export default FilterComponent;