import "server-only";
import { createSupabaseServerClient } from "@/adapters/supabase/server-client";
import type { Lang } from "@/i18n/messages";
import {
  checkId,
  checkMessageBody,
  MailboxError,
  type ActionEntry,
  type ApprovalCard,
  type MailboxAdapter,
  type MailboxMessage,
} from "./types";

type MessageRow = {
  id: string; user_id: string; conversation_id: string; role: MailboxMessage["role"]; body: string; lang: Lang;
  job_id: string | null; approval_id: string | null; meta: MailboxMessage["meta"] | null; created_at: string;
};
type ApprovalRow = { id: string; conversation_id: string; summary: string; status: ApprovalCard["status"]; created_at: string };
type ActionRow = {
  id: string; summary: string; level: number; status: ActionEntry["status"]; undoable: boolean; undo_requested_at: string | null;
};

const toMessage = (r: MessageRow): MailboxMessage => ({
  id: r.id, userId: r.user_id, conversationId: r.conversation_id, role: r.role, body: r.body, lang: r.lang,
  jobId: r.job_id, approvalId: r.approval_id, meta: r.meta ?? {}, createdAt: r.created_at,
});
const toCard = (r: ApprovalRow): ApprovalCard => ({
  id: r.id, conversationId: r.conversation_id, summary: r.summary, status: r.status, createdAt: r.created_at,
});
const toAction = (r: ActionRow): ActionEntry => ({
  id: r.id, summary: r.summary, level: r.level, status: r.status, undoable: r.undoable, undoRequested: !!r.undo_requested_at,
});

/**
 * Supabase mailbox. Runs as the signed-in user with the publishable key, so the
 * row-level security policies in supabase/migrations decide what is visible.
 * user_id is filled by the database (auth.uid()), never by the app; approvals and
 * Undo go only through the decide_approval and request_undo functions.
 */
export class SupabaseMailboxAdapter implements MailboxAdapter {
  private async client() {
    const client = await createSupabaseServerClient();
    if (!client) throw new MailboxError("Supabase is not configured");
    return client;
  }

  async listMessages(conversationId: string, limit = 50) {
    const { data, error } = await (await this.client())
      .from("messages").select("*").eq("conversation_id", checkId(conversationId))
      .order("created_at", { ascending: false }).limit(limit);
    if (error) throw new MailboxError(error.message);
    return (data as MessageRow[]).map(toMessage).reverse();
  }

  async sendChat(input: { conversationId: string; body: string; lang: Lang }) {
    const client = await this.client();
    const conversationId = checkId(input.conversationId);
    const { data, error } = await client.from("messages")
      .insert({ conversation_id: conversationId, role: "user", body: checkMessageBody(input.body), lang: input.lang })
      .select("*").single();
    if (error) throw new MailboxError(error.message);
    const message = toMessage(data as MessageRow);
    const job = await client.from("jobs")
      .insert({ kind: "chat.reply", payload: { message_id: message.id }, conversation_id: conversationId });
    if (job.error) throw new MailboxError(job.error.message);
    return message;
  }

  async approvals(ids: string[]) {
    if (!ids.length) return [];
    const { data, error } = await (await this.client()).from("approvals").select("id, conversation_id, summary, status, created_at")
      .in("id", ids.map(checkId));
    if (error) throw new MailboxError(error.message);
    return (data as ApprovalRow[]).map(toCard);
  }

  async pendingApprovals(limit = 10) {
    const { data, error } = await (await this.client()).from("approvals").select("id, conversation_id, summary, status, created_at")
      .eq("status", "pending").order("created_at", { ascending: false }).limit(limit);
    if (error) throw new MailboxError(error.message);
    return (data as ApprovalRow[]).map(toCard);
  }

  async decideApproval(id: string, decision: "approved" | "rejected") {
    const { data, error } = await (await this.client()).rpc("decide_approval", { p_id: checkId(id), p_decision: decision });
    if (error) throw new MailboxError(error.message);
    return toCard(data as ApprovalRow);
  }

  async actions(ids: string[]) {
    if (!ids.length) return [];
    const { data, error } = await (await this.client()).from("action_log")
      .select("id, summary, level, status, undoable, undo_requested_at").in("id", ids.map(checkId));
    if (error) throw new MailboxError(error.message);
    return (data as ActionRow[]).map(toAction);
  }

  async requestUndo(actionId: string) {
    const { error } = await (await this.client()).rpc("request_undo", { p_action_id: checkId(actionId) });
    if (error) throw new MailboxError(error.message);
  }

  async workerStatus() {
    const { data, error } = await (await this.client()).from("worker_status")
      .select("last_seen, last_backup_at, last_backup_ok, last_backup_error").maybeSingle();
    if (error) throw new MailboxError(error.message);
    if (!data) return null;
    const r = data as { last_seen: string; last_backup_at: string | null; last_backup_ok: boolean | null; last_backup_error: string | null };
    return { lastSeen: r.last_seen, lastBackupAt: r.last_backup_at, lastBackupOk: r.last_backup_ok, lastBackupError: r.last_backup_error };
  }
}
