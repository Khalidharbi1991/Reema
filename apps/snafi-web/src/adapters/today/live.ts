import type { AhmadCard, ApprovalCard, TodayFeed } from "@/adapters/mailbox/types";
import { APP_SETTINGS } from "@/config/app";
import { clock12 } from "@/core/clock";
import { inboxCards, pendingApprovals } from "@/core/inbox";
import type { Lang } from "@/i18n/messages";
import { gregorianDate } from "./placeholder";
import { hijriDate, upcomingPrayers } from "./prayer";
import type { GoogleState, NowItem, PlanEvent, TodaySnapshot, TodaySource } from "./types";

/** A Google snapshot older than this is shown as out of date (the worker writes one every 10 minutes). */
export const STALE_AFTER_MS = 30 * 60_000;

function localDay(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

/** "6:30 PM" today, "Tue 6:30 PM" on another day (ص/م in Arabic); all-day events show the day only. */
export function when(iso: string, lang: Lang, now: Date, timeZone: string, allDay = false, allDayLabel = ""): string {
  const locale = lang === "ar" ? "ar-SA-u-ca-gregory-nu-latn" : "en-GB";
  if (allDay) {
    const day = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
    if (Number.isNaN(day.getTime())) return allDayLabel;
    const same = iso.slice(0, 10) === localDay(now, timeZone);
    const weekday = new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(day);
    return same ? allDayLabel : allDayLabel ? `${weekday}, ${allDayLabel}` : weekday;
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const time = clock12(date, lang, timeZone);
  if (localDay(date, timeZone) === localDay(now, timeZone)) return time;
  return `${new Intl.DateTimeFormat(locale, { weekday: "short", timeZone }).format(date)} ${time}`;
}

const ALL_DAY = { en: "All day", ar: "طوال اليوم" } as const;
const TODAY = { en: "Today", ar: "اليوم" } as const;
const OVERDUE = { en: "Overdue", ar: "متأخرة" } as const;
const COMMA = { en: ", ", ar: "، " } as const;

/** A Todoist due date: "Today" or "6:30 PM" today, the day for another day, "Overdue, …" when late. */
export function taskDue(due: string, overdue: boolean, lang: Lang, now: Date, timeZone: string): string {
  let shown = "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(due)) {
    shown = due === localDay(now, timeZone) ? TODAY[lang] : when(due, lang, now, timeZone, true, "");
  } else if (due) {
    shown = when(due, lang, now, timeZone); // the worker writes times with their offset
  }
  return overdue ? (shown ? `${OVERDUE[lang]}${COMMA[lang]}${shown}` : OVERDUE[lang]) : shown;
}

function withStale(status: GoogleState, feed: TodayFeed | null, now: Date): GoogleState {
  if (!feed) return "waiting";
  if (status === "ok" && now.getTime() - new Date(feed.updatedAt).getTime() > STALE_AFTER_MS) return "stale";
  return status;
}

/**
 * The feed's event, if it is today and not over: for the plan, and (timed and not yet started)
 * for the Now card. The worker's feed carries one event; the plan is built for a list.
 */
function todaysEvents(feed: TodayFeed | null, lang: Lang, now: Date, tz: string): { plan: PlanEvent[]; next: NowItem[] } {
  const ev = feed?.nextEvent;
  if (!ev) return { plan: [], next: [] };
  if (ev.allDay) {
    const today = ev.start.slice(0, 10) === localDay(now, tz);
    return { plan: today ? [{ id: "e0", title: ev.title, place: ev.location, allDay: true, time: ALL_DAY[lang] }] : [], next: [] };
  }
  const start = new Date(ev.start);
  if (Number.isNaN(start.getTime()) || localDay(start, tz) !== localDay(now, tz)) return { plan: [], next: [] };
  const end = new Date(ev.end).getTime();
  if ((Number.isNaN(end) ? start.getTime() : end) <= now.getTime()) return { plan: [], next: [] };
  const time = clock12(start, lang, tz);
  return {
    plan: [{ id: "e0", title: ev.title, place: ev.location, allDay: false, time }],
    next: start > now ? [{ kind: "event", title: ev.title, place: ev.location, at: start.toISOString(), time }] : [],
  };
}

/** Soonest first; at the same instant the prayer comes first (it wins a tie on the Now card). */
export function nowItems(items: NowItem[]): NowItem[] {
  return [...items].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime()
    || Number(a.kind !== "prayer") - Number(b.kind !== "prayer"));
}

/**
 * Today: real prayer times and Hijri date for the configured city, pending approvals and Ahmad's
 * cards from the mailbox, and from the PC worker's snapshot today's event and Todoist tasks and
 * the state of each connection (shown in Settings).
 */
export class LiveTodaySource implements TodaySource {
  constructor(
    private readonly pendingApprovals: () => Promise<ApprovalCard[]>,
    private readonly feed: () => Promise<TodayFeed | null> = async () => null,
    private readonly ahmadCards: () => Promise<AhmadCard[]> = async () => [],
  ) {}

  async getToday(lang: Lang, now: Date): Promise<TodaySnapshot> {
    const city = APP_SETTINGS.city;
    const tz = city.timeZone;
    const [approvals, feed, cards] = await Promise.all([
      this.pendingApprovals().catch(() => null), // the rest of Today still shows if the mailbox is unreachable
      this.feed().catch(() => null),
      this.ahmadCards().catch(() => null),
    ]);
    const events = todaysEvents(feed, lang, now, tz);
    const prayers: NowItem[] = upcomingPrayers(city, now, lang)
      .map((p) => ({ kind: "prayer", key: p.key, at: p.at.toISOString(), time: p.time }));
    return {
      gregorianDate: gregorianDate(lang, now),
      hijriDate: hijriDate(now, lang, tz),
      now: nowItems([...prayers, ...events.next]),
      events: events.plan,
      tasks: (feed?.tasks ?? []).map((t, i) => ({ id: `t${i}`, title: t.content, due: taskDue(t.due, t.overdue, lang, now, tz),
        overdue: t.overdue, priority: t.priority })),
      google: withStale(feed ? feed.googleStatus : "waiting", feed, now),
      yahoo: withStale(feed ? feed.yahooStatus : "waiting", feed, now),
      todoist: withStale(feed ? feed.todoistStatus : "waiting", feed, now),
      approvals: approvals && pendingApprovals(approvals, now),
      cards: cards && inboxCards(cards, now),
      sample: false,
    };
  }
}
