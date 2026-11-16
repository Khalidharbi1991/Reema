/**
 * What the Today screen, the bell and the Inbox are drawn from. Each part comes from its own
 * source: prayer times and dates are computed locally, approvals and Ahmad's cards come from the
 * mailbox, and today's events and Todoist tasks from the PC worker's snapshot.
 */
import type { AhmadCard, ApprovalCard } from "@/adapters/mailbox/types";
import type { Lang } from "@/i18n/messages";

export type GoogleState = "ok" | "off" | "not_connected" | "reconnect" | "error" | "stale" | "waiting";
/** Yahoo and Todoist (step 4): the same states, from the same snapshot. */
export type SourceState = GoogleState;

/** The states that need Khalid to do something, or that mean the data cannot be trusted. */
export function needsAttention(state: GoogleState): boolean {
  return state === "not_connected" || state === "reconnect" || state === "error" || state === "stale";
}

export type PrayerKey = "fajr" | "dhuhr" | "asr" | "maghrib" | "isha";

/** One thing the Now card can show: its exact start (ISO) and its time as shown (12-hour). */
export type NowItem =
  | { kind: "prayer"; key: PrayerKey; at: string; time: string }
  | { kind: "event"; title: string; place: string; at: string; time: string };

export type PlanEvent = { id: string; title: string; place: string; allDay: boolean; time: string };

export type TodaySnapshot = {
  gregorianDate: string;
  hijriDate: string;
  /** Soonest first, a prayer before an event at the same instant; enough to move on at zero without a reload. */
  now: NowItem[];
  /** Today's remaining events, all-day first, then in time order. The worker's feed carries one event today. */
  events: PlanEvent[];
  tasks: { id: string; title: string; due: string; overdue?: boolean; priority?: 1 | 2 | 3 | 4 }[];
  /** What to say about each connection (shown in Settings): waiting = no snapshot yet; stale = older than 30 minutes. */
  google: GoogleState;
  yahoo: SourceState;
  todoist: SourceState;
  /** Pending approvals, oldest first; null when they could not be read. */
  approvals: ApprovalCard[] | null;
  /** The Inbox's cards, newest first; null when they could not be read. */
  cards: AhmadCard[] | null;
  /** True when the content is sample data; the screen says so once. */
  sample: boolean;
};

export interface TodaySource {
  getToday(lang: Lang, now: Date): Promise<TodaySnapshot>;
}
