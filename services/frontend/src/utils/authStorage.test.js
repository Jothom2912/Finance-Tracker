import { describe, it, expect, beforeEach } from 'vitest';
import { clearAuthStorage } from './authStorage';

beforeEach(() => localStorage.clear());

describe('clearAuthStorage', () => {
  it('removes all auth-related keys from localStorage', () => {
    localStorage.setItem('access_token', 'tok');
    localStorage.setItem('user_id', '1');
    localStorage.setItem('username', 'alice');
    localStorage.setItem('account_id', '42');
    localStorage.setItem('account_name', 'Main');

    clearAuthStorage();

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('user_id')).toBeNull();
    expect(localStorage.getItem('username')).toBeNull();
    expect(localStorage.getItem('account_id')).toBeNull();
    expect(localStorage.getItem('account_name')).toBeNull();
  });

  it('does not remove unrelated keys', () => {
    localStorage.setItem('theme', 'dark');
    localStorage.setItem('access_token', 'tok');

    clearAuthStorage();

    expect(localStorage.getItem('theme')).toBe('dark');
  });
});
