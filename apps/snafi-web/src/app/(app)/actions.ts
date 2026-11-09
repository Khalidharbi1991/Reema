"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { authAdapter } from "@/adapters";
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
  return { ok: true, status };
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
