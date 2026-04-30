import { vi, describe, it, expect, beforeEach } from 'vitest';
import { handleUnauthorized, _resetLogoutFlag } from './handleUnauthorized';

vi.mock('../lib/queryClient', () => ({
  queryClient: {
    cancelQueries: vi.fn(),
    clear: vi.fn(),
  },
}));

vi.mock('./authStorage', () => ({
  clearAuthStorage: vi.fn(),
}));

import { queryClient } from '../lib/queryClient';
import { clearAuthStorage } from './authStorage';

const replaceMock = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  _resetLogoutFlag();
  localStorage.clear();

  Object.defineProperty(window, 'location', {
    value: { replace: replaceMock },
    writable: true,
  });
});

describe('handleUnauthorized', () => {
  it('cancels queries, clears cache and storage, then redirects', () => {
    handleUnauthorized();

    expect(queryClient.cancelQueries).toHaveBeenCalledOnce();
    expect(queryClient.clear).toHaveBeenCalledOnce();
    expect(clearAuthStorage).toHaveBeenCalledOnce();
    expect(replaceMock).toHaveBeenCalledWith('/login');
  });

  it('executes cleanup in the correct order', () => {
    const callOrder = [];
    queryClient.cancelQueries.mockImplementation(() => callOrder.push('cancelQueries'));
    queryClient.clear.mockImplementation(() => callOrder.push('clear'));
    clearAuthStorage.mockImplementation(() => callOrder.push('clearAuthStorage'));
    replaceMock.mockImplementation(() => callOrder.push('replace'));

    handleUnauthorized();

    expect(callOrder).toEqual(['cancelQueries', 'clear', 'clearAuthStorage', 'replace']);
  });

  it('only runs once even when called multiple times', () => {
    handleUnauthorized();
    handleUnauthorized();
    handleUnauthorized();

    expect(queryClient.cancelQueries).toHaveBeenCalledTimes(1);
    expect(replaceMock).toHaveBeenCalledTimes(1);
  });

  it('can run again after flag is reset (test utility)', () => {
    handleUnauthorized();
    _resetLogoutFlag();
    handleUnauthorized();

    expect(queryClient.cancelQueries).toHaveBeenCalledTimes(2);
    expect(replaceMock).toHaveBeenCalledTimes(2);
  });
});
