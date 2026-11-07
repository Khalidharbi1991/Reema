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
 * Preview mode: only on a development server with no Supabase keys, so the
 * screens can be looked at before Supabase exists. Never in a production build.
 */
export function isPreviewMode(env: EnvSource = processEnv, nodeEnv = process.env.NODE_ENV): boolean {
  return nodeEnv === "development" && readSupabaseConfig(env) === null;
}
