import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';

/**
 * Creates standard CRUD operations for a REST resource.
 *
 * @param {string} basePath - API path, e.g. '/categories'
 * @param {object} options
 * @param {boolean} options.trailingSlash - Append '/' to paths (default true)
 * @param {boolean} options.emptyOnNotFound - Return [] on 404 for fetchAll (default false)
 */
export function createCrudApi(basePath, { trailingSlash = true, emptyOnNotFound = false } = {}) {
  const slash = trailingSlash ? '/' : '';

  return {
    async fetchAll(params) {
      const query = params ? new URLSearchParams(params).toString() : '';
      const url = `${basePath}${slash}${query ? `?${query}` : ''}`;
      const response = await apiClient.get(url);
      if (!response.ok) {
        if (emptyOnNotFound && response.status === 404) return [];
        throw await parseApiError(response);
      }
      return response.json();
    },

    async fetchById(id) {
      const response = await apiClient.get(`${basePath}/${id}`);
      if (!response.ok) throw await parseApiError(response);
      return response.json();
    },

    async create(data) {
      const response = await apiClient.post(`${basePath}${slash}`, data);
      if (!response.ok) throw await parseApiError(response);
      return response.json();
    },

    async update(id, data) {
      const response = await apiClient.put(`${basePath}/${id}`, data);
      if (!response.ok) throw await parseApiError(response);
      return response.json();
    },

    async remove(id) {
      const response = await apiClient.delete(`${basePath}/${id}`);
      if (!response.ok) throw await parseApiError(response);
    },
  };
}
