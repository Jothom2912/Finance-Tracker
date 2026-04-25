import React, { useState, useEffect, useCallback } from 'react';
import { Check, X } from 'lucide-react';
import { fetchConnections, syncConnection } from '../../api/bank';
import './BankConnectionWidget.css';

function formatTimeAgo(isoString) {
  if (!isoString) return 'Aldrig synkroniseret';
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Lige nu';
  if (mins < 60) return `${mins} min siden`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} time${hours > 1 ? 'r' : ''} siden`;
  const days = Math.floor(hours / 24);
  return `${days} dag${days > 1 ? 'e' : ''} siden`;
}

function BankConnectionWidget({ onSyncComplete }) {
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncingId, setSyncingId] = useState(null);
  const [syncResult, setSyncResult] = useState(null);

  const loadConnections = useCallback(async () => {
    try {
      const data = await fetchConnections();
      setConnections(data);
    } catch {
      setConnections([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConnections();
  }, [loadConnections]);

  useEffect(() => {
    if (!syncResult) return;
    const timer = setTimeout(() => setSyncResult(null), 8000);
    return () => clearTimeout(timer);
  }, [syncResult]);

  async function handleSync(connectionId) {
    if (syncingId) return;
    setSyncingId(connectionId);
    setSyncResult(null);

    try {
      const result = await syncConnection(connectionId);
      setSyncResult({
        connectionId,
        type: 'success',
        message: `${result.new_imported} nye, ${result.duplicates_skipped} duplikater`,
        detail: result.total_fetched > 0
          ? `${result.total_fetched} transaktioner hentet`
          : 'Ingen nye transaktioner',
      });
      await loadConnections();
      if (onSyncComplete) await onSyncComplete();
    } catch (err) {
      setSyncResult({
        connectionId,
        type: 'error',
        message: err.message || 'Sync fejlede',
      });
    } finally {
      setSyncingId(null);
    }
  }

  if (loading) {
    return (
      <div className="bank-widget">
        <div className="bank-widget-header">
          <h3>Bankforbindelser</h3>
        </div>
        <div className="bank-empty-state">
          <span className="bank-spinner" />
        </div>
      </div>
    );
  }

  const activeConnections = connections.filter((c) => c.status === 'active');

  return (
    <div className="bank-widget">
      <div className="bank-widget-header">
        <h3>Bankforbindelser</h3>
      </div>

      {activeConnections.length === 0 ? (
        <div className="bank-empty-state">
          <p>Ingen banker forbundet endnu.</p>
        </div>
      ) : (
        <div className="bank-connection-list">
          {activeConnections.map((conn) => (
            <div key={conn.id}>
              <div className="bank-connection-row">
                <div className="bank-icon">
                  {(conn.bank_name || '?').charAt(0)}
                </div>
                <div className="bank-connection-info">
                  <div className="bank-connection-name">
                    {conn.bank_name}{' '}
                    {conn.bank_country && `(${conn.bank_country})`}
                  </div>
                  <div className="bank-connection-meta">
                    <span
                      className={`bank-status-dot ${conn.status}`}
                      title={conn.status}
                    />
                    <span>
                      {conn.iban
                        ? `···${conn.iban.slice(-4)}`
                        : 'Konto forbundet'}
                    </span>
                    <span>·</span>
                    <span>{formatTimeAgo(conn.last_synced_at)}</span>
                  </div>
                </div>
                <button
                  className={`bank-sync-btn ${syncingId === conn.id ? 'syncing' : ''}`}
                  onClick={() => handleSync(conn.id)}
                  disabled={syncingId !== null}
                >
                  {syncingId === conn.id ? (
                    <>
                      <span className="bank-spinner" />
                      Synkroniserer...
                    </>
                  ) : (
                    'Sync nu'
                  )}
                </button>
              </div>

              {syncResult && syncResult.connectionId === conn.id && (
                <div className={`bank-sync-result ${syncResult.type}`}>
                  {syncResult.type === 'success' ? (
                    <Check aria-hidden="true" size={14} />
                  ) : (
                    <X aria-hidden="true" size={14} />
                  )}{' '}
                  {syncResult.message}
                  {syncResult.detail && (
                    <span style={{ opacity: 0.7 }}>
                      {' '}
                      — {syncResult.detail}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default BankConnectionWidget;
