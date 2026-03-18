import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';

export async function login(credentials) {
  const response = await apiClient.post('/users/login', credentials);
  if (!response.ok) {
    const error = await parseApiError(response);
    error.accounts = null;
    try {
      const body = await response.clone().json();
      if (body.accounts) error.accounts = body.accounts;
    } catch { /* no accounts data */ }
    throw error;
  }
  return response.json();
}

export async function register(userData) {
  const response = await apiClient.post('/users/', userData);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}
