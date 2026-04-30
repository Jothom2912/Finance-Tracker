// frontend/src/components/CategoryExpensesList.js

import './CategoryExpensesList.css'; // Opret denne CSS-fil

function CategoryExpensesList({ data, totalExpenses, formatAmount }) {
  if (!data || data.length === 0) {
    return <p className="no-expenses-message">Ingen udgifter registreret i denne periode.</p>;
  }

  return (
    <div className="category-list-container">
      <ul className="category-list">
        {data.map((item, index) => {
          if (!item || !item.name || !item.color) {
            console.warn('Invalid item in render:', item);
            return null;
          }

          return (
            <li key={`${item.name}-${index}`} className="category-item">
              <div className="category-name">
                <span
                  className="category-color-dot"
                  style={{ backgroundColor: item.color }}
                ></span>
                <span>{item.name}</span>
                <span className="category-percentage">({item.percentage}%)</span>
              </div>
              <span className="category-amount">{formatAmount(item.value)}</span>
            </li>
          );
        })}
      </ul>
      <div className="category-total">
        <strong>I alt: {formatAmount(Math.abs(totalExpenses || 0))}</strong>
      </div>
    </div>
  );
}

export default CategoryExpensesList;