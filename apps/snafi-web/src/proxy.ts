import { NextResponse, type NextRequest } from "next/server";
import { refreshSession } from "@/adapters/supabase/proxy-session";
import { isPreviewMode, readSupabaseConfig, siteUrl } from "@/config/env";
import { contentSecurityPolicy, newNonce } from "@/core/security-headers";

const PUBLIC_PATHS = new Set(["/sign-in"]);

/**
 * Redirects go to the fixed site address (SNAFI_SITE_URL or Vercel's own), never
 * to the Host the request claims (SEC-11). On a development server with neither,
 * the request's own origin is used so the phone's Wi-Fi dev mode works.
 */
function redirectTo(path: "/sign-in" | "/today", request: NextRequest, base: string | null) {
  return NextResponse.redirect(new URL(path, base ?? request.nextUrl.origin));
}

function withCsp(response: NextResponse, csp: string) {
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

/** Sends signed-out visitors to /sign-in, keeps the session cookie fresh, and sets the CSP (SEC-3). */
export async function proxy(request: NextRequest) {
  const csp = contentSecurityPolicy(newNonce(), process.env.NODE_ENV === "development");
  // Next.js reads the nonce from the request's CSP header while rendering.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("Content-Security-Policy", csp);
  const next = () => withCsp(NextResponse.next({ request: { headers: requestHeaders } }), csp);

  let base: string | null;
  try {
    base = siteUrl();
  } catch {
    // A production build with no site address: refuse rather than trust the Host header.
    return withCsp(new NextResponse("Snafi is not configured: set SNAFI_SITE_URL.", { status: 500 }), csp);
  }

  const path = request.nextUrl.pathname;
  const isPublic = PUBLIC_PATHS.has(path);

  let config;
  try {
    config = readSupabaseConfig({
      NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
      NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    });
  } catch {
    // Misconfigured: the sign-in page explains; nothing else opens.
    return isPublic ? next() : withCsp(redirectTo("/sign-in", request, base), csp);
  }

  if (!config) {
    if (isPreviewMode()) return next();
    return isPublic ? next() : withCsp(redirectTo("/sign-in", request, base), csp);
  }

  const { response, signedIn } = await refreshSession(request, requestHeaders, config);
  if (!signedIn && !isPublic) return withCsp(redirectTo("/sign-in", request, base), csp);
  if (signedIn && isPublic) return withCsp(redirectTo("/today", request, base), csp);
  return withCsp(response, csp);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|icons/|sw\\.js|offline\\.html|manifest\\.webmanifest|favicon\\.ico).*)"],
};
