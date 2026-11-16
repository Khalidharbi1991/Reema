"use client";

import { useSyncExternalStore } from "react";
import type { NowItem } from "@/adapters/today/types";
import { messages, type Lang } from "@/i18n/messages";

const MINUTE = 60_000;

/**
 * The clock, one tick a minute, lined up with the start of the minute. It stops while the page is
 * hidden and catches up when it is shown again; there is no per-second timer.
 */
function subscribe(tick: () => void): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const arm = () => {
    timer = setTimeout(() => { tick(); arm(); }, MINUTE - (Date.now() % MINUTE));
  };
  const onVisibility = () => {
    clearTimeout(timer);
    if (document.visibilityState === "visible") { tick(); arm(); }
  };
  arm();
  document.addEventListener("visibilitychange", onVisibility);
  return () => {
    clearTimeout(timer);
    document.removeEventListener("visibilitychange", onVisibility);
  };
}
const currentMinute = () => Math.floor(Date.now() / MINUTE);

/** The first item that has not started yet; the list is already soonest first, prayer before a tied event. */
export function currentItem(items: NowItem[], nowMs: number): NowItem | null {
  return items.find((item) => new Date(item.at).getTime() > nowMs) ?? null;
}

/** Whole minutes left, rounded up, as hours and minutes. */
export function timeLeft(at: string, nowMs: number): { hours: number; minutes: number } {
  const total = Math.max(1, Math.ceil((new Date(at).getTime() - nowMs) / MINUTE));
  return { hours: Math.floor(total / 60), minutes: total % 60 };
}

type Props = {
  lang: Lang;
  /** Soonest first, with a prayer before an event at the same instant (the prayer wins a tie). */
  items: NowItem[];
  /** The server's time, so the first paint matches what the server drew. */
  serverNow: string;
};

/**
 * The Now card (AC-14, AC-15): whichever starts first of the next prayer and the next event today,
 * with its name, its 12-hour time and a countdown. When the countdown reaches zero the card moves
 * to the next item without a reload. Not a live region: a minute tick is never read out.
 */
export function NowCard({ lang, items, serverNow }: Props) {
  const t = messages(lang);
  const serverMinute = Math.floor(new Date(serverNow).getTime() / MINUTE);
  const minute = useSyncExternalStore(subscribe, currentMinute, () => serverMinute);
  const nowMs = minute * MINUTE;
  const item = currentItem(items, nowMs);
  if (!item) return null;
  const left = timeLeft(item.at, nowMs);
  const countdown = t.now.countdown(left.hours, left.minutes);
  const name = item.kind === "prayer" ? t.prayers[item.key] : item.title;
  const label = item.kind === "prayer" ? t.now.prayerLabel(name, item.time, countdown) : t.now.eventLabel(name, item.time, countdown);
  return (
    <section className="surface mt-6" aria-label={label} data-testid="now-card" data-kind={item.kind}>
      {/* Keyed by the item: the three lines fade in together when the card moves on (still with reduced motion). */}
      <div key={item.at + item.kind} className="now-swap min-w-0">
        <p className="t-display wrap clamp-2" data-testid="now-name" data-slot="now-name"><bdi>{name}</bdi></p>
        <div className="mt-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <span className="t-time" data-testid="now-time"><bdi>{item.time}</bdi></span>
          <span className="t-body nums" data-testid="now-countdown"><bdi>{countdown}</bdi></span>
        </div>
        {item.kind === "event" && item.place && (
          <p className="t-small mt-1 truncate text-muted" data-slot="now-place"><bdi>{item.place}</bdi></p>
        )}
      </div>
    </section>
  );
}
