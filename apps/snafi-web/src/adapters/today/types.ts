/**
 * What the Today screen shows. Each part comes from its own source: prayer times and
 * dates are computed locally (step 2), approvals come from the mailbox, the next event and
 * important emails (Gmail and Yahoo) and today's Todoist tasks come from the PC worker's
 * snapshot (steps 3 and 4), and Ahmad's cards from the worker's scheduler (step 5).
 */
import type { ApprovalCard } from "@/adapters/mailbox/types";
import type { Lang } from "@/i18n/messages";

export type GoogleState = "ok" | "off" | "not_connected" | "reconnect" | "error" | "stale" | "waiting";
/** Yahoo and Todoist (step 4): the same states, from the same snapshot. */
export type SourceState = GoogleState;

export type PrayerKey = "fajr" | "dhuhr" | "asr" | "maghrib" | "isha";

export type TodaySnapshot = {
  gregorianDate: string;
  hijriDate: string;
  nextPrayer: { key: PrayerKey; time: string; progress: number };
  nextEvent: { title: string; time: string; place: string } | null;
  /** Gmail's and Yahoo's important emails together, newest first; account says which inbox. */
  emails: { id: string; from: string; subject: string; time: string; account?: "gmail" | "yahoo" }[];
  /** What to say about the Google connection: waiting = no snapshot yet; stale = older than 30 minutes. */
  google: GoogleState;
  yahoo: SourceState;
  todoist: SourceState;
  tasks: { id: string; title: string; due: string; overdue?: boolean; priority?: 1 | 2 | 3 | 4 }[];
  /** Step 5: Ahmad's cards (reminders, the morning brief, important mail), with when they came, 12-hour. */
  cards: { id: string; title: string; body: string; kind?: "reminder" | "brief" | "mail" | "test"; time?: string }[];
  approvals: ApprovalCard[];
  /** Which parts are still sample data; the screen labels them. */
  samples: { prayer: boolean; nextEvent: boolean; emails: boolean; tasks: boolean; cards: boolean };
};

export interface TodaySource {
  getToday(lang: Lang, now: Date): Promise<TodaySnapshot>;
}
