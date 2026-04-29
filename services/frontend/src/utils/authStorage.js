const AUTH_KEYS = ['access_token', 'user_id', 'username', 'account_id', 'account_name'];

export function clearAuthStorage() {
  AUTH_KEYS.forEach((key) => localStorage.removeItem(key));
}
