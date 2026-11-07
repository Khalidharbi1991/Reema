import "server-only";
import { createServerClient } from "@supabase/ssr";
import { cookies, headers } from "next/headers";
import { supabaseConfig } from "@/config/env";
import { isSecureRequest, sessionCookieOptions } from "./cookie-policy";

/** Host and protocol of the current request, as the browser sees them. */
export async function requestOrigin() {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  // Hosts such as Vercel set x-forwarded-proto; without it, only localhost counts as safe.
  const protocol = h.get("x-forwarded-proto");
  return { host, protocol, secure: isSecureRequest(host, protocol) };
}

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
