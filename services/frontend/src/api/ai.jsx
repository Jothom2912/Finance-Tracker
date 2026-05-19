import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';
import { AI_SERVICE_URL } from '../config/serviceUrls';

const AI_CHAT_TIMEOUT_MS = 180_000;

export async function ingestTransactionsForRag() {
  const response = await apiClient.post(`${AI_SERVICE_URL}/ingest`, {}, {
    timeoutMs: AI_CHAT_TIMEOUT_MS,
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}
