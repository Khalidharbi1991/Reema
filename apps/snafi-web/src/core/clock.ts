/**
 * Every time Snafi shows: 12-hour with AM/PM in English and ص/م in Arabic (Khalid, Nov 14, 2026),
 * with Western digits, in the city's time zone. Built by hand so every browser and server agrees.
 */
import type { Lang } from "@/i18n/messages";

const PERIOD: Record<Lang, [string, string]> = { en: ["AM", "PM"], ar: ["ص", "م"] };

function parts(date: Date, timeZone: string): { hour: number; minute: number } {
  const p = new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(date);
  const get = (type: string) => Number(p.find((x) => x.type === type)?.value ?? 0);
  return { hour: get("hour") % 24, minute: get("minute") };
}

/** 7:05 AM / 7:05 ص. */
export function clock12(date: Date, lang: Lang, timeZone: string): string {
  const { hour, minute } = parts(date, timeZone);
  return hm12(hour, minute, lang);
}

/** 0-23 and 0-59 to 12-hour text. */
export function hm12(hour: number, minute: number, lang: Lang): string {
  const [am, pm] = PERIOD[lang] ?? PERIOD.en;
  return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour >= 12 ? pm : am}`;
}

/** "07:00" (as stored) to { hour12: 7, minute: 0, pm: false }, and back. */
export function splitHHMM(value: string): { hour12: number; minute: number; pm: boolean } {
  const m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(value);
  const hour = m ? Number(m[1]) : 7;
  const minute = m ? Number(m[2]) : 0;
  return { hour12: hour % 12 || 12, minute, pm: hour >= 12 };
}

export function joinHHMM(hour12: number, minute: number, pm: boolean): string {
  if (!Number.isInteger(hour12) || hour12 < 1 || hour12 > 12 || !Number.isInteger(minute) || minute < 0 || minute > 59) {
    throw new Error("invalid time");
  }
  const hour = (hour12 % 12) + (pm ? 12 : 0);
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

/** "9 Nov, 3:30 AM": a day and month (in the language) with a 12-hour time. */
export function dayMonthClock(date: Date, lang: Lang, timeZone: string): string {
  const locale = lang === "ar" ? "ar-SA-u-ca-gregory-nu-latn" : "en-GB";
  const day = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone }).format(date);
  return `${day}, ${clock12(date, lang, timeZone)}`;
}
