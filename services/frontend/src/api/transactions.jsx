import { createCrudApi } from './crudFactory';
import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';

const crud = createCrudApi('/transactions');

export const createTransaction = crud.create;
export const updateTransaction = crud.update;
export const deleteTransaction = crud.remove;

export async function fetchTransactions({ startDate, endDate, categoryId } = {}) {
  const params = { start_date: startDate, end_date: endDate };
  if (categoryId) params.category_id = categoryId;
  return crud.fetchAll(params);
}

export async function uploadTransactionsCsv(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.fetch('/transactions/upload-csv/', {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}
