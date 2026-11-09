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
