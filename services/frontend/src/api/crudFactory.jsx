import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';

/**
 * Creates standard CRUD operations for a REST resource.
 *
 * @param {string} basePath - API path, e.g. '/categories'
 * @param {object} options
 * @param {string} options.baseUrl - Full base URL for a specific service (e.g. 'http://localhost:8002/api/v1').
 *   When provided, basePath is appended to it and absolute URLs are sent to apiClient.
 *   When omitted, basePath is used as a relative URL (resolved against VITE_API_BASE_URL).
 * @param {boolean} options.trailingSlash - Append '/' to paths (default true)
 * @param {boolean} options.emptyOnNotFound - Return [] on 404 for fetchAll (default false)
 */
export function createCrudApi(basePath, { baseUrl, trailingSlash = true, emptyOnNotFound = false } = {}) {
  const slash = trailingSlash ? '/' : '';
  const prefix = baseUrl ? `${baseUrl}${basePath}` : basePath;

  return {
    async fetchAll(params) {
      const query = params ? new URLSearchParams(params).toString() : '';
      const url = `${prefix}${slash}${query ? `?${query}` : ''}`;
      const response = await apiClient.get(url);
      if (!response.ok) {
        if (emptyOnNotFound && response.status === 404) return [];
        throw await parseApiError(response);
      }
      return response.json();
    },

    async fetchById(id) {
      const response = await apiClient.get(`${prefix}/${id}`);
      if (!response.ok) throw await parseApiError(response);
      return response.json();
    },

    async create(data) {
      const response = await apiClient.post(`${prefix}${slash}`, data);
      if (!response.ok) throw await parseApiError(response);
      return response.json();
    },

    async update(id, data) {
      const response = await apiClient.put(`${prefix}/${id}`, data);
      if (!response.ok) throw await parseApiError(response);
      return response.json();
    },

    async remove(id) {
      const response = await apiClient.delete(`${prefix}/${id}`);
      if (!response.ok) throw await parseApiError(response);
    },
  };
}
