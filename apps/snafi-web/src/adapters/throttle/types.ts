/**
 * SEC-4 sign-in throttle store. Keys are HMAC-SHA-256 hex strings made in
 * src/core/signin-throttle.ts; the store never sees an email or an IP address.
 * Supabase today (migration 0005); the in-memory one is for tests and preview mode.
 */
export const THROTTLE_LIMIT = 5;
export const THROTTLE_WINDOW_SECONDS = 15 * 60;

export interface ThrottleAdapter {
  /** Seconds until another try is allowed for these keys (0 = go ahead). */
  waitSeconds(keys: string[]): Promise<number>;
  /** Records one wrong password against each key. */
  recordFailure(keys: string[]): Promise<void>;
}

export class ThrottleError extends Error {}

export function checkKeys(keys: string[]): string[] {
  if (keys.length < 1 || keys.length > 2 || keys.some((k) => !/^[0-9a-f]{64}$/.test(k))) {
    throw new ThrottleError("invalid throttle keys");
  }
  return keys;
}
