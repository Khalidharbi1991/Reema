import "server-only";
import { redirect } from "next/navigation";
import { authAdapter } from "@/adapters";
import { ConfigError, isPreviewMode, supabaseConfig } from "@/config/env";

export type Session = { preview: true; userId: null } | { preview: false; userId: string };

/** Checked on every protected page, in addition to the proxy. */
export async function requireSession(): Promise<Session> {
  if (isPreviewMode()) return { preview: true, userId: null };
  try {
    if (!supabaseConfig()) redirect("/sign-in");
  } catch (e) {
    if (e instanceof ConfigError) redirect("/sign-in");
    throw e;
  }
  const user = await authAdapter().currentUser();
  if (!user) redirect("/sign-in");
  return { preview: false, userId: user.id };
}
