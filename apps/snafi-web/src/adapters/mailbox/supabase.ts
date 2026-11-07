import "server-only";
import { createSupabaseServerClient } from "@/adapters/supabase/server-client";
import type { Lang } from "@/i18n/messages";
import {
  checkJobKind,
  checkMessageBody,
  MailboxError,
  type MailboxAdapter,
  type MailboxJob,
  type MailboxMessage,
} from "./types";

type MessageRow = {
  id: string; user_id: string; conversation_id: string; role: MailboxMessage["role"];
  body: string; lang: Lang; job_id: string | null; created_at: string;
};
type JobRow = {
  id: string; user_id: string; kind: string; status: MailboxJob["status"];
  payload: Record<string, unknown>; result: Record<string, unknown> | null;
  error: string | null; created_at: string; updated_at: string;
};

const toMessage = (r: MessageRow): MailboxMessage => ({
  id: r.id, userId: r.user_id, conversationId: r.conversation_id, role: r.role,
  body: r.body, lang: r.lang, jobId: r.job_id, createdAt: r.created_at,
});
const toJob = (r: JobRow): MailboxJob => ({
  id: r.id, userId: r.user_id, kind: r.kind, status: r.status, payload: r.payload,
  result: r.result, error: r.error, createdAt: r.created_at, updatedAt: r.updated_at,
});

/**
 * Supabase mailbox. Runs as the signed-in user with the publishable key, so the
 * row-level security policies in supabase/migrations decide what is visible.
 * user_id is filled by the database (auth.uid()), never by the app.
 */
export class SupabaseMailboxAdapter implements MailboxAdapter {
  private async client() {
    const client = await createSupabaseServerClient();
    if (!client) throw new MailboxError("Supabase is not configured");
    return client;
  }

  async listMessages(conversationId: string, limit = 50) {
    const { data, error } = await (await this.client())
      .from("messages").select("*").eq("conversation_id", conversationId)
      .order("created_at", { ascending: false }).limit(limit);
    if (error) throw new MailboxError(error.message);
    return (data as MessageRow[]).map(toMessage).reverse();
  }

  async postUserMessage(input: { conversationId: string; body: string; lang: Lang }) {
    const { data, error } = await (await this.client())
      .from("messages")
      .insert({ conversation_id: input.conversationId, role: "user", body: checkMessageBody(input.body), lang: input.lang })
      .select("*").single();
    if (error) throw new MailboxError(error.message);
    return toMessage(data as MessageRow);
  }

  async enqueueJob(input: { kind: string; payload: Record<string, unknown> }) {
    const { data, error } = await (await this.client())
      .from("jobs").insert({ kind: checkJobKind(input.kind), payload: input.payload })
      .select("*").single();
    if (error) throw new MailboxError(error.message);
    return toJob(data as JobRow);
  }

  async listJobs(limit = 50) {
    const { data, error } = await (await this.client())
      .from("jobs").select("*").order("created_at", { ascending: false }).limit(limit);
    if (error) throw new MailboxError(error.message);
    return (data as JobRow[]).map(toJob).reverse();
  }
}
