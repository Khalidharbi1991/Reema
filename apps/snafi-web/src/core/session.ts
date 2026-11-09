import "server-only";
import { redirect } from "next/navigation";
import { authAdapter, mailboxAdapter, PREVIEW_USER } from "@/adapters";
import type { MailboxAdapter } from "@/adapters/mailbox/types";
import { ConfigError, isPreviewMode, supabaseConfig } from "@/config/env";

export type Session = { preview: true; userId: null } | { preview: false; userId: string };

/** Checked on every protected page and server action, in addition to the proxy (SEC-6). */
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

/** Khalid's one conversation with Ahmad (one per user for now). */
export function conversationId(session: Session): string {
  return session.userId ?? PREVIEW_USER;
}

export function mailboxFor(session: Session): MailboxAdapter {
  return mailboxAdapter(session.userId);
}
