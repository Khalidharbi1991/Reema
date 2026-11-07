import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import type { SupabaseConfig } from "@/config/env";
import { sessionCookieOptions } from "./cookie-policy";

/** Refreshes the Supabase session cookie on each request and reports whether someone is signed in. */
export async function refreshSession(request: NextRequest, config: SupabaseConfig) {
  let response = NextResponse.next({ request });
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? request.nextUrl.host;
  const client = createServerClient(config.url, config.publishableKey, {
    cookieOptions: sessionCookieOptions(host),
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (toSet, headers) => {
        for (const { name, value } of toSet) request.cookies.set(name, value);
        response = NextResponse.next({ request });
        for (const { name, value, options } of toSet) response.cookies.set(name, value, options);
        for (const [key, value] of Object.entries(headers ?? {})) response.headers.set(key, value);
      },
    },
  });
  const { data } = await client.auth.getUser();
  return { response, signedIn: Boolean(data.user) };
}
