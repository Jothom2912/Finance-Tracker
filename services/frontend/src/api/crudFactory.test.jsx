import { vi, describe, it, expect, beforeEach } from 'vitest';
import { createCrudApi } from './crudFactory';
import apiClient from '../utils/apiClient';

vi.mock('../utils/apiClient');

beforeEach(() => vi.clearAllMocks());

function okResponse(body) {
  return { ok: true, status: 200, json: () => Promise.resolve(body) };
}

function errorResponse(status, body) {
  return {
    ok: false,
    status,
    statusText: 'Error',
    json: () => Promise.resolve(body),
  };
}

describe('createCrudApi', () => {
  const api = createCrudApi('/items');

  describe('fetchAll', () => {
    it('calls GET on the base path with trailing slash', async () => {
      const items = [{ id: 1 }];
      apiClient.get.mockResolvedValue(okResponse(items));

      const result = await api.fetchAll();

      expect(apiClient.get).toHaveBeenCalledWith('/items/');
      expect(result).toEqual(items);
    });

    it('appends query params when provided', async () => {
      apiClient.get.mockResolvedValue(okResponse([]));

      await api.fetchAll({ page: '1', limit: '10' });

      expect(apiClient.get).toHaveBeenCalledWith('/items/?page=1&limit=10');
    });

    it('throws ApiError on non-ok response', async () => {
      apiClient.get.mockResolvedValue(errorResponse(500, { detail: 'Server error' }));

      await expect(api.fetchAll()).rejects.toThrow('Server error');
    });

    it('returns empty array on 404 when emptyOnNotFound is true', async () => {
      const lenientApi = createCrudApi('/items', { emptyOnNotFound: true });
      apiClient.get.mockResolvedValue(errorResponse(404, { detail: 'Not found' }));

      const result = await lenientApi.fetchAll();

      expect(result).toEqual([]);
    });

    it('still throws on 404 when emptyOnNotFound is false', async () => {
      apiClient.get.mockResolvedValue(errorResponse(404, { detail: 'Not found' }));

      await expect(api.fetchAll()).rejects.toThrow('Not found');
    });
  });

  describe('fetchById', () => {
    it('calls GET with item id', async () => {
      const item = { id: 42, name: 'Test' };
      apiClient.get.mockResolvedValue(okResponse(item));

      const result = await api.fetchById(42);

      expect(apiClient.get).toHaveBeenCalledWith('/items/42');
      expect(result).toEqual(item);
    });

    it('throws on non-ok response', async () => {
      apiClient.get.mockResolvedValue(errorResponse(404, { detail: 'Not found' }));

      await expect(api.fetchById(999)).rejects.toThrow('Not found');
    });
  });

  describe('create', () => {
    it('calls POST with data and trailing slash', async () => {
      const newItem = { name: 'New' };
      const created = { id: 1, name: 'New' };
      apiClient.post.mockResolvedValue(okResponse(created));

      const result = await api.create(newItem);

      expect(apiClient.post).toHaveBeenCalledWith('/items/', newItem);
      expect(result).toEqual(created);
    });

    it('throws on non-ok response', async () => {
      apiClient.post.mockResolvedValue(errorResponse(400, { detail: 'Validation failed' }));

      await expect(api.create({})).rejects.toThrow('Validation failed');
    });
  });

  describe('update', () => {
    it('calls PUT with id and data', async () => {
      const updated = { id: 1, name: 'Updated' };
      apiClient.put.mockResolvedValue(okResponse(updated));

      const result = await api.update(1, { name: 'Updated' });

      expect(apiClient.put).toHaveBeenCalledWith('/items/1', { name: 'Updated' });
      expect(result).toEqual(updated);
    });
  });

  describe('remove', () => {
    it('calls DELETE with id', async () => {
      apiClient.delete.mockResolvedValue({ ok: true, status: 204 });

      await api.remove(1);

      expect(apiClient.delete).toHaveBeenCalledWith('/items/1');
    });

    it('throws on non-ok response', async () => {
      apiClient.delete.mockResolvedValue(errorResponse(403, { detail: 'Forbidden' }));

      await expect(api.remove(1)).rejects.toThrow('Forbidden');
    });
  });

  describe('options', () => {
    it('omits trailing slash when trailingSlash is false', async () => {
      const noSlash = createCrudApi('/items', { trailingSlash: false });
      apiClient.get.mockResolvedValue(okResponse([]));

      await noSlash.fetchAll();

      expect(apiClient.get).toHaveBeenCalledWith('/items');
    });
  });
});
