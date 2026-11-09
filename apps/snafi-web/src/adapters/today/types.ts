/**
 * What the Today screen shows. Each part comes from its own source: prayer times and
 * dates are computed locally (step 2), approvals come from the mailbox, and the event,
 * tasks and cards stay marked samples until steps 3 and 4 connect calendar and tasks.
 */
import type { ApprovalCard } from "@/adapters/mailbox/types";
import type { Lang } from "@/i18n/messages";

export type PrayerKey = "fajr" | "dhuhr" | "asr" | "maghrib" | "isha";

export type TodaySnapshot = {
  gregorianDate: string;
  hijriDate: string;
  nextPrayer: { key: PrayerKey; time: string; progress: number };
  nextEvent: { title: string; time: string; place: string } | null;
  tasks: { id: string; title: string; due: string }[];
  cards: { id: string; title: string; body: string }[];
  approvals: ApprovalCard[];
  /** Which parts are still sample data; the screen labels them. */
  samples: { prayer: boolean; nextEvent: boolean; tasks: boolean; cards: boolean };
};

export interface TodaySource {
  getToday(lang: Lang, now: Date): Promise<TodaySnapshot>;
}
