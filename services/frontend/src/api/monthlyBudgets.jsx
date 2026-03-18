import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';

const BASE = '/monthly-budgets';

export async function fetchMonthlyBudget({ month, year }) {
  const response = await apiClient.get(
    `${BASE}/?month=${month}&year=${year}`
  );
  if (!response.ok) {
    if (response.status === 404) return null;
    throw await parseApiError(response);
  }
  return response.json();
}

export async function createMonthlyBudget({ month, year, lines }) {
  const response = await apiClient.post(`${BASE}/`, { month, year, lines });
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function updateMonthlyBudget(id, { lines }) {
  const response = await apiClient.put(`${BASE}/${id}`, { lines });
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function deleteMonthlyBudget(id) {
  const response = await apiClient.delete(`${BASE}/${id}`);
  if (!response.ok) throw await parseApiError(response);
}

export async function copyMonthlyBudget({
  sourceMonth,
  sourceYear,
  targetMonth,
  targetYear,
}) {
  const response = await apiClient.post(`${BASE}/copy`, {
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
    `${BASE}/summary?month=${month}&year=${year}`
  );
  if (!response.ok) {
    if (response.status === 404) return null;
    throw await parseApiError(response);
  }
  return response.json();
}
