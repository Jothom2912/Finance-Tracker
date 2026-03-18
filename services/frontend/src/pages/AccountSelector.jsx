import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { fetchAccounts, createAccount } from '../api/accounts';
import '../styles/AccountSelector.css';

export default function AccountSelector() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newAccountName, setNewAccountName] = useState('');
  const [error, setError] = useState(null);

  const selectAccount = useCallback((accountId) => {
    localStorage.setItem('account_id', String(accountId));
    navigate('/dashboard');
  }, [navigate]);

  useEffect(() => {
    if (!user) return;

    (async () => {
      try {
        const data = await fetchAccounts();
        setAccounts(data);
      } catch (err) {
        setError(err.message || 'Forbindelsesfejl - kan ikke nå backend');
      } finally {
        setLoading(false);
      }
    })();
  }, [user, selectAccount]);

  const handleCreateAccount = async () => {
    if (!newAccountName.trim()) {
      setError('Kontonavn kan ikke være tomt');
      return;
    }

    try {
      const newAccount = await createAccount({ name: newAccountName.trim() });
      setAccounts((prev) => [...prev, newAccount]);
      setNewAccountName('');
      setShowCreateForm(false);
      setError(null);
      selectAccount(newAccount.idAccount || newAccount.id);
    } catch (err) {
      setError(err.message || 'Forbindelsesfejl - kan ikke nå backend');
    }
  };

  if (loading) {
    return (
      <div className="account-selector-container">
        <div className="account-selector-card">
          <div className="account-selector-loading">Indlæser konti...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="account-selector-container">
      <div className="account-selector-card">
        <div className="account-selector-header">
          <h1>Vælg eller opret en konto</h1>
          <p>Hej {user?.username}!</p>
        </div>

        {error && <div className="error-message">{error}</div>}

        {accounts.length > 0 && (
          <div className="accounts-list" data-cy="account-list">
            <h2>Dine konti:</h2>
            {accounts.map((account, index) => (
              <button
                key={account.idAccount || account.id || `account-${index}`}
                onClick={() => selectAccount(account.idAccount || account.id)}
                className="account-button"
                data-cy="account-button"
              >
                {account.name}
              </button>
            ))}
          </div>
        )}

        {accounts.length === 0 && !showCreateForm && (
          <p className="no-accounts-message">Du har ingen konti endnu. Opret en for at komme i gang!</p>
        )}

        <div className="create-account-section">
          <button
            onClick={() => { setShowCreateForm(!showCreateForm); setError(null); }}
            className="create-account-button"
            data-cy="create-account-button"
          >
            {showCreateForm ? 'Annuller' : '+ Opret ny konto'}
          </button>

          {showCreateForm && (
            <div className="create-account-form">
              <input
                type="text"
                placeholder="Kontonavn (f.eks. 'Min privat konto')"
                value={newAccountName}
                onChange={(e) => setNewAccountName(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleCreateAccount()}
                autoFocus
                data-cy="account-name-input"
              />
              <button onClick={handleCreateAccount} className="create-account-submit-button" data-cy="create-account-submit-button">
                Opret konto
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
