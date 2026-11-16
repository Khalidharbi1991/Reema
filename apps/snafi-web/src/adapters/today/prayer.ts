/**
 * Prayer times by the Umm al-Qura method (adhan library, computed locally, no network)
 * and the Hijri date from the built-in Umm al-Qura calendar (Intl "islamic-umalqura").
 * The city lives in config/app.ts.
 */
import { CalculationMethod, Coordinates, PrayerTimes } from "adhan";
import { clock12 } from "@/core/clock";
import type { Lang } from "@/i18n/messages";
import type { PrayerKey } from "./types";

export type City = { name: string; latitude: number; longitude: number; timeZone: string };

const ORDER: PrayerKey[] = ["fajr", "dhuhr", "asr", "maghrib", "isha"];

/** Calendar day (year, month, day) of `now` in the city's time zone. */
function localDay(now: Date, timeZone: string): [number, number, number] {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" })
    .format(now).split("-").map(Number);
  return [parts[0], parts[1], parts[2]];
}

/** Umm al-Qura month number (1-12) of `date` in the city's time zone. */
export function hijriMonth(date: Date, timeZone: string): number {
  const part = new Intl.DateTimeFormat("en-u-ca-islamic-umalqura-nu-latn", { timeZone, month: "numeric" })
    .formatToParts(date).find((p) => p.type === "month");
  return Number(part?.value);
}

/**
 * adhan reads the date's own Y/M/D, so build it from the city's calendar day.
 * Umm al-Qura sets Isha 90 minutes after Maghrib, and 120 minutes in Ramadan; adhan
 * always uses 90, so the extra 30 minutes are added here in Ramadan.
 */
export function prayerTimesFor(city: City, y: number, m: number, d: number): Record<PrayerKey, Date> {
  const times = new PrayerTimes(new Coordinates(city.latitude, city.longitude), new Date(y, m - 1, d),
    CalculationMethod.UmmAlQura());
  const ramadan = hijriMonth(times.dhuhr, city.timeZone) === 9;
  const isha = ramadan ? new Date(times.isha.getTime() + 30 * 60_000) : times.isha;
  return { fajr: times.fajr, dhuhr: times.dhuhr, asr: times.asr, maghrib: times.maghrib, isha };
}

function shiftDay(y: number, m: number, d: number, delta: number): [number, number, number] {
  const t = new Date(Date.UTC(y, m - 1, d + delta));
  return [t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate()];
}

/** A prayer time as Snafi shows every time: 12-hour, AM/PM or ص/م. */
export function clock(date: Date, timeZone: string, lang: Lang = "en"): string {
  return clock12(date, lang, timeZone);
}

/** The next prayer after `now`, and how much of the wait since the previous one has passed (0..1). */
export function nextPrayer(city: City, now: Date, lang: Lang = "en"): { key: PrayerKey; at: Date; time: string; progress: number } {
  const [y, m, d] = localDay(now, city.timeZone);
  const today = prayerTimesFor(city, y, m, d);
  let key = ORDER.find((k) => today[k] > now);
  let at: Date;
  let previous: Date;
  if (key) {
    at = today[key];
    const i = ORDER.indexOf(key);
    previous = i > 0 ? today[ORDER[i - 1]] : prayerTimesFor(city, ...shiftDay(y, m, d, -1)).isha;
  } else {
    key = "fajr";
    at = prayerTimesFor(city, ...shiftDay(y, m, d, 1)).fajr;
    previous = today.isha;
  }
  const span = at.getTime() - previous.getTime();
  const progress = span > 0 ? Math.min(1, Math.max(0, (now.getTime() - previous.getTime()) / span)) : 0;
  return { key, at, time: clock(at, city.timeZone, lang), progress };
}

/** The prayers still to come today and all of tomorrow's, soonest first (for the Now card). */
export function upcomingPrayers(city: City, now: Date, lang: Lang = "en"): { key: PrayerKey; at: Date; time: string }[] {
  const [y, m, d] = localDay(now, city.timeZone);
  return [prayerTimesFor(city, y, m, d), prayerTimesFor(city, ...shiftDay(y, m, d, 1))]
    .flatMap((day) => ORDER.map((key) => ({ key, at: day[key], time: clock(day[key], city.timeZone, lang) })))
    .filter((p) => p.at > now);
}

/** Hijri date from the Umm al-Qura calendar, in Arabic or English. */
export function hijriDate(now: Date, lang: "ar" | "en", timeZone: string): string {
  const locale = lang === "ar" ? "ar-SA-u-ca-islamic-umalqura-nu-latn" : "en-GB-u-ca-islamic-umalqura";
  return new Intl.DateTimeFormat(locale, { timeZone, day: "numeric", month: "long", year: "numeric" }).format(now);
}
