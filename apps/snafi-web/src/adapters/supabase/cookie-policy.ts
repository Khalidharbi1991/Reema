/**
 * Session cookie rules (SEC-2): HttpOnly, SameSite=Lax, and Secure everywhere
 * except on this PC (localhost), where the dev server runs over plain HTTP.
 * The app has no browser-side Supabase client, so scripts never need the cookie.
 */
export type SessionCookieOptions = { httpOnly: true; sameSite: "lax"; path: "/"; secure: boolean };

function hostname(host: string | null | undefined): string {
  if (!host) return "";
  const h = host.trim().toLowerCase();
  if (h.startsWith("[")) return h.slice(0, h.indexOf("]") + 1); // [::1]:3000
  return h.split(":")[0];
}

export function isLocalHost(host: string | null | undefined): boolean {
  const h = hostname(host);
  return h === "localhost" || h === "127.0.0.1" || h === "[::1]" || h === "::1" || h.endsWith(".localhost");
}

/** True when the browser will keep a Secure cookie for this request. */
export function isSecureRequest(host: string | null | undefined, protocol: string | null | undefined): boolean {
  const proto = (protocol ?? "").toLowerCase().replace(/:$/, "").split(",")[0].trim();
  return proto === "https" || isLocalHost(host);
}

export function sessionCookieOptions(host: string | null | undefined): SessionCookieOptions {
  return { httpOnly: true, sameSite: "lax", path: "/", secure: !isLocalHost(host) };
}
