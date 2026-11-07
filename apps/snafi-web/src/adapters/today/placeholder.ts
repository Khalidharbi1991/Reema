import { APP_SETTINGS } from "@/config/app";
import type { Lang } from "@/i18n/messages";
import type { TodaySnapshot, TodaySource } from "./types";

const SAMPLE = {
  en: {
    hijri: "Sample Hijri date",
    event: { title: "Sample: site visit with the architect", time: "16:30", place: "New Home" },
    tasks: [
      { id: "t1", title: "Sample: review the patching SOP draft", due: "Today" },
      { id: "t2", title: "Sample: call the contractor", due: "Today" },
      { id: "t3", title: "Sample: renew car registration", due: "Tomorrow" },
    ],
    cards: [{ id: "c1", title: "Sample card", body: "Ahmad's notes will appear here once he is connected in step 2." }],
    approvals: [{ id: "a1", title: "Sample: send reply to the architect", detail: "Email draft · needs your approval" }],
  },
  ar: {
    hijri: "تاريخ هجري تجريبي",
    event: { title: "نموذج: زيارة الموقع مع المهندس", time: "16:30", place: "البيت الجديد" },
    tasks: [
      { id: "t1", title: "نموذج: مراجعة مسودة إجراء التحديثات", due: "اليوم" },
      { id: "t2", title: "نموذج: الاتصال بالمقاول", due: "اليوم" },
      { id: "t3", title: "نموذج: تجديد استمارة السيارة", due: "غداً" },
    ],
    cards: [{ id: "c1", title: "بطاقة تجريبية", body: "ستظهر ملاحظات أحمد هنا بعد ربطه في المرحلة الثانية." }],
    approvals: [{ id: "a1", title: "نموذج: إرسال رد إلى المهندس", detail: "مسودة بريد · تحتاج موافقتك" }],
  },
} as const;

/**
 * Fixed sample data, clearly marked. Only the Gregorian date is real.
 * Real prayer times and a verified Umm al-Qura Hijri date come in step 2.
 */
export class PlaceholderTodaySource implements TodaySource {
  async getToday(lang: Lang, now: Date): Promise<TodaySnapshot> {
    const s = SAMPLE[lang];
    const gregorianDate = new Intl.DateTimeFormat(lang === "ar" ? "ar-SA-u-ca-gregory-nu-latn" : "en-GB", {
      weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: APP_SETTINGS.timeZone,
    }).format(now);
    return {
      placeholder: true,
      gregorianDate,
      hijriDate: s.hijri,
      nextPrayer: { key: "asr", time: "15:12", progress: 0.62 },
      nextEvent: { ...s.event },
      tasks: s.tasks.map((t) => ({ ...t })),
      cards: s.cards.map((c) => ({ ...c })),
      approvals: s.approvals.map((a) => ({ ...a })),
    };
  }
}
