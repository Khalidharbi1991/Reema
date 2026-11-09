import type { Lang } from "@/i18n/messages";
import {
  checkId,
  checkMessageBody,
  MailboxError,
  type ActionEntry,
  type ApprovalCard,
  type MailboxAdapter,
  type MailboxMessage,
  type WorkerStatus,
} from "./types";

type Job = { id: string; userId: string; kind: string; payload: Record<string, unknown>; conversationId: string };
type Store = {
  messages: MailboxMessage[];
  jobs: Job[];
  approvals: (ApprovalCard & { userId: string })[];
  actions: (ActionEntry & { userId: string })[];
  status: Record<string, WorkerStatus>;
};

/**
 * In-memory mailbox for tests and preview mode. One shared store, one view per user,
 * mirroring the row-level security rules: a user sees and changes only their own rows.
 */
export function createMemoryStore(): Store {
  return { messages: [], jobs: [], approvals: [], actions: [], status: {} };
}

export class MemoryMailboxAdapter implements MailboxAdapter {
  constructor(
    private readonly store: Store,
    private readonly userId: string | null,
    private readonly now: () => Date = () => new Date(),
  ) {}

  private me(): string {
    if (!this.userId) throw new MailboxError("not signed in");
    return this.userId;
  }

  private id() {
    return crypto.randomUUID();
  }

  async listMessages(conversationId: string, limit = 50) {
    const me = this.me();
    return this.store.messages.filter((m) => m.userId === me && m.conversationId === conversationId).slice(-limit);
  }

  async sendChat(input: { conversationId: string; body: string; lang: Lang }) {
    const me = this.me();
    const message: MailboxMessage = {
      id: this.id(), userId: me, conversationId: checkId(input.conversationId), role: "user",
      body: checkMessageBody(input.body), lang: input.lang, jobId: null, approvalId: null, meta: {},
      createdAt: this.now().toISOString(),
    };
    this.store.messages.push(message);
    this.store.jobs.push({ id: this.id(), userId: me, kind: "chat.reply", payload: { message_id: message.id },
      conversationId: message.conversationId });
    return message;
  }

  async approvals(ids: string[]) {
    const me = this.me();
    return this.store.approvals.filter((a) => a.userId === me && ids.includes(a.id));
  }

  async pendingApprovals(limit = 10) {
    const me = this.me();
    const now = this.now().getTime();
    return this.store.approvals
      .filter((a) => a.userId === me && a.status === "pending" && new Date(a.expiresAt).getTime() > now).slice(0, limit);
  }

  async decideApproval(id: string, decision: "approved" | "rejected", argsHash: string) {
    const me = this.me();
    const cardId = checkId(id);
    const card = this.store.approvals.find((a) => a.id === cardId && a.userId === me && a.status === "pending");
    if (!card) throw new MailboxError("no pending approval with that id");
    if (new Date(card.expiresAt).getTime() <= this.now().getTime()) {
      card.status = "expired";
      return card;
    }
    if (decision === "approved" && (!card.argsHash || card.argsHash !== argsHash)) {
      throw new MailboxError("the action changed after it was shown; nothing was approved");
    }
    card.status = decision;
    this.store.jobs.push({ id: this.id(), userId: me, kind: "approval.resume", payload: { approval_id: id },
      conversationId: card.conversationId });
    return card;
  }

  async actions(ids: string[]) {
    const me = this.me();
    return this.store.actions.filter((a) => a.userId === me && ids.includes(a.id));
  }

  async requestUndo(actionId: string) {
    const me = this.me();
    const entryId = checkId(actionId);
    const entry = this.store.actions.find((a) => a.id === entryId && a.userId === me);
    if (!entry || !entry.undoable || entry.status !== "done" || entry.undoRequested) {
      throw new MailboxError("nothing to undo with that id");
    }
    entry.undoRequested = true;
    this.store.jobs.push({ id: this.id(), userId: me, kind: "action.undo", payload: { action_id: actionId },
      conversationId: "" });
  }

  async workerStatus() {
    return this.store.status[this.me()] ?? null;
  }
}
