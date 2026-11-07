/**
 * Session cookie rules (SEC-2): HttpOnly, SameSite=Lax, and Secure everywhere
 * except on this PC (localhost), where the dev server runs over plain HTTP.
 * The app has no browser-side Supabase client, so scripts never need the cookie.
 */
import { isLocalHost } from "@/core/connection";

export { isLocalHost, isSecureRequest } from "@/core/connection";

export type SessionCookieOptions = { httpOnly: true; sameSite: "lax"; path: "/"; secure: boolean };

export function sessionCookieOptions(host: string | null | undefined): SessionCookieOptions {
  return { httpOnly: true, sameSite: "lax", path: "/", secure: !isLocalHost(host) };
}
