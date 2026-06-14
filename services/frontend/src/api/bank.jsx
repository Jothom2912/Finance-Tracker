import apiClient from '../utils/apiClient';
import { BANKING_SERVICE_URL } from '../config/serviceUrls';

const BASE = `${BANKING_SERVICE_URL}/bank`;

export async function fetchConnections() {
  const accountId = localStorage.getItem('account_id');
  if (!accountId) throw new Error('Ingen konto valgt. Vælg en konto først.');
  const resp = await apiClient.fetch(
    `${BASE}/connections?account_id=${accountId}`,
  );
  if (!resp.ok) throw new Error('Kunne ikke hente bankforbindelser');
  return resp.json();
}

export async function syncConnection(connectionId, dateFrom = null) {
  const body = dateFrom ? { date_from: dateFrom } : {};
  const resp = await apiClient.fetch(
    `${BASE}/connections/${connectionId}/sync`,
    {
      method: 'POST',
      body: JSON.stringify(body),
      timeoutMs: 15_000,
    },
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || 'Sync fejlede');
  }
  const data = await resp.json();
  if (resp.status === 202 && data.saga_id) {
    return { sagaId: data.saga_id, status: data.status || 'started' };
  }
  return { sagaId: null, status: 'completed', legacyResult: data };
}

export async function fetchAvailableBanks(country = 'DK') {
  const resp = await apiClient.fetch(`${BASE}/available-banks?country=${country}`);
  if (!resp.ok) throw new Error('Kunne ikke hente tilgaengelige banker');
  return resp.json();
}

export async function connectBank(bankName, country = 'DK') {
  const accountId = parseInt(localStorage.getItem('account_id'), 10);
  if (!accountId) throw new Error('Ingen konto valgt. Vælg en konto først.');
  const resp = await apiClient.fetch(`${BASE}/connect`, {
    method: 'POST',
    body: JSON.stringify({
      bank_name: bankName,
      country,
      account_id: accountId,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || 'Kunne ikke starte bankforbindelse');
  }
  return resp.json();
}
