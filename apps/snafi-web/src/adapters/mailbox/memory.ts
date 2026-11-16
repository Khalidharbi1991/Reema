import type { Lang } from "@/i18n/messages";
import {
  cardShown,
  checkId,
  checkMessageBody,
  checkPushKeys,
  checkSettings,
  DEFAULT_SETTINGS,
  MailboxError,
  type ActionEntry,
  type AhmadCard,
  type ApprovalCard,
  type MailboxAdapter,
  type MailboxMessage,
  type PushKeys,
  type Settings,
  type TodayFeed,
  type WorkerStatus,
} from "./types";

type Job = { id: string; userId: string; kind: string; payload: Record<string, unknown>; conversationId: string };
type Store = {
  messages: MailboxMessage[];
  jobs: Job[];
  approvals: (ApprovalCard & { userId: string })[];
  actions: (ActionEntry & { userId: string })[];
  status: Record<string, WorkerStatus>;
  feeds: Record<string, TodayFeed>;
  cards: (Omit<AhmadCard, "readAt"> & { readAt?: string | null; userId: string; dismissed?: boolean })[];
  settings: Record<string, Settings>;
  pushes: (PushKeys & { userId: string })[];
};

/**
 * In-memory mailbox for tests and preview mode. One shared store, one view per user,
 * mirroring the row-level security rules: a user sees and changes only their own rows.
 */
export function createMemoryStore(): Store {
  return { messages: [], jobs: [], approvals: [], actions: [], status: {}, feeds: {}, cards: [], settings: {}, pushes: [] };
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

  async todayFeed() {
    return this.store.feeds[this.me()] ?? null;
  }

  // ---------- step 5 and the Inbox ----------
  async cards(limit = 10): Promise<AhmadCard[]> {
    const me = this.me();
    const now = this.now();
    return this.store.cards.filter((c) => c.userId === me && !c.dismissed)
      .map(({ id, kind, title, body, createdAt, readAt }) => ({ id, kind, title, body, createdAt, readAt: readAt ?? null }))
      .filter((c) => cardShown(c, now))
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, limit);
  }

  /** Like mark_card_read: the first time only; another user's card changes nothing. */
  async markCardRead(id: string) {
    const me = this.me();
    const cardId = checkId(id);
    const card = this.store.cards.find((c) => c.id === cardId && c.userId === me);
    if (card && !card.readAt) card.readAt = this.now().toISOString();
  }

  async settings() {
    return { ...(this.store.settings[this.me()] ?? DEFAULT_SETTINGS) };
  }

  async saveSettings(s: Settings) {
    const v = checkSettings({ ...s });
    this.store.settings[this.me()] = v;
    return { ...v };
  }

  async savePushSubscription(k: PushKeys) {
    const me = this.me();
    const v = checkPushKeys(k);
    if (this.store.pushes.some((p) => p.endpoint === v.endpoint && p.userId !== me)) {
      throw new MailboxError("that push address is already in use");
    }
    this.store.pushes = [...this.store.pushes.filter((p) => p.endpoint !== v.endpoint), { ...v, userId: me }];
  }

  async removePushSubscription(endpoint: string) {
    const me = this.me();
    this.store.pushes = this.store.pushes.filter((p) => !(p.userId === me && p.endpoint === endpoint));
  }

  /** Like remove_all_push_subscriptions (0011): every phone's address goes, and push is switched off. */
  async removeAllPushSubscriptions() {
    const me = this.me();
    const before = this.store.pushes.length;
    this.store.pushes = this.store.pushes.filter((p) => p.userId !== me);
    this.store.settings[me] = { ...(this.store.settings[me] ?? DEFAULT_SETTINGS), pushEnabled: false };
    return before - this.store.pushes.length;
  }

  async requestTestPush() {
    const me = this.me();
    if (this.store.jobs.some((j) => j.userId === me && j.kind === "push.test")) return;
    this.store.jobs.push({ id: this.id(), userId: me, kind: "push.test", payload: {}, conversationId: "" });
  }
}
