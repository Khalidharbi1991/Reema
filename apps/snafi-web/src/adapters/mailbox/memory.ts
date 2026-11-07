import type { Lang } from "@/i18n/messages";
import {
  checkJobKind,
  checkMessageBody,
  MailboxError,
  type MailboxAdapter,
  type MailboxJob,
  type MailboxMessage,
} from "./types";

type Store = { messages: MailboxMessage[]; jobs: MailboxJob[] };

/**
 * In-memory mailbox for tests and offline work. One shared store, one view per
 * user, mirroring the row-level security rules: a user sees only their own rows.
 */
export function createMemoryStore(): Store {
  return { messages: [], jobs: [] };
}

export class MemoryMailboxAdapter implements MailboxAdapter {
  private seq = 0;
  constructor(
    private readonly store: Store,
    private readonly userId: string | null,
    private readonly now: () => Date = () => new Date(),
  ) {}

  private requireUser(): string {
    if (!this.userId) throw new MailboxError("not signed in");
    return this.userId;
  }

  private id() {
    this.seq += 1;
    return `${this.requireUser()}-${this.seq}-${Math.random().toString(36).slice(2, 8)}`;
  }

  async listMessages(conversationId: string, limit = 50) {
    const user = this.requireUser();
    return this.store.messages
      .filter((m) => m.userId === user && m.conversationId === conversationId)
      .slice(-limit);
  }

  async postUserMessage(input: { conversationId: string; body: string; lang: Lang }) {
    const user = this.requireUser();
    const message: MailboxMessage = {
      id: this.id(),
      userId: user,
      conversationId: input.conversationId,
      role: "user",
      body: checkMessageBody(input.body),
      lang: input.lang,
      jobId: null,
      createdAt: this.now().toISOString(),
    };
    this.store.messages.push(message);
    return message;
  }

  async enqueueJob(input: { kind: string; payload: Record<string, unknown> }) {
    const user = this.requireUser();
    const at = this.now().toISOString();
    const job: MailboxJob = {
      id: this.id(),
      userId: user,
      kind: checkJobKind(input.kind),
      status: "queued",
      payload: input.payload,
      result: null,
      error: null,
      createdAt: at,
      updatedAt: at,
    };
    this.store.jobs.push(job);
    return job;
  }

  async listJobs(limit = 50) {
    const user = this.requireUser();
    return this.store.jobs.filter((j) => j.userId === user).slice(-limit);
  }
}
