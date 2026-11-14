import { APP_SETTINGS } from "@/config/app";
import type { Lang } from "@/i18n/messages";
import type { TodaySnapshot, TodaySource } from "./types";

export const SAMPLE = {
  en: {
    hijri: "Sample Hijri date",
    event: { title: "Sample: site visit with the architect", time: "16:30", place: "New Home" },
    emails: [{ id: "e1", from: "Sample sender", subject: "Sample: drawings for review", time: "09:10" }],
    tasks: [
      { id: "t1", title: "Sample: review the patching SOP draft", due: "Today" },
      { id: "t2", title: "Sample: call the contractor", due: "Today" },
      { id: "t3", title: "Sample: renew car registration", due: "Tomorrow" },
    ],
    cards: [{ id: "c1", title: "Sample card", body: "Ahmad's cards (briefs and alerts) will appear here from step 5." }],
  },
  ar: {
    hijri: "تاريخ هجري تجريبي",
    event: { title: "نموذج: زيارة الموقع مع المهندس", time: "16:30", place: "البيت الجديد" },
    emails: [{ id: "e1", from: "مرسل تجريبي", subject: "نموذج: مخططات للمراجعة", time: "09:10" }],
    tasks: [
      { id: "t1", title: "نموذج: مراجعة مسودة إجراء التحديثات", due: "اليوم" },
      { id: "t2", title: "نموذج: الاتصال بالمقاول", due: "اليوم" },
      { id: "t3", title: "نموذج: تجديد استمارة السيارة", due: "غداً" },
    ],
    cards: [{ id: "c1", title: "بطاقة تجريبية", body: "ستظهر بطاقات أحمد (الملخصات والتنبيهات) هنا ابتداءً من المرحلة الخامسة." }],
  },
} as const;

export function gregorianDate(lang: Lang, now: Date): string {
  return new Intl.DateTimeFormat(lang === "ar" ? "ar-SA-u-ca-gregory-nu-latn" : "en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: APP_SETTINGS.timeZone,
  }).format(now);
}

/** Everything sample except the Gregorian date. Used in tests and as a fallback source. */
export class PlaceholderTodaySource implements TodaySource {
  async getToday(lang: Lang, now: Date): Promise<TodaySnapshot> {
    const s = SAMPLE[lang];
    return {
      gregorianDate: gregorianDate(lang, now),
      hijriDate: s.hijri,
      nextPrayer: { key: "asr", time: "15:12", progress: 0.62 },
      nextEvent: { ...s.event },
      emails: s.emails.map((m) => ({ ...m })),
      google: "ok",
      yahoo: "ok",
      todoist: "ok",
      tasks: s.tasks.map((t) => ({ ...t })),
      cards: s.cards.map((c) => ({ ...c })),
      approvals: [],
      samples: { prayer: true, nextEvent: true, emails: true, tasks: true, cards: true },
    };
  }
}
