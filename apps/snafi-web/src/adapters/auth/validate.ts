/** Shared input checks so every auth adapter treats input the same way. */
export function cleanCredentials(email: unknown, password: unknown): { email: string; password: string } | null {
  if (typeof email !== "string" || typeof password !== "string") return null;
  const e = email.trim().toLowerCase();
  if (!e || !password || e.length > 254 || password.length > 1024) return null;
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) return null;
  return { email: e, password };
}
