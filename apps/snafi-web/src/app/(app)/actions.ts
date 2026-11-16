"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { authAdapter } from "@/adapters";
import { MailboxError } from "@/adapters/mailbox/types";
import { isPreviewMode } from "@/config/env";
import { getPreferences } from "@/core/server-preferences";
import { conversationId, mailboxFor, requireSession } from "@/core/session";

export async function signOut() {
  if (!isPreviewMode()) await authAdapter().signOut();
  redirect("/sign-in");
}

export type ChatState = { error: boolean; sentAt: number };

/** Posts Khalid's message and queues Ahmad's reply. The worker does the rest. */
export async function sendMessage(_prev: ChatState, form: FormData): Promise<ChatState> {
  const session = await requireSession();
  const { lang } = await getPreferences();
  try {
    await mailboxFor(session).sendChat({
      conversationId: conversationId(session), body: String(form.get("body") ?? ""), lang,
    });
  } catch {
    return { error: true, sentAt: Date.now() };
  }
  revalidatePath("/chat");
  return { error: false, sentAt: Date.now() };
}

/** Approve or Reject a card. Only the database function can change it, once. */
export async function decideApproval(
  id: string, decision: "approved" | "rejected", argsHash: string,
): Promise<{ ok: boolean; status?: string }> {
  if (decision !== "approved" && decision !== "rejected") return { ok: false };
  const session = await requireSession();
  let status: string;
  try {
    status = (await mailboxFor(session).decideApproval(id, decision, argsHash)).status;
  } catch {
    return { ok: false };
  }
  revalidatePath("/chat");
  revalidatePath("/today");
  revalidatePath("/inbox");
  return { ok: true, status };
}

// ---------- the Inbox, settings and push ----------
/**
 * Marks one of Khalid's own cards read (opened in the Inbox). The card stays unread when it
 * fails. Quiet only when the database has no mark_card_read yet (PRD risk 7); any other
 * failure is reported like the other actions, with `reported` so the screen can say so
 * (SEC-172). It never throws into the Inbox.
 */
export async function markCardRead(id: string): Promise<{ ok: boolean; reported?: boolean }> {
  const session = await requireSession();
  try {
    await mailboxFor(session).markCardRead(String(id ?? ""));
  } catch (error) {
    return { ok: false, reported: !(error instanceof MailboxError && error.schemaMissing) };
  }
  return { ok: true };
}

export type SettingsInput = { pushEnabled: boolean; briefTime: string; dailyCap: number };

/** Saves the Settings screen. The language comes from the app's own preference (for lock-screen text). */
export async function saveSettings(input: SettingsInput): Promise<{ ok: boolean }> {
  const session = await requireSession();
  const { lang } = await getPreferences();
  try {
    await mailboxFor(session).saveSettings({
      pushEnabled: input?.pushEnabled === true, briefTime: String(input?.briefTime ?? ""),
      dailyCap: Number(input?.dailyCap), lang,
    });
  } catch {
    return { ok: false };
  }
  // No revalidatePath("/settings"): the form keeps its own values, and a page refresh after Save only
  // added a wait before the button came back (live bug, Nov 15, 2026).
  return { ok: true };
}

export async function savePushSubscription(keys: { endpoint: string; p256dh: string; auth: string }): Promise<{ ok: boolean }> {
  const session = await requireSession();
  try {
    await mailboxFor(session).savePushSubscription({
      endpoint: String(keys?.endpoint ?? ""), p256dh: String(keys?.p256dh ?? ""), auth: String(keys?.auth ?? ""),
    });
  } catch {
    return { ok: false };
  }
  return { ok: true };
}

export async function removePushSubscription(endpoint: string): Promise<{ ok: boolean }> {
  const session = await requireSession();
  try {
    await mailboxFor(session).removePushSubscription(String(endpoint ?? ""));
  } catch {
    return { ok: false };
  }
  return { ok: true };
}

export async function requestTestPush(): Promise<{ ok: boolean }> {
  const session = await requireSession();
  try {
    await mailboxFor(session).requestTestPush();
  } catch {
    return { ok: false };
  }
  return { ok: true };
}

export async function undoAction(actionId: string): Promise<{ ok: boolean }> {
  const session = await requireSession();
  try {
    await mailboxFor(session).requestUndo(actionId);
  } catch {
    return { ok: false };
  }
  revalidatePath("/chat");
  return { ok: true };
}
