import { createCrudApi } from './crudFactory';
import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';

const crud = createCrudApi('/budgets', { emptyOnNotFound: true });

export const fetchBudgets = crud.fetchAll;
export const createBudget = crud.create;
export const updateBudget = crud.update;
export const deleteBudget = crud.remove;

export async function fetchBudgetSummary({ month, year }) {
  const m = parseInt(month, 10);
  const y = parseInt(year, 10);
  const response = await apiClient.get(`/budgets/summary?month=${m}&year=${y}`);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}
