/**
 * The Inbox's rules, as pure functions: what counts as unread for the bell, what the badge
 * says, which single item is "Ahmad's message" on Today, and what a mail row may show.
 */
import { cardShown, effectiveStatus, type AhmadCard, type ApprovalCard } from "@/adapters/mailbox/types";
import { clock12, dayMonthClock } from "@/core/clock";
import type { Lang } from "@/i18n/messages";

const stamp = (iso: string) => {
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
};

function localDay(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

/** Approvals still waiting (not past their expiry), oldest first. */
export function pendingApprovals(approvals: ApprovalCard[], now: Date): ApprovalCard[] {
  return approvals.filter((a) => effectiveStatus(a, now) === "pending").sort((a, b) => stamp(a.createdAt) - stamp(b.createdAt));
}

/** The cards the Inbox lists, newest first: unread of any age, or read less than 7 days ago. */
export function inboxCards(cards: AhmadCard[], now: Date): AhmadCard[] {
  return cards.filter((c) => cardShown(c, now)).sort((a, b) => stamp(b.createdAt) - stamp(a.createdAt));
}

/**
 * What the bell counts: every pending approval (opening it does not uncount it) and every
 * unread card, except `test` cards, which never count (Khalid, Q4).
 */
export function unreadIds(approvals: ApprovalCard[], cards: AhmadCard[], now: Date): string[] {
  return [
    ...pendingApprovals(approvals, now).map((a) => a.id),
    ...cards.filter((c) => !c.readAt && c.kind !== "test").map((c) => c.id),
  ];
}

export function unreadCount(approvals: ApprovalCard[], cards: AhmadCard[], now: Date): number {
  return unreadIds(approvals, cards, now).length;
}

/** The badge: nothing at 0, the number for 1 to 9, "9+" from 10. */
export function badgeText(count: number): string | null {
  if (!Number.isFinite(count) || count < 1) return null;
  return count >= 10 ? "9+" : String(Math.floor(count));
}

export type AhmadMessage =
  | { kind: "approval"; id: string; title: string; more: number }
  | { kind: "reminder" | "brief"; id: string; title: string; createdAt: string };

/**
 * Ahmad's one message on Today (AC-17), in this order: (1) the oldest pending approval, with how
 * many others wait; (2) the newest unread reminder; (3) today's unread brief; (4) nothing.
 * Mail and test cards are never chosen.
 */
export function chooseAhmadMessage(approvals: ApprovalCard[], cards: AhmadCard[], now: Date, timeZone: string): AhmadMessage | null {
  const waiting = pendingApprovals(approvals, now);
  if (waiting.length) return { kind: "approval", id: waiting[0].id, title: waiting[0].summary, more: waiting.length - 1 };
  const unread = inboxCards(cards, now).filter((c) => !c.readAt);
  const reminder = unread.find((c) => c.kind === "reminder");
  if (reminder) return { kind: "reminder", id: reminder.id, title: reminder.title, createdAt: reminder.createdAt };
  const today = localDay(now, timeZone);
  const brief = unread.find((c) => c.kind === "brief" && stamp(c.createdAt) > 0 && localDay(new Date(c.createdAt), timeZone) === today);
  return brief ? { kind: "brief", id: brief.id, title: brief.title, createdAt: brief.createdAt } : null;
}

/**
 * A mail card shows the sender and the subject only (AC-8). The worker writes the sender in the
 * card's title and the subject as the body's first line; nothing else of a mail card is shown.
 */
export function mailLines(card: Pick<AhmadCard, "title" | "body">): { sender: string; subject: string } {
  return { sender: card.title.trim(), subject: (card.body.split(/\r?\n/).find((line) => line.trim()) ?? "").trim() };
}

/** "4:10 PM" for today, "14 Nov, 9:15 PM" for an earlier day; 12-hour in both languages. */
export function inboxTime(iso: string, lang: Lang, now: Date, timeZone: string): string {
  if (!stamp(iso)) return "";
  const date = new Date(iso);
  return localDay(date, timeZone) === localDay(now, timeZone) ? clock12(date, lang, timeZone) : dayMonthClock(date, lang, timeZone);
}
