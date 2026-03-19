import { createCrudApi } from './crudFactory';
import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';
import { TRANSACTION_SERVICE_URL } from '../config/serviceUrls';

const crud = createCrudApi('/transactions', { baseUrl: TRANSACTION_SERVICE_URL });

export async function createTransaction(data) {
  const payload = toServicePayload(data);
  const result = await crud.create(payload);
  return fromServiceResponse(result);
}

export async function updateTransaction(id, data) {
  const payload = toServicePayload(data);
  const result = await crud.update(id, payload);
  return fromServiceResponse(result);
}

export async function deleteTransaction(id) {
  return crud.remove(id);
}

export async function fetchTransactions({ startDate, endDate, categoryId } = {}) {
  const params = {};
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  if (categoryId) params.category_id = categoryId;
  const results = await crud.fetchAll(params);
  return results.map(fromServiceResponse);
}

export async function uploadTransactionsCsv(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.fetch(`${TRANSACTION_SERVICE_URL}/transactions/import-csv`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) throw await parseApiError(response);
  const result = await response.json();
  return {
    message: `${result.imported} transaktioner importeret, ${result.skipped} sprunget over.`,
    imported_count: result.imported,
    skipped: result.skipped,
    errors: result.errors,
  };
}

function toServicePayload(data) {
  const payload = { ...data };

  if ('type' in payload) {
    payload.transaction_type = payload.type;
    delete payload.type;
  }
  if ('transaction_date' in payload) {
    payload.date = payload.transaction_date;
    delete payload.transaction_date;
  }

  if (!payload.account_id) {
    const accountId = localStorage.getItem('account_id');
    if (accountId) payload.account_id = parseInt(accountId, 10);
  }
  if (!payload.account_name) {
    payload.account_name = localStorage.getItem('account_name') || 'Default';
  }

  return payload;
}

function fromServiceResponse(tx) {
  return {
    ...tx,
    idTransaction: tx.id,
    Category_idCategory: tx.category_id,
    Account_idAccount: tx.account_id,
    type: tx.transaction_type,
  };
}
