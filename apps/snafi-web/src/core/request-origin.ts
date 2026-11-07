import "server-only";
import { headers } from "next/headers";
import { isSecureRequest } from "./connection";

/**
 * Host and protocol of the current request, decided on the server (SEC-10),
 * so the sign-in form can start switched off over plain HTTP.
 *
 * SEC-11: x-forwarded-host, host and x-forwarded-proto come from the client as
 * sent; Next.js only fills them in when they are missing. Use them ONLY to decide
 * whether to show the sign-in form and how to flag cookies, where a forged value
 * harms only the forger's own connection. NEVER use them for the sign-in throttle
 * (SEC-4), redirect or callback URLs, or any access decision.
 */
export async function requestOrigin() {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  // Hosts such as Vercel set x-forwarded-proto; without it, only localhost counts as safe.
  const protocol = h.get("x-forwarded-proto");
  return { host, protocol, secure: isSecureRequest(host, protocol) };
}
