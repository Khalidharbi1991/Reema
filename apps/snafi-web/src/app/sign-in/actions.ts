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
  const creds = cleanCredentials(String(form.get("email") ?? ""), String(form.get("password") ?? ""));
  if (!creds) return { error: "missing" };

  // SEC-4: every try is counted BEFORE Supabase is asked, one at a time per key
  // (SEC-72): 5 in 15 minutes per email (and per client IP on Vercel), then wait.
  // Fails closed if the store cannot be reached.
  let throttle: Awaited<ReturnType<typeof signInThrottle>>;
  let attempt: string;
  try {
    throttle = await signInThrottle(creds.email);
    const ticket = await throttle.begin();
    if (ticket.wait > 0 || !ticket.attempt) return { error: "throttled" };
    attempt = ticket.attempt;
  } catch {
    return { error: "unavailable" };
  }

  const result = await authAdapter().signInWithPassword(creds.email, creds.password);
  // Only a wrong password keeps its count; anything else is taken back.
  if (result.ok || result.error !== "invalid") {
    try {
      await throttle.forget(attempt);
    } catch {
      // The try stays counted: safe, it only makes the limit stricter.
    }
  }
  if (!result.ok) return { error: result.error };
  redirect("/today");
}
