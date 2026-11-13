import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import type { SupabaseConfig } from "@/config/env";
import { sessionCookieOptions } from "./cookie-policy";

/**
 * Refreshes the Supabase session cookie on each request and reports whether someone
 * is signed in. requestHeaders carries the CSP (SEC-3) on to the page render.
 */
export async function refreshSession(request: NextRequest, requestHeaders: Headers, config: SupabaseConfig) {
  let response = NextResponse.next({ request: { headers: requestHeaders } });
  // SEC-11: these headers come from the client as sent. Use them ONLY to flag the
  // session cookies; NEVER for the sign-in throttle, redirect or callback URLs, or
  // any access decision. Redirects in proxy.ts use the fixed site URL
  // (SNAFI_SITE_URL or Vercel's own address), not this host.
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? request.nextUrl.host;
  const client = createServerClient(config.url, config.publishableKey, {
    cookieOptions: sessionCookieOptions(host),
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (toSet, headers) => {
        for (const { name, value } of toSet) request.cookies.set(name, value);
        // Copy the refreshed cookies into the headers the page is rendered with.
        requestHeaders.set("cookie", request.headers.get("cookie") ?? "");
        response = NextResponse.next({ request: { headers: requestHeaders } });
        for (const { name, value, options } of toSet) response.cookies.set(name, value, options);
        for (const [key, value] of Object.entries(headers ?? {})) response.headers.set(key, value);
      },
    },
  });
  const { data } = await client.auth.getUser();
  return { response, signedIn: Boolean(data.user) };
}
