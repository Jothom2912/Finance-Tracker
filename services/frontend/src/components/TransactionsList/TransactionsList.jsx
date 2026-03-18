import React from 'react';
import { formatDate } from '../../lib/formatters';
import './TransactionsList.css';

function TransactionsList({
  transactions = [],
  onEdit,
  onDelete,
  onCreateTransaction,
  categories = [],
}) {
  const getCategoryName = (id) => {
    if (!id) return 'Ukendt';
    const category = categories.find((cat) => cat.id === id || cat.idCategory === id);
    return category ? category.name : 'Ukendt';
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
    <div className="transactions-list-container" data-cy="transaction-list">
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
            const transactionId = transaction.idTransaction || transaction.id;
            return (
              <tr key={transactionId} className={transaction.type === 'expense' ? 'expense-row' : 'income-row'}>
                <td>{formatDate(transaction.date)}</td>
                <td>{transaction.description}</td>
                <td className={transaction.type === 'expense' ? 'expense-amount' : 'income-amount'}>
                  {transaction.type === 'expense' ? '-' : '+'}
                  {Math.abs(transaction.amount).toFixed(2)} DKK
                </td>
                <td>{transaction.type === 'expense' ? 'Udgift' : 'Indkomst'}</td>
                <td>{getCategoryName(transaction.category_id || transaction.Category_idCategory)}</td>
                <td className="transaction-actions">
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
