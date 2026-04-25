import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { fetchAccounts, createAccount, updateAccount } from '../api/accounts';
import '../styles/AccountSelector.css';

const START_DAY_OPTIONS = Array.from({ length: 28 }, (_, i) => i + 1);

export default function AccountSelector() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newAccountName, setNewAccountName] = useState('');
  const [error, setError] = useState(null);

  const selectAccount = useCallback((accountId, accountName) => {
    localStorage.setItem('account_id', String(accountId));
    localStorage.setItem('account_name', accountName || 'Default');
    navigate('/dashboard');
  }, [navigate]);

  const handleStartDayChange = useCallback(async (account, newDay) => {
    try {
      await updateAccount(account.idAccount || account.id, {
        name: account.name,
        saldo: account.saldo,
        budget_start_day: newDay,
      });
      setAccounts((prev) =>
        prev.map((a) =>
          (a.idAccount || a.id) === (account.idAccount || account.id)
            ? { ...a, budget_start_day: newDay }
            : a
        )
      );
    } catch (err) {
      setError(err.message || 'Kunne ikke opdatere budgetperiode.');
    }
  }, []);

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
      selectAccount(newAccount.idAccount || newAccount.id, newAccount.name);
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
          <div className="accounts-list">
            <h2>Dine konti:</h2>
            {accounts.map((account, index) => (
              <div
                key={account.idAccount || account.id || `account-${index}`}
                className="account-card"
              >
                <button
                  onClick={() => selectAccount(account.idAccount || account.id, account.name)}
                  className="account-button"
                >
                  {account.name}
                </button>
                <div className="account-settings-row">
                  <label className="start-day-label">
                    Budgetperiode starter d.
                    <select
                      className="start-day-select"
                      value={account.budget_start_day ?? 1}
                      onChange={(e) =>
                        handleStartDayChange(account, parseInt(e.target.value, 10))
                      }
                      onClick={(e) => e.stopPropagation()}
                    >
                      {START_DAY_OPTIONS.map((d) => (
                        <option key={d} value={d}>{d}.</option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>
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
              />
              <button onClick={handleCreateAccount} className="create-account-submit-button">
                Opret konto
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
