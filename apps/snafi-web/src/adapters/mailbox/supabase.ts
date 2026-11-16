import "server-only";
import { createSupabaseServerClient } from "@/adapters/supabase/server-client";
import type { Lang } from "@/i18n/messages";
import {
  checkId,
  checkMessageBody,
  checkPushKeys,
  checkSettings,
  DEFAULT_SETTINGS,
  MailboxError,
  READ_KEEP_MS,
  toCard as toAhmadCard,
  toTodayFeed,
  type ActionEntry,
  type ApprovalCard,
  type MailboxAdapter,
  type MailboxMessage,
  type PushKeys,
  type Settings,
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

/**
 * "That column or function is not there": Postgres undefined_column and undefined_function, and
 * PostgREST's own codes when its schema cache has no such column or function. Nothing else counts
 * as a missing migration (SEC-172).
 */
const MISSING_SCHEMA_CODES: readonly string[] = ["42703", "42883", "PGRST204", "PGRST202"];
const schemaMissing = (error: { code?: string | null } | null | undefined): boolean =>
  !!error?.code && MISSING_SCHEMA_CODES.includes(error.code);

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
      .select("next_event, emails, tasks, google_status, yahoo_status, todoist_status, updated_at").maybeSingle();
    if (error) throw new MailboxError(error.message);
    return data ? toTodayFeed(data) : null;
  }

  // ---------- step 5 and the Inbox ----------
  /**
   * Not dismissed, and unread or read less than 7 days ago. Before migration 0009 is run the
   * read_at column does not exist: only then is the old query used, and every card shows as
   * unread. Any other error is passed on, so the screen says it could not load instead of
   * quietly showing read and cleared cards as new (SEC-172).
   */
  async cards(limit = 10) {
    const client = await this.client();
    const cutoff = new Date(Date.now() - READ_KEEP_MS).toISOString();
    const withRead = await client.from("cards").select("id, kind, title, body, created_at, read_at")
      .is("dismissed_at", null).or(`read_at.is.null,read_at.gt.${cutoff}`)
      .order("created_at", { ascending: false }).limit(limit);
    if (!withRead.error) return (withRead.data ?? []).map(toAhmadCard);
    if (!schemaMissing(withRead.error)) throw new MailboxError(withRead.error.message);
    const { data, error } = await client.from("cards").select("id, kind, title, body, created_at")
      .is("dismissed_at", null).order("created_at", { ascending: false }).limit(limit);
    if (error) throw new MailboxError(error.message);
    return (data ?? []).map(toAhmadCard);
  }

  /**
   * Throws either way; the card stays unread. The error says `schemaMissing` only when the
   * database has no mark_card_read yet, and only then does the caller stay silent (SEC-172).
   */
  async markCardRead(id: string) {
    const { error } = await (await this.client()).rpc("mark_card_read", { p_id: checkId(id) });
    if (error) throw new MailboxError(error.message, schemaMissing(error));
  }

  async settings(): Promise<Settings> {
    const { data, error } = await (await this.client()).from("user_settings")
      .select("push_enabled, brief_time, daily_cap, lang").maybeSingle();
    if (error) throw new MailboxError(error.message);
    if (!data) return { ...DEFAULT_SETTINGS };
    const r = data as { push_enabled: boolean; brief_time: string; daily_cap: number; lang: "en" | "ar" };
    return { pushEnabled: r.push_enabled, briefTime: r.brief_time, dailyCap: r.daily_cap, lang: r.lang };
  }

  async saveSettings(s: Settings) {
    const v = checkSettings(s);
    const { error } = await (await this.client()).rpc("save_settings", {
      p_push_enabled: v.pushEnabled, p_brief_time: v.briefTime, p_daily_cap: v.dailyCap, p_lang: v.lang,
    });
    if (error) throw new MailboxError(error.message);
    return v;
  }

  async savePushSubscription(k: PushKeys) {
    const v = checkPushKeys(k);
    const { error } = await (await this.client()).rpc("save_push_subscription", {
      p_endpoint: v.endpoint, p_p256dh: v.p256dh, p_auth: v.auth,
    });
    if (error) throw new MailboxError(error.message);
  }

  async removePushSubscription(endpoint: string) {
    if (typeof endpoint !== "string" || endpoint.length > 1000) throw new MailboxError("invalid push address");
    const { error } = await (await this.client()).rpc("remove_push_subscription", { p_endpoint: endpoint });
    if (error) throw new MailboxError(error.message);
  }

  /** "Turn off on all phones" (SEC-153 follow-up, migration 0011): every address, and push off. */
  async removeAllPushSubscriptions() {
    const { data, error } = await (await this.client()).rpc("remove_all_push_subscriptions");
    if (error) throw new MailboxError(error.message, schemaMissing(error));
    return typeof data === "number" ? data : 0;
  }

  async requestTestPush() {
    const { error } = await (await this.client()).rpc("request_test_push");
    if (error) throw new MailboxError(error.message);
  }
}
