import { sampleApprovals, sampleCards } from "@/adapters/sample";
import { APP_SETTINGS } from "@/config/app";
import { hm12 } from "@/core/clock";
import type { Lang } from "@/i18n/messages";
import type { TodaySnapshot, TodaySource } from "./types";

export const SAMPLE = {
  en: {
    hijri: "Sample Hijri date",
    event: { title: "Sample: site visit with the architect", place: "New Home" },
    tasks: [
      { id: "t1", title: "Sample: review the patching SOP draft", due: "Today" },
      { id: "t2", title: "Sample: call the contractor", due: "Today" },
      { id: "t3", title: "Sample: renew car registration", due: "Tomorrow" },
      { id: "t4", title: "Sample: book the car service", due: "Tomorrow" },
    ],
  },
  ar: {
    hijri: "تاريخ هجري تجريبي",
    event: { title: "نموذج: زيارة الموقع مع المهندس", place: "البيت الجديد" },
    tasks: [
      { id: "t1", title: "نموذج: مراجعة مسودة إجراء التحديثات", due: "اليوم" },
      { id: "t2", title: "نموذج: الاتصال بالمقاول", due: "اليوم" },
      { id: "t3", title: "نموذج: تجديد استمارة السيارة", due: "غداً" },
      { id: "t4", title: "نموذج: حجز صيانة السيارة", due: "غداً" },
    ],
  },
} as const;

const SAMPLE_CONVERSATION = "00000000-0000-4000-8000-000000000000";

export function gregorianDate(lang: Lang, now: Date): string {
  return new Intl.DateTimeFormat(lang === "ar" ? "ar-SA-u-ca-gregory-nu-latn" : "en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: APP_SETTINGS.timeZone,
  }).format(now);
}

/** Everything sample except the Gregorian date. Used in tests and as a fallback source. */
export class PlaceholderTodaySource implements TodaySource {
  async getToday(lang: Lang, now: Date): Promise<TodaySnapshot> {
    const s = SAMPLE[lang];
    const soon = (minutes: number) => new Date(now.getTime() + minutes * 60_000).toISOString();
    return {
      gregorianDate: gregorianDate(lang, now),
      hijriDate: s.hijri,
      now: [
        { kind: "prayer", key: "asr", at: soon(42), time: hm12(15, 12, lang) },
        { kind: "event", ...s.event, at: soon(120), time: hm12(16, 30, lang) },
        { kind: "prayer", key: "maghrib", at: soon(200), time: hm12(17, 50, lang) },
      ],
      events: [{ id: "e1", ...s.event, allDay: false, time: hm12(16, 30, lang) }],
      google: "ok",
      yahoo: "ok",
      todoist: "ok",
      tasks: s.tasks.map((t) => ({ ...t })),
      approvals: sampleApprovals(SAMPLE_CONVERSATION, now),
      cards: sampleCards(now),
      sample: true,
    };
  }
}
