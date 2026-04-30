import { queryClient } from '../lib/queryClient';
import { clearAuthStorage } from './authStorage';

let isLoggingOut = false;

export function handleUnauthorized() {
  if (isLoggingOut) return;
  isLoggingOut = true;

  queryClient.cancelQueries();
  queryClient.clear();
  clearAuthStorage();
  window.location.replace('/login');
}

/** Reset the dedup flag. Only needed in tests. */
export function _resetLogoutFlag() {
  isLoggingOut = false;
}
