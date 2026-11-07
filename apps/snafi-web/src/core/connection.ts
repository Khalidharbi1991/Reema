/** Is this connection safe to send a password over? Pure functions; no headers read here. */

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

/** True when the request is HTTPS or comes to this PC's own name (localhost). */
export function isSecureRequest(host: string | null | undefined, protocol: string | null | undefined): boolean {
  const proto = (protocol ?? "").toLowerCase().replace(/:$/, "").split(",")[0].trim();
  return proto === "https" || isLocalHost(host);
}
