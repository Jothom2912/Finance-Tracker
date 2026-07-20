import { NOTIFICATION_SERVICE_URL } from '../config/serviceUrls';
import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';

const BASE = `${NOTIFICATION_SERVICE_URL}/notifications`;

export async function fetchNotifications({ unread = false, limit = 50 } = {}) {
  const qs = new URLSearchParams();
  if (unread) qs.set('unread', 'true');
  if (limit) qs.set('limit', String(limit));
  const response = await apiClient.get(`${BASE}?${qs.toString()}`);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function fetchUnreadCount() {
  const response = await apiClient.get(`${BASE}/unread-count`);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function markRead(id) {
  const response = await apiClient.post(`${BASE}/${id}/read`);
  if (!response.ok) throw await parseApiError(response);
}

export async function markAllRead() {
  const response = await apiClient.post(`${BASE}/read-all`);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function dismissNotification(id) {
  const response = await apiClient.delete(`${BASE}/${id}`);
  if (!response.ok) throw await parseApiError(response);
}
