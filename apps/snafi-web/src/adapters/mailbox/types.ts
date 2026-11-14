/**
 * The mailbox between the phone app and the PC worker. Supabase today; any Postgres
 * later. The app posts Khalid's own words, decides approval cards, asks for Undo and
 * reads results; everything else is done by the worker.
 */
import type { Lang } from "@/i18n/messages";

export type MessageRole = "user" | "assistant" | "system";

export type MailboxMessage = {
  id: string;
  userId: string;
  conversationId: string;
  role: MessageRole;
  body: string;
  lang: Lang;
  jobId: string | null;
  approvalId: string | null;
  meta: { kind?: string; actions?: string[]; approvals?: string[] };
  createdAt: string;
};

export type ApprovalStatus = "pending" | "approved" | "executing" | "rejected" | "executed" | "failed" | "expired";
/** A Level 3 action waiting for Khalid. `args` is exactly what will run; `argsHash` binds Approve to it (SEC-13). */
export type ApprovalCard = {
  id: string;
  conversationId: string;
  tool: string;
  args: Record<string, unknown>;
  argsHash: string;
  summary: string;
  status: ApprovalStatus;
  createdAt: string;
  expiresAt: string;
};

/** A pending card past its expiry shows as expired; the database refuses to approve it. */
export function effectiveStatus(card: ApprovalCard, now: Date): ApprovalStatus {
  return card.status === "pending" && new Date(card.expiresAt).getTime() <= now.getTime() ? "expired" : card.status;
}

export type ActionEntry = {
  id: string;
  summary: string;
  level: number;
  status: "done" | "failed" | "undone";
  undoable: boolean;
  undoRequested: boolean;
};

export type WorkerStatus = {
  lastSeen: string;
  lastBackupAt: string | null;
  lastBackupOk: boolean | null;
  lastBackupError: string | null;
};

/**
 * The worker's snapshot for Today (steps 3 and 4). Written by the PC only: senders and subjects (never
 * bodies), each email's account, and today's Todoist tasks (never descriptions).
 */
export type GoogleStatus = "ok" | "off" | "not_connected" | "reconnect" | "error";
/** Yahoo and Todoist report the same states as Google. */
export type SourceStatus = GoogleStatus;
export type MailAccount = "gmail" | "yahoo";
export type TodayFeed = {
  nextEvent: { title: string; start: string; end: string; location: string; allDay: boolean } | null;
  emails: { from: string; subject: string; receivedAt: string; account: MailAccount }[];
  tasks: { content: string; due: string; priority: 1 | 2 | 3 | 4; overdue: boolean; recurring: boolean }[];
  googleStatus: GoogleStatus;
  yahooStatus: SourceStatus;
  todoistStatus: SourceStatus;
  updatedAt: string;
};

export const MAX_MESSAGE_LENGTH = 8000;
/** The app shows "PC offline" when the worker's heartbeat is older than this. */
export const OFFLINE_AFTER_MS = 45_000;

export interface MailboxAdapter {
  /** Newest last; only the signed-in user's own messages. */
  listMessages(conversationId: string, limit?: number): Promise<MailboxMessage[]>;
  /** Posts Khalid's message and queues Ahmad's reply (a chat.reply job). */
  sendChat(input: { conversationId: string; body: string; lang: Lang }): Promise<MailboxMessage>;
  approvals(ids: string[]): Promise<ApprovalCard[]>;
  pendingApprovals(limit?: number): Promise<ApprovalCard[]>;
  /** Pending -> approved or rejected, once, for exactly the arguments shown; the database queues the worker's follow-up. */
  decideApproval(id: string, decision: "approved" | "rejected", argsHash: string): Promise<ApprovalCard>;
  actions(ids: string[]): Promise<ActionEntry[]>;
  /** Asks the worker to undo a Level 2 action. */
  requestUndo(actionId: string): Promise<void>;
  workerStatus(): Promise<WorkerStatus | null>;
  /** The worker's latest Google snapshot for Today, or null before the first one. */
  todayFeed(): Promise<TodayFeed | null>;
}

const STATUSES: readonly GoogleStatus[] = ["ok", "off", "not_connected", "reconnect", "error"];
const text = (v: unknown, max: number) => (typeof v === "string" ? v.slice(0, max) : "");

const status = (v: unknown, missing: GoogleStatus): GoogleStatus =>
  v === undefined || v === null ? missing : STATUSES.includes(v as GoogleStatus) ? (v as GoogleStatus) : "error";

/**
 * A today_feed row made safe for the screen: known fields only, text cut to size, at most five emails
 * from each account (ten in all) and ten tasks. An email without a known account is Gmail (step 3 rows).
 */
export function toTodayFeed(row: {
  next_event?: unknown; emails?: unknown; tasks?: unknown; google_status?: unknown; yahoo_status?: unknown;
  todoist_status?: unknown; updated_at?: unknown;
}): TodayFeed {
  const e = row.next_event && typeof row.next_event === "object" ? (row.next_event as Record<string, unknown>) : null;
  const emails = (Array.isArray(row.emails) ? row.emails : []).filter((m) => m && typeof m === "object") as Record<string, unknown>[];
  const tasks = (Array.isArray(row.tasks) ? row.tasks : []).filter((t) => t && typeof t === "object") as Record<string, unknown>[];
  const counts: Record<MailAccount, number> = { gmail: 0, yahoo: 0 };
  return {
    nextEvent: e && text(e.start, 40)
      ? { title: text(e.title, 200), start: text(e.start, 40), end: text(e.end, 40), location: text(e.location, 200), allDay: e.all_day === true }
      : null,
    emails: emails
      .map((r) => ({ from: text(r.from, 120), subject: text(r.subject, 200), receivedAt: text(r.received_at, 40),
        account: (r.account === "yahoo" ? "yahoo" : "gmail") as MailAccount }))
      .filter((m) => ++counts[m.account] <= 5)
      .slice(0, 10),
    tasks: tasks.slice(0, 10).map((r) => {
      const p = typeof r.priority === "number" && [1, 2, 3, 4].includes(r.priority) ? (r.priority as 1 | 2 | 3 | 4) : 4;
      return { content: text(r.content, 200), due: text(r.due, 40), priority: p, overdue: r.overdue === true, recurring: r.recurring === true };
    }),
    googleStatus: status(row.google_status, "error"),
    // Rows written before step 4 have no Yahoo or Todoist column: those sources are off.
    yahooStatus: status(row.yahoo_status, "off"),
    todoistStatus: status(row.todoist_status, "off"),
    updatedAt: text(row.updated_at, 40),
  };
}

export class MailboxError extends Error {}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function checkMessageBody(body: string): string {
  const trimmed = body.trim();
  if (!trimmed) throw new MailboxError("empty message");
  if (trimmed.length > MAX_MESSAGE_LENGTH) throw new MailboxError("message too long");
  return trimmed;
}

export function checkId(id: string): string {
  if (!UUID.test(id)) throw new MailboxError("invalid id");
  return id.toLowerCase();
}

export function isOnline(status: WorkerStatus | null, now: Date): boolean {
  return !!status && now.getTime() - new Date(status.lastSeen).getTime() <= OFFLINE_AFTER_MS;
}
