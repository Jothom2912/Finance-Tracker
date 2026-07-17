
import { useState } from 'react';
import { formatDate } from '../../lib/formatters';
import './TransactionsList.css';

/**
 * Inline-rekategorisering (F1-03): kategoricellen kan redigeres direkte
 * med én dropdown (optgroup per kategori, valg = underkategori), så en
 * rettelse ikke kræver hele redigerings-modalen. Rettelsen pinner
 * tier=manual server-side og fodrer feedback-loopet, der lærer
 * merchant→kategori til fremtidige imports.
 */
function TransactionsList({
  transactions = [],
  onEdit,
  onDelete,
  onCreateTransaction,
  onQuickCategorize,
  categories = [],
  allSubcategories = [],
}) {
  const [editingRowId, setEditingRowId] = useState(null);

  const getCategoryName = (transaction) => {
    if (transaction.category_name) return transaction.category_name;
    const id = transaction.category_id;
    if (!id) return 'Ukendt';
    const category = categories.find((cat) => cat.id === id);
    return category ? category.name : 'Ukendt';
  };

  const subcategoriesByCategory = allSubcategories.reduce((acc, sub) => {
    (acc[sub.category_id] = acc[sub.category_id] || []).push(sub);
    return acc;
  }, {});

  const currentValue = (transaction) =>
    transaction.category_id
      ? `${transaction.category_id}:${transaction.subcategory_id || ''}`
      : '';

  const handleCategorySelect = async (transaction, value) => {
    setEditingRowId(null);
    if (!value || value === currentValue(transaction)) return;
    const [catPart, subPart] = value.split(':');
    const categoryId = parseInt(catPart, 10);
    const category = categories.find((cat) => cat.id === categoryId);
    await onQuickCategorize(transaction, {
      category_id: categoryId,
      category_name: category?.name || null,
      subcategory_id: subPart ? parseInt(subPart, 10) : null,
    });
  };

  if (transactions.length === 0) {
    return (
      <div className="transactions-empty-state">
        <p>Ingen transaktioner fundet for de valgte filtre.</p>
        <button className="empty-state-action" onClick={onCreateTransaction}>
          Tilføj din første transaktion
        </button>
      </div>
    );
  }

  return (
    <div className="transactions-list-container">
      <table className="transactions-table">
        <thead>
          <tr>
            <th>Dato</th>
            <th>Beskrivelse</th>
            <th>Beløb</th>
            <th>Type</th>
            <th>Kategori</th>
            <th>Handlinger</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((transaction) => {
            const transactionId = transaction.id;
            const isEditingCategory = editingRowId === transactionId;
            return (
              <tr key={transactionId} className={transaction.type === 'expense' ? 'expense-row' : 'income-row'}>
                <td data-label="Dato">{formatDate(transaction.date)}</td>
                <td data-label="Beskrivelse">{transaction.description}</td>
                <td
                  data-label="Beløb"
                  className={transaction.type === 'expense' ? 'expense-amount' : 'income-amount'}
                >
                  {transaction.type === 'expense' ? '-' : '+'}
                  {Math.abs(transaction.amount).toFixed(2)} DKK
                </td>
                <td data-label="Type">{transaction.type === 'expense' ? 'Udgift' : 'Indkomst'}</td>
                <td data-label="Kategori">
                  {isEditingCategory && onQuickCategorize ? (
                    <select
                      className="inline-category-select"
                      autoFocus
                      defaultValue={currentValue(transaction)}
                      onChange={(e) => handleCategorySelect(transaction, e.target.value)}
                      onBlur={() => setEditingRowId(null)}
                      aria-label={`Ret kategori for ${transaction.description}`}
                    >
                      <option value="">Vælg kategori…</option>
                      {categories.map((cat) => (
                        <optgroup key={cat.id} label={cat.name}>
                          <option value={`${cat.id}:`}>{cat.name} (ingen underkategori)</option>
                          {(subcategoriesByCategory[cat.id] || []).map((sub) => (
                            <option key={sub.id} value={`${cat.id}:${sub.id}`}>
                              {sub.name}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  ) : (
                    <button
                      type="button"
                      className="inline-category-button"
                      onClick={() => onQuickCategorize && setEditingRowId(transactionId)}
                      disabled={!onQuickCategorize}
                      title="Klik for at rette kategori"
                    >
                      {getCategoryName(transaction)}
                      {transaction.subcategory_name && (
                        <span className="subcategory-label"> › {transaction.subcategory_name}</span>
                      )}
                    </button>
                  )}
                </td>
                <td data-label="Handlinger" className="transaction-actions">
                  <button className="button secondary small-button" onClick={() => onEdit(transaction)}>Rediger</button>
                  <button className="button danger small-button" onClick={() => onDelete(transactionId)}>Slet</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default TransactionsList;
