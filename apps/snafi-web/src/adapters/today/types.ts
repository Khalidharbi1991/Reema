/**
 * What the Today screen shows. Each part comes from its own source: prayer times and
 * dates are computed locally (step 2), approvals come from the mailbox, the next event and
 * important emails come from the PC worker's Google snapshot (step 3), and tasks and cards
 * stay marked samples until steps 4 and 5.
 */
import type { ApprovalCard } from "@/adapters/mailbox/types";
import type { Lang } from "@/i18n/messages";

export type GoogleState = "ok" | "off" | "not_connected" | "reconnect" | "error" | "stale" | "waiting";

export type PrayerKey = "fajr" | "dhuhr" | "asr" | "maghrib" | "isha";

export type TodaySnapshot = {
  gregorianDate: string;
  hijriDate: string;
  nextPrayer: { key: PrayerKey; time: string; progress: number };
  nextEvent: { title: string; time: string; place: string } | null;
  emails: { id: string; from: string; subject: string; time: string }[];
  /** What to say about the Google connection: waiting = no snapshot yet; stale = older than 30 minutes. */
  google: GoogleState;
  tasks: { id: string; title: string; due: string }[];
  cards: { id: string; title: string; body: string }[];
  approvals: ApprovalCard[];
  /** Which parts are still sample data; the screen labels them. */
  samples: { prayer: boolean; nextEvent: boolean; emails: boolean; tasks: boolean; cards: boolean };
};

export interface TodaySource {
  getToday(lang: Lang, now: Date): Promise<TodaySnapshot>;
}
