import type { ApprovalCard, TodayFeed } from "@/adapters/mailbox/types";
import { APP_SETTINGS } from "@/config/app";
import type { Lang } from "@/i18n/messages";
import { gregorianDate, SAMPLE } from "./placeholder";
import { hijriDate, nextPrayer } from "./prayer";
import type { GoogleState, TodaySnapshot, TodaySource } from "./types";

/** A Google snapshot older than this is shown as out of date (the worker writes one every 10 minutes). */
export const STALE_AFTER_MS = 30 * 60_000;

function localDay(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

/** "18:30" today, "Tue 18:30" on another day; all-day events show the day only. */
export function when(iso: string, lang: Lang, now: Date, timeZone: string, allDay = false, allDayLabel = ""): string {
  const locale = lang === "ar" ? "ar-SA-u-ca-gregory-nu-latn" : "en-GB";
  if (allDay) {
    const day = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
    if (Number.isNaN(day.getTime())) return allDayLabel;
    const same = iso.slice(0, 10) === localDay(now, timeZone);
    return same ? allDayLabel : `${new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(day)} · ${allDayLabel}`;
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const time = new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone }).format(date);
  if (localDay(date, timeZone) === localDay(now, timeZone)) return time;
  return `${new Intl.DateTimeFormat(locale, { weekday: "short", timeZone }).format(date)} ${time}`;
}

const ALL_DAY = { en: "All day", ar: "طوال اليوم" } as const;
const TODAY = { en: "Today", ar: "اليوم" } as const;
const OVERDUE = { en: "Overdue", ar: "متأخرة" } as const;

/** A Todoist due date: "Today" or "18:30" today, the day for another day, "Overdue · …" when late. */
export function taskDue(due: string, overdue: boolean, lang: Lang, now: Date, timeZone: string): string {
  let shown = "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(due)) {
    shown = due === localDay(now, timeZone) ? TODAY[lang] : when(due, lang, now, timeZone, true, "").replace(/ · $/, "");
  } else if (due) {
    shown = when(due, lang, now, timeZone); // the worker writes times with their offset
  }
  return overdue ? (shown ? `${OVERDUE[lang]} · ${shown}` : OVERDUE[lang]) : shown;
}

function withStale(status: GoogleState, feed: TodayFeed | null, now: Date): GoogleState {
  if (!feed) return "waiting";
  if (status === "ok" && now.getTime() - new Date(feed.updatedAt).getTime() > STALE_AFTER_MS) return "stale";
  return status;
}

/**
 * Today: real prayer times and Hijri date for the configured city, real pending approvals
 * from the mailbox, and from the PC worker's snapshot the next event, important emails from
 * Gmail and Yahoo (steps 3 and 4) and today's Todoist tasks (step 4). Cards stay marked
 * samples until step 5.
 */
export class LiveTodaySource implements TodaySource {
  constructor(
    private readonly pendingApprovals: () => Promise<ApprovalCard[]>,
    private readonly feed: () => Promise<TodayFeed | null> = async () => null,
  ) {}

  async getToday(lang: Lang, now: Date): Promise<TodaySnapshot> {
    const city = APP_SETTINGS.city;
    const tz = city.timeZone;
    const prayer = nextPrayer(city, now);
    const s = SAMPLE[lang];
    const [approvals, feed] = await Promise.all([
      this.pendingApprovals().catch(() => [] as ApprovalCard[]), // the rest of Today still shows if the mailbox is unreachable
      this.feed().catch(() => null),
    ]);

    const google = withStale(feed ? feed.googleStatus : "waiting", feed, now);
    const yahoo = withStale(feed ? feed.yahooStatus : "waiting", feed, now);
    const todoist = withStale(feed ? feed.todoistStatus : "waiting", feed, now);
    const ev = feed?.nextEvent ?? null;
    const stamp = (iso: string) => { const t = new Date(iso).getTime(); return Number.isNaN(t) ? 0 : t; };
    const emails = [...(feed?.emails ?? [])].sort((a, b) => stamp(b.receivedAt) - stamp(a.receivedAt));
    return {
      gregorianDate: gregorianDate(lang, now),
      hijriDate: hijriDate(now, lang, tz),
      nextPrayer: { key: prayer.key, time: prayer.time, progress: prayer.progress },
      nextEvent: ev ? { title: ev.title, time: when(ev.start, lang, now, tz, ev.allDay, ALL_DAY[lang]), place: ev.location } : null,
      emails: emails.map((m, i) => ({ id: `m${i}`, from: m.from, subject: m.subject, time: when(m.receivedAt, lang, now, tz), account: m.account })),
      google,
      yahoo,
      todoist,
      tasks: (feed?.tasks ?? []).map((t, i) => ({ id: `t${i}`, title: t.content, due: taskDue(t.due, t.overdue, lang, now, tz),
        overdue: t.overdue, priority: t.priority })),
      cards: s.cards.map((c) => ({ ...c })),
      approvals,
      samples: { prayer: false, nextEvent: false, emails: false, tasks: false, cards: true },
    };
  }
}
