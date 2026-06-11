import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';
import { BUDGET_SERVICE_URL } from '../config/serviceUrls';
import { getAccountId } from '../utils/authStorage';

const BASE = `${BUDGET_SERVICE_URL}/monthly-budgets`;

export async function fetchMonthlyBudget({ month, year }) {
  const response = await apiClient.get(
    `${BASE}/?account_id=${getAccountId()}&month=${month}&year=${year}`
  );
  if (!response.ok) {
    if (response.status === 404) return null;
    throw await parseApiError(response);
  }
  return response.json();
}

export async function createMonthlyBudget({ month, year, lines }) {
  const response = await apiClient.post(`${BASE}/?account_id=${getAccountId()}`, { month, year, lines });
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function updateMonthlyBudget(id, { lines }) {
  const response = await apiClient.put(`${BASE}/${id}?account_id=${getAccountId()}`, { lines });
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function deleteMonthlyBudget(id) {
  const response = await apiClient.delete(`${BASE}/${id}?account_id=${getAccountId()}`);
  if (!response.ok) throw await parseApiError(response);
}

export async function copyMonthlyBudget({
  sourceMonth,
  sourceYear,
  targetMonth,
  targetYear,
}) {
  const response = await apiClient.post(`${BASE}/copy?account_id=${getAccountId()}`, {
    source_month: sourceMonth,
    source_year: sourceYear,
    target_month: targetMonth,
    target_year: targetYear,
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function fetchMonthlyBudgetSummary({ month, year }) {
  const response = await apiClient.get(
    `${BASE}/summary?account_id=${getAccountId()}&month=${month}&year=${year}`
  );
  if (!response.ok) {
    if (response.status === 404) return null;
    throw await parseApiError(response);
  }
  return response.json();
}
