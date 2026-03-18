const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const REQUEST_TIMEOUT_MS = 30_000;

export const apiClient = {
  getAuthHeader(skipContentType = false) {
    const token = localStorage.getItem('access_token');
    const accountId = localStorage.getItem('account_id');
    const headers = {};

    if (!skipContentType) {
      headers['Content-Type'] = 'application/json';
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    if (accountId) {
      headers['X-Account-ID'] = accountId;
    }

    return headers;
  },

  async fetch(url, options = {}) {
    const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    const isFormData = options.body instanceof FormData;
    const authHeaders = this.getAuthHeader(isFormData);

    const userHeaders = { ...options.headers };
    if (isFormData) delete userHeaders['Content-Type'];

    const headers = { ...authHeaders, ...userHeaders };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
      const response = await fetch(fullUrl, {
        ...options,
        headers,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timeout - serveren svarer ikke');
      }
      throw error;
    }
  },

  async get(url, options = {}) {
    return this.fetch(url, { method: 'GET', ...options });
  },

  async post(url, data, options = {}) {
    return this.fetch(url, {
      method: 'POST',
      body: JSON.stringify(data),
      ...options,
    });
  },

  async put(url, data, options = {}) {
    return this.fetch(url, {
      method: 'PUT',
      body: JSON.stringify(data),
      ...options,
    });
  },

  async delete(url, options = {}) {
    return this.fetch(url, { method: 'DELETE', ...options });
  },
};

export default apiClient;
