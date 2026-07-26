import { createCrudApi } from './crudFactory';
import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';
import { TRANSACTION_SERVICE_URL } from '../config/serviceUrls';
import { PAGE_SIZE } from '../lib/pagination';

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

export async function fetchTransactions({
  startDate,
  endDate,
  categoryId,
  skip = 0,
  limit = PAGE_SIZE,
} = {}) {
  // skip sættes ubetinget: `if (skip)` ville droppe skip=0, altså side 1 —
  // det almindelige tilfælde.
  const params = { skip, limit };
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  if (categoryId) params.category_id = categoryId;
  const body = await crud.fetchAll(params);
  const { items, totalCount } = unpackTransactionList(body);
  return { items: items.map(fromServiceResponse), totalCount };
}

/**
 * Læser både den nuværende bare liste og den kommende {total_count, items}-envelope.
 *
 * MIDLERTIDIG: Array-grenen findes udelukkende for at denne læser kan deployes
 * FØR serveren skifter form (P1-14 step 11), så der ikke er et vindue hvor et
 * gammelt bundle kalder en ny server og blanker siden. I det vindue er totalen
 * en tilnærmelse (`items.length`, dvs. "Viser 1–50 af 50") — mindre end sandheden,
 * men mere end i dag, hvor der ikke står noget.
 * Fjernes sammen med sin test når envelopen er ude: se P3-36 i BACKLOG.md og
 * decisions/2026-07-26-transaction-list-envelope.md.
 */
function unpackTransactionList(body) {
  if (Array.isArray(body)) {
    return { items: body, totalCount: body.length };
  }
  return {
    items: body?.items ?? [],
    // null, ikke 0: 0 betyder "tom periode" og ville lade en clamp på
    // sidetallet udløse på et gæt. Kun et rigtigt tal er et tal.
    totalCount: typeof body?.total_count === 'number' ? body.total_count : null,
  };
}

export async function uploadTransactionsCsv({ file, bankFormat = 'internal' }) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('bank_format', bankFormat);

  if (bankFormat !== 'internal') {
    const accountId = localStorage.getItem('account_id');
    const accountName = localStorage.getItem('account_name') || 'Default';
    if (accountId) formData.append('account_id', accountId);
    formData.append('account_name', accountName);
  }

  const response = await apiClient.fetch(`${TRANSACTION_SERVICE_URL}/transactions/import-csv`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) throw await parseApiError(response);
  const result = await response.json();
  const parts = [`${result.imported} transaktioner importeret`];
  if (result.duplicates_skipped) parts.push(`${result.duplicates_skipped} dubletter sprunget over`);
  if (result.skipped) parts.push(`${result.skipped} rækker sprunget over`);
  return {
    message: `${parts.join(', ')}.`,
    imported_count: result.imported,
    skipped: result.skipped,
    duplicates_skipped: result.duplicates_skipped || 0,
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
    type: tx.transaction_type,
  };
}
