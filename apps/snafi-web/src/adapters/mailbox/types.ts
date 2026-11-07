/**
 * The mailbox between the phone app and the PC worker. Supabase today; any
 * Postgres later. Step 1 defines it; the screens do not write to it yet.
 */
import type { Lang } from "@/i18n/messages";

export type MessageRole = "user" | "assistant" | "system";
export type JobStatus = "queued" | "claimed" | "running" | "done" | "failed" | "cancelled";

export type MailboxMessage = {
  id: string;
  userId: string;
  conversationId: string;
  role: MessageRole;
  body: string;
  lang: Lang;
  jobId: string | null;
  createdAt: string;
};

export type MailboxJob = {
  id: string;
  userId: string;
  kind: string;
  status: JobStatus;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
};

export const MAX_MESSAGE_LENGTH = 8000;
export const JOB_KIND_PATTERN = /^[a-z][a-z0-9_.]{0,63}$/;

export interface MailboxAdapter {
  /** Newest last; only the signed-in user's own messages. */
  listMessages(conversationId: string, limit?: number): Promise<MailboxMessage[]>;
  /** The app may only post the user's own words; Ahmad's replies come from the PC worker. */
  postUserMessage(input: { conversationId: string; body: string; lang: Lang }): Promise<MailboxMessage>;
  /** Queue work for the PC worker. The app can create jobs but never change their status. */
  enqueueJob(input: { kind: string; payload: Record<string, unknown> }): Promise<MailboxJob>;
  listJobs(limit?: number): Promise<MailboxJob[]>;
}

export class MailboxError extends Error {}

export function checkMessageBody(body: string): string {
  const trimmed = body.trim();
  if (!trimmed) throw new MailboxError("empty message");
  if (trimmed.length > MAX_MESSAGE_LENGTH) throw new MailboxError("message too long");
  return trimmed;
}

export function checkJobKind(kind: string): string {
  if (!JOB_KIND_PATTERN.test(kind)) throw new MailboxError("invalid job kind");
  return kind;
}
