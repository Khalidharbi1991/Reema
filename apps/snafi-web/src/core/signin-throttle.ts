import "server-only";
import { createHmac, randomBytes } from "node:crypto";
import { headers } from "next/headers";
import { throttleAdapter } from "@/adapters";
import { ConfigError } from "@/config/env";

/**
 * SEC-4: the sign-in throttle's keys. The store gets an HMAC of the email and of
 * the client IP, never the values themselves, keyed with SNAFI_THROTTLE_SECRET.
 *
 * The client IP is used only on Vercel, where Vercel's edge sets x-real-ip and
 * replaces any value the client sent. Anywhere else (this PC, the Wi-Fi dev mode)
 * the header comes from the client as sent (SEC-11), so only the email key applies.
 */
const DEV_PEPPER = randomBytes(32).toString("hex");

export function throttlePepper(env: Record<string, string | undefined>, nodeEnv: string | undefined): string {
  const value = env.SNAFI_THROTTLE_SECRET?.trim();
  if (value) {
    if (value.length < 32) throw new ConfigError("SNAFI_THROTTLE_SECRET must be at least 32 characters.");
    return value;
  }
  // A development server may use a per-process value; counts then reset on restart.
  if (nodeEnv === "development") return DEV_PEPPER;
  throw new ConfigError("Set SNAFI_THROTTLE_SECRET (32 or more random characters).");
}

export function throttleKeys(pepper: string, email: string, ip: string | null): string[] {
  const mac = (label: string, value: string) => createHmac("sha256", pepper).update(`${label}:${value}`).digest("hex");
  const keys = [mac("email", email.trim().toLowerCase())];
  if (ip) keys.push(mac("ip", ip));
  return keys;
}

/** The client IP, only where the host vouches for it (Vercel); otherwise null. */
export function trustedClientIp(get: (name: string) => string | null, env: Record<string, string | undefined>): string | null {
  if (env.VERCEL !== "1") return null;
  const ip = get("x-real-ip")?.trim();
  if (!ip || ip.length > 64 || !/^[0-9a-fA-F.:]+$/.test(ip)) return null;
  return ip.toLowerCase();
}

export async function signInThrottle(email: string) {
  const env = { SNAFI_THROTTLE_SECRET: process.env.SNAFI_THROTTLE_SECRET, VERCEL: process.env.VERCEL };
  const pepper = throttlePepper(env, process.env.NODE_ENV);
  const h = await headers();
  const keys = throttleKeys(pepper, email, trustedClientIp((n) => h.get(n), env));
  const store = throttleAdapter();
  return {
    waitSeconds: () => store.waitSeconds(keys),
    recordFailure: () => store.recordFailure(keys),
  };
}
