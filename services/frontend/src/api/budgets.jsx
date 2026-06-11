import { createCrudApi } from './crudFactory';
import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';
import { BUDGET_SERVICE_URL } from '../config/serviceUrls';
import { getAccountId } from '../utils/authStorage';

const crud = createCrudApi('/budgets', { baseUrl: BUDGET_SERVICE_URL, emptyOnNotFound: true });

export const fetchBudgets = crud.fetchAll;
export const createBudget = crud.create;
export const updateBudget = crud.update;
export const deleteBudget = crud.remove;

export async function fetchBudgetSummary({ month, year }) {
  const m = parseInt(month, 10);
  const y = parseInt(year, 10);
  const response = await apiClient.get(
    `${BUDGET_SERVICE_URL}/monthly-budgets/summary?account_id=${getAccountId()}&month=${m}&year=${y}`
  );
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}
