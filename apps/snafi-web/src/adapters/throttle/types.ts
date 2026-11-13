/**
 * SEC-4 sign-in throttle store. Keys are HMAC-SHA-256 hex strings made in
 * src/core/signin-throttle.ts; the store never sees an email or an IP address.
 * Supabase today (migration 0005); the in-memory one is for tests and preview mode.
 */
export const THROTTLE_LIMIT = 5;
export const THROTTLE_WINDOW_SECONDS = 15 * 60;
export const THROTTLE_GLOBAL_CEILING = 10_000;

/** wait > 0: do not try, nothing was counted. wait = 0: the try is counted under attempt. */
export type ThrottleTicket = { wait: number; attempt: string | null };

export interface ThrottleAdapter {
  /** Counts a try before Supabase Auth is asked, one at a time per key (SEC-72). */
  begin(keys: string[]): Promise<ThrottleTicket>;
  /** Takes back a counted try that was not a wrong password. */
  forget(attempt: string): Promise<void>;
}

export class ThrottleError extends Error {}

export function checkKeys(keys: string[]): string[] {
  if (keys.length < 1 || keys.length > 2 || keys.some((k) => !/^[0-9a-f]{64}$/.test(k))) {
    throw new ThrottleError("invalid throttle keys");
  }
  return keys;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function checkTicket(value: unknown): ThrottleTicket {
  const v = value as { wait?: unknown; attempt?: unknown } | null;
  const wait = Number(v?.wait);
  const attempt = v?.attempt ?? null;
  if (!Number.isInteger(wait) || wait < 0) throw new ThrottleError("unexpected throttle answer");
  if (wait === 0 && (typeof attempt !== "string" || !UUID.test(attempt))) throw new ThrottleError("unexpected throttle answer");
  return { wait, attempt: wait === 0 ? (attempt as string) : null };
}
