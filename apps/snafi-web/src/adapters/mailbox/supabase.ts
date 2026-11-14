import "server-only";
import { createSupabaseServerClient } from "@/adapters/supabase/server-client";
import type { Lang } from "@/i18n/messages";
import {
  checkId,
  checkMessageBody,
  MailboxError,
  toTodayFeed,
  type ActionEntry,
  type ApprovalCard,
  type MailboxAdapter,
  type MailboxMessage,
} from "./types";

type MessageRow = {
  id: string; user_id: string; conversation_id: string; role: MailboxMessage["role"]; body: string; lang: Lang;
  job_id: string | null; approval_id: string | null; meta: MailboxMessage["meta"] | null; created_at: string;
};
type ApprovalRow = {
  id: string; conversation_id: string; tool: string; args: Record<string, unknown> | null; args_hash: string;
  summary: string; status: ApprovalCard["status"]; created_at: string; expires_at: string;
};
const CARD_COLUMNS = "id, conversation_id, tool, args, args_hash, summary, status, created_at, expires_at";
type ActionRow = {
  id: string; summary: string; level: number; status: ActionEntry["status"]; undoable: boolean; undo_requested_at: string | null;
};

const toMessage = (r: MessageRow): MailboxMessage => ({
  id: r.id, userId: r.user_id, conversationId: r.conversation_id, role: r.role, body: r.body, lang: r.lang,
  jobId: r.job_id, approvalId: r.approval_id, meta: r.meta ?? {}, createdAt: r.created_at,
});
const toCard = (r: ApprovalRow): ApprovalCard => ({
  id: r.id, conversationId: r.conversation_id, tool: r.tool, args: r.args ?? {}, argsHash: r.args_hash,
  summary: r.summary, status: r.status, createdAt: r.created_at, expiresAt: r.expires_at,
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

  /**
   * The message and its chat.reply job are saved in one transaction (send_chat,
   * migration 0004), so a failure never leaves a message in the chat with no reply
   * queued. send_chat runs as the signed-in user, under the same grants and RLS.
   */
  async sendChat(input: { conversationId: string; body: string; lang: Lang }) {
    const { data, error } = await (await this.client()).rpc("send_chat", {
      p_conversation_id: checkId(input.conversationId), p_body: checkMessageBody(input.body), p_lang: input.lang,
    });
    if (error) throw new MailboxError(error.message);
    return toMessage(data as MessageRow);
  }

  async approvals(ids: string[]) {
    if (!ids.length) return [];
    const { data, error } = await (await this.client()).from("approvals").select(CARD_COLUMNS)
      .in("id", ids.map(checkId));
    if (error) throw new MailboxError(error.message);
    return (data as ApprovalRow[]).map(toCard);
  }

  async pendingApprovals(limit = 10) {
    const { data, error } = await (await this.client()).from("approvals").select(CARD_COLUMNS)
      .eq("status", "pending").gt("expires_at", new Date().toISOString()).order("created_at", { ascending: false }).limit(limit);
    if (error) throw new MailboxError(error.message);
    return (data as ApprovalRow[]).map(toCard);
  }

  async decideApproval(id: string, decision: "approved" | "rejected", argsHash: string) {
    if (!/^[0-9a-f]{64}$/.test(argsHash)) throw new MailboxError("invalid arguments hash");
    const { data, error } = await (await this.client()).rpc("decide_approval", {
      p_id: checkId(id), p_decision: decision, p_args_hash: argsHash,
    });
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

  async todayFeed() {
    const { data, error } = await (await this.client()).from("today_feed")
      .select("next_event, emails, google_status, updated_at").maybeSingle();
    if (error) throw new MailboxError(error.message);
    return data ? toTodayFeed(data) : null;
  }
}
