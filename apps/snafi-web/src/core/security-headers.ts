/**
 * SEC-3: the Content-Security-Policy, built per request with a fresh nonce in
 * src/proxy.ts. Next.js reads the nonce from the request's CSP header and puts it
 * on its own scripts and inline styles. Pure functions; no headers are read here.
 */

/** A fresh, unguessable nonce for one response (128 random bits, base64). */
export function newNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

export function contentSecurityPolicy(nonce: string, dev: boolean): string {
  if (!/^[A-Za-z0-9+/]{22}==$/.test(nonce)) throw new Error("invalid nonce");
  return [
    "default-src 'self'",
    // React needs eval only in development (error stacks); never in a production build.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'nonce-${nonce}'`,
    // style="" attributes (animation order, sizes) carry no script; nonces cannot cover attributes.
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    // The browser talks only to this site; Supabase is called from the server.
    "connect-src 'self'",
    "worker-src 'self'",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    // Not in development: the phone's Wi-Fi dev mode is plain HTTP.
    ...(dev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");
}

/** SEC-3: two years, this host and its subdomains. Browsers ignore it over plain HTTP. */
export const HSTS = "max-age=63072000; includeSubDomains";
