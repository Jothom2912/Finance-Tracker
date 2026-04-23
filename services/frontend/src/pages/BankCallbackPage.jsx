import React from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import '../styles/BankCallbackPage.css';

const ERROR_MESSAGES = {
  auth_rejected: 'Bankforbindelsen blev afvist. Prøv igen eller vælg en anden bank.',
  missing_code: 'Autorisationskoden mangler fra banken. Prøv igen.',
  unknown_state: 'Autorisationen er udløbet. Start forbindelsen forfra.',
  config_error: 'Bankforbindelsen er midlertidigt utilgængelig. Kontakt support.',
  upstream_unavailable: 'Banken kunne ikke kontaktes. Prøv igen om et øjeblik.',
};

function BankCallbackPage() {
  const [searchParams] = useSearchParams();
  const status = searchParams.get('status');
  const code = searchParams.get('code');
  const connections = searchParams.get('connections');
  const ref = searchParams.get('ref');

  const isSuccess = status === 'success';
  const errorMessage = code ? (ERROR_MESSAGES[code] || 'Der opstod en uventet fejl.') : null;

  return (
    <div className="bank-callback-container">
      <div className="bank-callback-card">
        {isSuccess ? (
          <>
            <div className="bank-callback-icon bank-callback-icon--success">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <h1>Bank forbundet</h1>
            <p className="bank-callback-detail">
              {connections
                ? `${connections} bankkonto${connections !== '1' ? 'er' : ''} er nu forbundet.`
                : 'Din bankkonto er nu forbundet.'}
            </p>
            <p className="bank-callback-hint">
              Dine transaktioner synkroniseres automatisk.
            </p>
          </>
        ) : (
          <>
            <div className="bank-callback-icon bank-callback-icon--error">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </div>
            <h1>Forbindelse fejlede</h1>
            <p className="bank-callback-detail">{errorMessage}</p>
            {ref && (
              <p className="bank-callback-ref">Reference: {ref}</p>
            )}
          </>
        )}

        <Link to="/dashboard" className="bank-callback-button">
          Gå til dashboard
        </Link>
      </div>
    </div>
  );
}

export default BankCallbackPage;
