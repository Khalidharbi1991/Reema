"use server";

import { redirect } from "next/navigation";
import { authAdapter } from "@/adapters";
import { cleanCredentials } from "@/adapters/auth/validate";
import { ConfigError, supabaseConfig } from "@/config/env";
import type { SignInResult } from "@/adapters/auth/types";
import { signInThrottle } from "@/core/signin-throttle";

export type SignInState = { error: Exclude<SignInResult, { ok: true }>["error"] | "throttled" | null };

export async function signIn(_prev: SignInState, form: FormData): Promise<SignInState> {
  try {
    if (!supabaseConfig()) return { error: "not_configured" };
  } catch (e) {
    if (e instanceof ConfigError) return { error: "not_configured" };
    throw e;
  }
  const email = String(form.get("email") ?? "");
  const password = String(form.get("password") ?? "");
  const creds = cleanCredentials(email, password);
  if (!creds) return { error: "missing" };

  // SEC-4: 5 wrong passwords in 15 minutes per email (and per client IP on Vercel),
  // then wait. Checked before Supabase is asked; fails closed if the store is unreachable.
  let throttle: Awaited<ReturnType<typeof signInThrottle>>;
  try {
    throttle = await signInThrottle(creds.email);
    if ((await throttle.waitSeconds()) > 0) return { error: "throttled" };
  } catch {
    return { error: "unavailable" };
  }

  const result = await authAdapter().signInWithPassword(creds.email, creds.password);
  if (!result.ok) {
    if (result.error === "invalid") {
      try {
        await throttle.recordFailure();
      } catch {
        // The answer stays "invalid"; a store outage blocks the next try at waitSeconds.
      }
    }
    return { error: result.error };
  }
  redirect("/today");
}
