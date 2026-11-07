"use server";

import { redirect } from "next/navigation";
import { authAdapter } from "@/adapters";
import { ConfigError, supabaseConfig } from "@/config/env";
import type { SignInResult } from "@/adapters/auth/types";

export type SignInState = { error: Exclude<SignInResult, { ok: true }>["error"] | null };

export async function signIn(_prev: SignInState, form: FormData): Promise<SignInState> {
  try {
    if (!supabaseConfig()) return { error: "not_configured" };
  } catch (e) {
    if (e instanceof ConfigError) return { error: "not_configured" };
    throw e;
  }
  const result = await authAdapter().signInWithPassword(String(form.get("email") ?? ""), String(form.get("password") ?? ""));
  if (!result.ok) return { error: result.error };
  redirect("/today");
}
