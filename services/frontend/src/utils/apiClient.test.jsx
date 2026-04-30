import { vi, describe, it, expect, beforeEach } from 'vitest';

const { handleUnauthorizedMock } = vi.hoisted(() => ({
  handleUnauthorizedMock: vi.fn(),
}));

vi.mock('./handleUnauthorized', () => ({
  handleUnauthorized: handleUnauthorizedMock,
}));

import { apiClient } from './apiClient';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.restoreAllMocks();
});

function mockFetch(status, body = {}) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: 'Test',
    json: () => Promise.resolve(body),
  });
}

describe('apiClient 401 interceptor', () => {
  it('calls handleUnauthorized on 401 from a normal endpoint', async () => {
    mockFetch(401, { detail: 'Invalid or expired token' });

    const resultPromise = apiClient.get('/categories/');

    // The returned Promise should never resolve (page is navigating away).
    const raced = await Promise.race([
      resultPromise.then(() => 'resolved'),
      new Promise((r) => setTimeout(() => r('pending'), 50)),
    ]);

    expect(raced).toBe('pending');
    expect(handleUnauthorizedMock).toHaveBeenCalledOnce();
  });

  it('does NOT call handleUnauthorized on 401 from /login', async () => {
    mockFetch(401, { detail: 'Invalid email or password.' });

    const response = await apiClient.post('http://localhost:8001/api/v1/users/login', {
      username_or_email: 'alice',
      password: 'wrong',
    });

    expect(response.status).toBe(401);
    expect(handleUnauthorizedMock).not.toHaveBeenCalled();
  });

  it('does NOT call handleUnauthorized on 401 from /register', async () => {
    mockFetch(401, { detail: 'Registration error' });

    const response = await apiClient.post('http://localhost:8001/api/v1/users/register', {
      email: 'a@b.com',
    });

    expect(response.status).toBe(401);
    expect(handleUnauthorizedMock).not.toHaveBeenCalled();
  });

  it('returns response normally on non-401 errors', async () => {
    mockFetch(500, { detail: 'Server error' });

    const response = await apiClient.get('/categories/');

    expect(response.status).toBe(500);
    expect(handleUnauthorizedMock).not.toHaveBeenCalled();
  });

  it('returns response normally on success', async () => {
    mockFetch(200, [{ id: 1 }]);

    const response = await apiClient.get('/categories/');

    expect(response.status).toBe(200);
    expect(handleUnauthorizedMock).not.toHaveBeenCalled();
  });
});
