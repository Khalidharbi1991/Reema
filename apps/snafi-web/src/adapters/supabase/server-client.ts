import "server-only";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { supabaseConfig } from "@/config/env";
import { requestOrigin } from "@/core/request-origin";
import { sessionCookieOptions } from "./cookie-policy";

/**
 * A Supabase client bound to this request's cookies. Uses the publishable key,
 * so every query runs as the signed-in user under row-level security.
 * Session cookies are HttpOnly, SameSite=Lax and Secure off localhost (SEC-2).
 * Only files in src/adapters/ may import Supabase.
 */
export async function createSupabaseServerClient() {
  const config = supabaseConfig();
  if (!config) return null;
  const store = await cookies();
  // SEC-11: host is client-supplied; used only to flag cookies (see core/request-origin.ts).
  const { host } = await requestOrigin();
  return createServerClient(config.url, config.publishableKey, {
    cookieOptions: sessionCookieOptions(host),
    cookies: {
      getAll: () => store.getAll(),
      setAll: (toSet) => {
        try {
          for (const { name, value, options } of toSet) store.set(name, value, options);
        } catch {
          // Called from a Server Component, where cookies are read-only; the proxy refreshes them.
        }
      },
    },
  });
}
