import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';

export async function fetchDashboardOverview({ startDate, endDate } = {}) {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);

  const query = params.toString();
  const url = `/dashboard/overview/${query ? `?${query}` : ''}`;

  const response = await apiClient.get(url);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}
