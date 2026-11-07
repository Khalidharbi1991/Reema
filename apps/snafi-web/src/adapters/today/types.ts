/**
 * What the Today screen shows. Step 1 has only a placeholder source; later
 * steps add prayer times (Umm al-Qura), calendar, tasks and Ahmad's cards,
 * each behind its own adapter, without touching the screen.
 */
import type { Lang } from "@/i18n/messages";

export type PrayerKey = "fajr" | "dhuhr" | "asr" | "maghrib" | "isha";

export type TodaySnapshot = {
  /** True while any part is sample data; the screen labels it. */
  placeholder: boolean;
  gregorianDate: string;
  hijriDate: string;
  nextPrayer: { key: PrayerKey; time: string; progress: number };
  nextEvent: { title: string; time: string; place: string } | null;
  tasks: { id: string; title: string; due: string }[];
  cards: { id: string; title: string; body: string }[];
  approvals: { id: string; title: string; detail: string }[];
};

export interface TodaySource {
  getToday(lang: Lang, now: Date): Promise<TodaySnapshot>;
}
