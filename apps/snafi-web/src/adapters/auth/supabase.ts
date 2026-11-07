import "server-only";
import { createSupabaseServerClient, requestOrigin } from "@/adapters/supabase/server-client";
import type { AuthAdapter, SignInResult } from "./types";
import { cleanCredentials } from "./validate";

/** Email and password sign-in through Supabase Auth. There is no sign-up call anywhere. */
export class SupabaseAuthAdapter implements AuthAdapter {
  async signInWithPassword(email: string, password: string): Promise<SignInResult> {
    const creds = cleanCredentials(email, password);
    if (!creds) return { ok: false, error: "missing" };
    // SEC-1/SEC-2: no real sign-in over plain HTTP except on this PC.
    if (!(await requestOrigin()).secure) return { ok: false, error: "insecure" };
    const client = await createSupabaseServerClient();
    if (!client) return { ok: false, error: "not_configured" };
    try {
      const { data, error } = await client.auth.signInWithPassword(creds);
      if (error || !data.user) {
        // 400-range errors mean wrong credentials; do not say which part was wrong.
        return { ok: false, error: error && (error.status ?? 500) >= 500 ? "unavailable" : "invalid" };
      }
      return { ok: true, user: { id: data.user.id, email: data.user.email ?? null } };
    } catch {
      return { ok: false, error: "unavailable" };
    }
  }

  async signOut() {
    const client = await createSupabaseServerClient();
    await client?.auth.signOut();
  }

  async currentUser() {
    const client = await createSupabaseServerClient();
    if (!client) return null;
    // getUser() checks the token with Supabase, unlike getSession().
    const { data, error } = await client.auth.getUser();
    if (error || !data.user) return null;
    return { id: data.user.id, email: data.user.email ?? null };
  }
}
