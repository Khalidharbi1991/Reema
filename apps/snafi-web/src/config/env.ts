/**
 * The only place that reads environment variables. Keys come from .env.local
 * (gitignored) on this PC, or from the host's settings when deployed.
 * Only the publishable key is read; a secret key is refused outright.
 */
export type SupabaseConfig = { url: string; publishableKey: string };

export type EnvSource = Record<string, string | undefined>;

export class ConfigError extends Error {}

function looksSecret(key: string): boolean {
  if (key.startsWith("sb_secret_")) return true;
  // Legacy JWT keys carry their role in the payload.
  const parts = key.split(".");
  if (parts.length === 3) {
    try {
      const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
      const payload = JSON.parse(atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4)));
      return payload?.role === "service_role";
    } catch {
      return false;
    }
  }
  return false;
}

/** Returns null when Supabase is not configured yet; throws when it is configured wrongly. */
export function readSupabaseConfig(env: EnvSource): SupabaseConfig | null {
  const url = env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  const publishableKey = env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim();
  if (!url && !publishableKey) return null;
  if (!url || !publishableKey) throw new ConfigError("Set both NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY.");
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new ConfigError("NEXT_PUBLIC_SUPABASE_URL is not a valid URL.");
  }
  const local = parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1";
  if (parsed.protocol !== "https:" && !(local && parsed.protocol === "http:")) {
    throw new ConfigError("NEXT_PUBLIC_SUPABASE_URL must use https.");
  }
  if (looksSecret(publishableKey)) {
    throw new ConfigError("That is a secret (service_role) key. The web app takes only the publishable key.");
  }
  return { url: parsed.origin, publishableKey };
}

// Next.js inlines NEXT_PUBLIC_* only when written out literally.
const processEnv: EnvSource = {
  NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
};

export function supabaseConfig(): SupabaseConfig | null {
  return readSupabaseConfig(processEnv);
}

/**
 * The site's own address, for every redirect (never the request's Host header,
 * which the client controls; SEC-11). In order:
 *   1. SNAFI_SITE_URL, if set (https, or http only for localhost);
 *   2. on Vercel, the address Vercel itself sets: the production domain in
 *      production, the branch address on a preview;
 *   3. on a development server only: null, meaning "this request's own origin",
 *      so the phone's Wi-Fi dev mode still works.
 * A production build with none of these throws: redirects fail closed.
 */
export function readSiteUrl(env: EnvSource, nodeEnv: string | undefined): string | null {
  const explicit = env.SNAFI_SITE_URL?.trim();
  if (explicit) return checkSiteUrl(explicit, "SNAFI_SITE_URL");
  const vercelHost = env.VERCEL_ENV === "production"
    ? env.VERCEL_PROJECT_PRODUCTION_URL
    : env.VERCEL_ENV === "preview" ? (env.VERCEL_BRANCH_URL || env.VERCEL_URL) : undefined;
  if (vercelHost?.trim()) return checkSiteUrl(`https://${vercelHost.trim()}`, "the Vercel address");
  if (nodeEnv === "development") return null;
  throw new ConfigError("Set SNAFI_SITE_URL to the site's address, for example https://snafi.example.com.");
}

function checkSiteUrl(value: string, name: string): string {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new ConfigError(`${name} is not a valid URL.`);
  }
  const local = parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1";
  if (parsed.protocol !== "https:" && !(local && parsed.protocol === "http:")) {
    throw new ConfigError(`${name} must use https.`);
  }
  if (parsed.username || parsed.password || parsed.pathname !== "/" || parsed.search || parsed.hash) {
    throw new ConfigError(`${name} must be just the address, like https://snafi.example.com.`);
  }
  return parsed.origin;
}

export function siteUrl(): string | null {
  return readSiteUrl({
    SNAFI_SITE_URL: process.env.SNAFI_SITE_URL,
    VERCEL_ENV: process.env.VERCEL_ENV,
    VERCEL_PROJECT_PRODUCTION_URL: process.env.VERCEL_PROJECT_PRODUCTION_URL,
    VERCEL_BRANCH_URL: process.env.VERCEL_BRANCH_URL,
    VERCEL_URL: process.env.VERCEL_URL,
  }, process.env.NODE_ENV);
}

/**
 * Step 5: the Web Push (VAPID) PUBLIC key, NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY. Not a secret: the
 * private half stays on the PC in Credential Manager. It is 65 bytes (an uncompressed P-256 point,
 * starting with 0x04), base64url: 87 characters starting with "B". null when not set yet.
 */
export function readVapidPublicKey(env: EnvSource): string | null {
  const key = env.NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY?.trim();
  if (!key) return null;
  if (!/^B[A-Za-z0-9_-]{86}$/.test(key)) {
    throw new ConfigError("NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY must be the push PUBLIC key printed by snafi.cmd set-secrets.");
  }
  return key;
}

export function vapidPublicKey(): string | null {
  try {
    return readVapidPublicKey({ NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY: process.env.NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY });
  } catch {
    return null; // a wrong value only switches push off; Settings says push is not set up
  }
}

/**
 * Preview mode: only on a development server with no Supabase keys, so the
 * screens can be looked at before Supabase exists. Never in a production build.
 */
export function isPreviewMode(env: EnvSource = processEnv, nodeEnv = process.env.NODE_ENV): boolean {
  return nodeEnv === "development" && readSupabaseConfig(env) === null;
}
