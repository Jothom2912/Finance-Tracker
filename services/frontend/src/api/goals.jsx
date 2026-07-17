import { createCrudApi } from './crudFactory';
import { GOAL_SERVICE_URL } from '../config/serviceUrls';
import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';

const BASE = `${GOAL_SERVICE_URL}/goals`;

const crud = createCrudApi('/goals', { baseUrl: GOAL_SERVICE_URL, emptyOnNotFound: true, trailingSlash: false });

export const fetchGoals = crud.fetchAll;
export const createGoal = crud.create;
export const updateGoal = crud.update;
export const deleteGoal = crud.remove;

export async function setDefaultGoal(id) {
  const response = await apiClient.put(`${BASE}/${id}/default`);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function clearDefaultGoal(id) {
  const response = await apiClient.delete(`${BASE}/${id}/default`);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function fetchAllocationHistory(id) {
  const response = await apiClient.get(`${BASE}/${id}/allocation-history`);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

// X-Account-ID sættes automatisk af apiClient.
export async function fetchUnallocatedSurplus() {
  const response = await apiClient.get(`${BASE}/unallocated-surplus`);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}
