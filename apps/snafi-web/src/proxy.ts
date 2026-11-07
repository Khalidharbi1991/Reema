import { NextResponse, type NextRequest } from "next/server";
import { refreshSession } from "@/adapters/supabase/proxy-session";
import { isPreviewMode, readSupabaseConfig } from "@/config/env";

const PUBLIC_PATHS = new Set(["/sign-in"]);

function toSignIn(request: NextRequest) {
  return NextResponse.redirect(new URL("/sign-in", request.url));
}

/** Sends signed-out visitors to /sign-in and keeps the session cookie fresh. */
export async function proxy(request: NextRequest) {
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
    return isPublic ? NextResponse.next() : toSignIn(request);
  }

  if (!config) {
    if (isPreviewMode()) return NextResponse.next();
    return isPublic ? NextResponse.next() : toSignIn(request);
  }

  const { response, signedIn } = await refreshSession(request, config);
  if (!signedIn && !isPublic) return toSignIn(request);
  if (signedIn && isPublic) return NextResponse.redirect(new URL("/today", request.url));
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|icons/|fonts/|sw\\.js|manifest\\.webmanifest|favicon\\.ico).*)"],
};
