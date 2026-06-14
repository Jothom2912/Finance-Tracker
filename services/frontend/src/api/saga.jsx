import apiClient from '../utils/apiClient';
import { SAGA_SERVICE_URL } from '../config/serviceUrls';

const BASE = `${SAGA_SERVICE_URL}/sagas`;

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'timed_out']);

export const BANK_SYNC_STEP_LABELS = {
  fetch_transactions: 'Henter transaktioner fra bank...',
  import_transactions: 'Importerer transaktioner...',
  mark_sync_complete: 'Afslutter sync...',
};

export function getSagaProgressLabel(saga) {
  if (!saga) return 'Starter sync...';

  if (saga.status === 'pending') {
    return 'Starter sync...';
  }
  if (saga.status === 'compensating') {
    return 'Ruller import tilbage...';
  }
  if (saga.status === 'completed') {
    return 'Sync fuldført';
  }
  if (saga.status === 'failed' || saga.status === 'timed_out') {
    return saga.error_detail || 'Sync fejlede';
  }

  if (saga.current_step_name && BANK_SYNC_STEP_LABELS[saga.current_step_name]) {
    return BANK_SYNC_STEP_LABELS[saga.current_step_name];
  }

  return 'Synkroniserer...';
}

export async function fetchSagaStatus(sagaId) {
  const resp = await apiClient.fetch(`${BASE}/${sagaId}`, { timeoutMs: 10_000 });
  if (resp.status === 404) {
    return null;
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || 'Kunne ikke hente saga-status');
  }
  return resp.json();
}

export async function pollSagaUntilComplete(
  sagaId,
  { intervalMs = 1500, timeoutMs = 300_000, onProgress } = {},
) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    const saga = await fetchSagaStatus(sagaId);

    if (saga === null) {
      if (onProgress) onProgress({ status: 'pending' });
    } else {
      if (onProgress) onProgress(saga);

      if (TERMINAL_STATUSES.has(saga.status)) {
        return saga;
      }
    }

    await new Promise((resolve) => {
      setTimeout(resolve, intervalMs);
    });
  }

  throw new Error('Sync tog for lang tid. Prøv igen senere.');
}

export function buildBankSyncResultMessage(saga) {
  const ctx = saga.context || {};
  const newImported = ctx.new_imported ?? 0;
  const duplicatesSkipped = ctx.duplicates_skipped ?? 0;
  const totalFetched = ctx.total_fetched ?? 0;

  return {
    message: `${newImported} nye, ${duplicatesSkipped} duplikater`,
    detail: totalFetched > 0
      ? `${totalFetched} transaktioner hentet`
      : 'Ingen nye transaktioner',
  };
}
