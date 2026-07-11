/**
 * Minimal client-side JWT helpers. No verification is performed (the backend
 * is the source of truth for signature validity) — this only decodes the
 * payload so the UI can react to an expired `exp` claim before making a
 * request that would otherwise 401.
 */

/**
 * Decode a JWT's payload. Returns null if the token is missing/malformed.
 */
export function decodeJwtPayload(token) {
  if (!token || typeof token !== 'string') return null;

  const parts = token.split('.');
  if (parts.length !== 3) return null;

  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
    const json = decodeURIComponent(
      atob(padded)
        .split('')
        .map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join(''),
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/**
 * Returns true if the token has a numeric `exp` claim that has passed.
 * Tokens without an `exp` claim (or that fail to decode) are treated as
 * NOT expired — the backend controls expiry and will reject the token itself
 * if it's actually invalid.
 */
export function isTokenExpired(token) {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return false;

  const nowInSeconds = Date.now() / 1000;
  return payload.exp <= nowInSeconds;
}
