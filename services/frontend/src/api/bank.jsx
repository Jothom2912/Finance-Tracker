import apiClient from '../utils/apiClient';

const BASE = '/bank';

export async function fetchConnections() {
  const accountId = localStorage.getItem('account_id') || '1';
  const resp = await apiClient.get(`${BASE}/connections?account_id=${accountId}`);
  if (!resp.ok) throw new Error('Kunne ikke hente bankforbindelser');
  return resp.json();
}

export async function syncConnection(connectionId, dateFrom = null) {
  const body = dateFrom ? { date_from: dateFrom } : {};
  const resp = await apiClient.post(
    `${BASE}/connections/${connectionId}/sync`,
    body,
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || 'Sync fejlede');
  }
  return resp.json();
}

export async function fetchAvailableBanks(country = 'DK') {
  const resp = await apiClient.get(`${BASE}/available-banks?country=${country}`);
  if (!resp.ok) throw new Error('Kunne ikke hente tilgaengelige banker');
  return resp.json();
}

export async function connectBank(bankName, country = 'DK') {
  const accountId = parseInt(localStorage.getItem('account_id') || '1', 10);
  const resp = await apiClient.post(`${BASE}/connect`, {
    bank_name: bankName,
    country,
    account_id: accountId,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || 'Kunne ikke starte bankforbindelse');
  }
  return resp.json();
}
