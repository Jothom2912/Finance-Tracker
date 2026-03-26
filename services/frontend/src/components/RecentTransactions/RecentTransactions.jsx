import React from 'react';
import { Link } from 'react-router-dom';
import { formatAmount, formatDate } from '../../lib/formatters';
import './RecentTransactions.css';

function RecentTransactions({ transactions }) {
  if (!transactions || transactions.length === 0) {
    return (
      <div className="recent-transactions-section">
        <h3>Seneste transaktioner</h3>
        <p className="no-data-message">
          Ingen transaktioner endnu.{' '}
          <Link to="/transactions" className="empty-state-link">
            Tilføj din første
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="recent-transactions-section">
      <div className="recent-transactions-header">
        <h3>Seneste transaktioner</h3>
        <Link to="/transactions" className="view-all-link">
          Se alle
        </Link>
      </div>
      <ul className="recent-transactions-list">
        {transactions.map((tx) => {
          const isExpense = tx.type === 'expense' || tx.amount < 0;
          return (
            <li key={tx.id} className="recent-transaction-item">
              <div className="recent-tx-left">
                <div className="recent-tx-desc-row">
                  <span className="recent-tx-description">
                    {tx.description || 'Ingen beskrivelse'}
                  </span>
                  {tx.categorizationTier && (
                    <span className={`tier-badge tier-${tx.categorizationTier}`}>
                      {tx.categorizationTier === 'rule' ? 'auto' : tx.categorizationTier}
                    </span>
                  )}
                </div>
                <span className="recent-tx-date">{formatDate(tx.date)}</span>
              </div>
              <span className={`recent-tx-amount ${isExpense ? 'expense' : 'income'}`}>
                {isExpense ? '-' : '+'}{formatAmount(Math.abs(tx.amount))}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default RecentTransactions;
