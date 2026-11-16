/** Snafi step 3: the Today screen's Google part (today_feed), its database rules and the screen. */
import { render, screen } from "@testing-library/react";
import type { PGlite } from "@electric-sql/pglite";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { createMemoryStore, MemoryMailboxAdapter } from "@/adapters/mailbox/memory";
import { toTodayFeed, type TodayFeed } from "@/adapters/mailbox/types";
import { LiveTodaySource, STALE_AFTER_MS, when } from "@/adapters/today/live";
import { Connections } from "@/app/(app)/settings/Connections";
import { TodayView } from "@/app/(app)/today/TodayView";
import { ALICE, as, BOB, freshDb } from "./helpers/db";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const NOW = new Date("2026-11-14T09:00:00Z"); // 12:00 in Jeddah
const FEED: TodayFeed = {
  nextEvent: { title: "Site visit with the architect", start: "2026-11-14T13:30:00Z", end: "2026-11-14T14:30:00Z",
    location: "New Home", allDay: false },
  emails: [{ from: "Ahmed Ali", subject: "Drawings for review", receivedAt: "2026-11-14T06:05:00Z", account: "gmail" }],
  tasks: [],
  googleStatus: "ok",
  yahooStatus: "off",
  todoistStatus: "off",
  updatedAt: "2026-11-14T08:55:00Z",
};

describe("today_feed in the database", () => {
  let db: PGlite;
  beforeAll(async () => {
    db = await freshDb();
  }, 60_000);

  it("has RLS forced, and the app can only read its own row", async () => {
    const r = await db.query<{ relrowsecurity: boolean; relforcerowsecurity: boolean }>(
      "select relrowsecurity, relforcerowsecurity from pg_class where relname = 'today_feed'");
    expect(r.rows[0]).toEqual({ relrowsecurity: true, relforcerowsecurity: true });
    await as(db, "service_role", null,
      `insert into public.today_feed (user_id, emails, google_status) values
       ($1, '[{"from":"a","subject":"alice mail"}]', 'ok'), ($2, '[{"from":"b","subject":"bob mail"}]', 'ok')`, [ALICE, BOB]);
    const mine = await as<{ emails: { subject: string }[] }>(db, "authenticated", ALICE, "select emails from public.today_feed");
    expect(mine.rows.map((x) => x.emails[0].subject)).toEqual(["alice mail"]);
    await expect(as(db, "anon", null, "select * from public.today_feed")).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE, "update public.today_feed set google_status = 'off'")).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE, "delete from public.today_feed")).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE, `insert into public.today_feed (user_id) values ('${ALICE}')`)).rejects.toThrow(/permission denied/);
  });

  it("holds at most ten emails (five per account since step 4) and a known status", async () => {
    const six = JSON.stringify(Array.from({ length: 11 }, (_, i) => ({ from: "x", subject: `s${i}` })));
    await expect(as(db, "service_role", null, "update public.today_feed set emails = $1 where user_id = $2", [six, ALICE]))
      .rejects.toThrow(/check constraint/);
    await expect(as(db, "service_role", null, "update public.today_feed set google_status = 'hacked' where user_id = $1", [ALICE]))
      .rejects.toThrow(/check constraint/);
  });
});

describe("the feed on the screen", () => {
  it("keeps only known fields, cut to size", () => {
    const feed = toTodayFeed({
      next_event: { title: "x".repeat(500), start: "2026-11-14T13:30:00Z", end: "", location: "", all_day: true, extra: "no" },
      emails: Array.from({ length: 9 }, () => ({ from: "a", subject: "b", received_at: "c", body: "never shown" })),
      google_status: "weird", updated_at: "2026-11-14T08:55:00Z",
    });
    expect(feed.nextEvent?.title).toHaveLength(200);
    expect(feed.nextEvent?.allDay).toBe(true);
    expect(feed.emails).toHaveLength(5);
    expect(JSON.stringify(feed)).not.toContain("never shown");
    expect(feed.googleStatus).toBe("error");
  });

  it("shows the real event in Jeddah time, for the plan and the Now card; important email is no longer on Today", async () => {
    const today = await new LiveTodaySource(async () => [], async () => FEED).getToday("en", NOW);
    expect(today.events).toEqual([{ id: "e0", title: "Site visit with the architect", time: "4:30 PM", place: "New Home", allDay: false }]);
    expect(today.now.find((item) => item.kind === "event")).toMatchObject({ title: "Site visit with the architect", time: "4:30 PM", place: "New Home" });
    expect(JSON.stringify(today)).not.toContain("Drawings for review"); // AC-13: no Important email on Today
    expect(today.google).toBe("ok");
    expect(today.sample).toBe(false);
  });

  it("says when the snapshot is old, missing or Google needs reconnecting", async () => {
    const old = { ...FEED, updatedAt: new Date(NOW.getTime() - STALE_AFTER_MS - 1000).toISOString() };
    expect((await new LiveTodaySource(async () => [], async () => old).getToday("en", NOW)).google).toBe("stale");
    expect((await new LiveTodaySource(async () => [], async () => null).getToday("en", NOW)).google).toBe("waiting");
    const down = await new LiveTodaySource(async () => [], async () => { throw new Error("down"); }).getToday("en", NOW);
    expect(down.google).toBe("waiting");
    const reconnect = { ...FEED, googleStatus: "reconnect" as const, nextEvent: null, emails: [] };
    expect((await new LiveTodaySource(async () => [], async () => reconnect).getToday("en", NOW)).google).toBe("reconnect");
  });

  it("formats other days and all-day events", () => {
    expect(when("2026-11-17T15:00:00Z", "en", NOW, "Asia/Riyadh")).toBe("Tue 6:00 PM");
    expect(when("2026-11-14", "en", NOW, "Asia/Riyadh", true, "All day")).toBe("All day");
  });

  it("renders the event in the plan and no email card or connection note on Today; the reconnect note is in Settings (AC-13, AC-19)", async () => {
    const live = await new LiveTodaySource(async () => [], async () => FEED).getToday("en", NOW);
    const { unmount } = render(<TodayView lang="en" hour={12} today={live} now={NOW} />);
    expect(screen.queryByTestId("important-emails")).toBeNull();
    expect(screen.queryByText("Drawings for review")).toBeNull();
    expect(screen.getByTestId("plan-events")).toHaveTextContent("Site visit with the architect");
    expect(screen.queryByTestId("google-status")).toBeNull();
    unmount();
    const reconnect = await new LiveTodaySource(async () => [], async () => ({ ...FEED, googleStatus: "reconnect" as const,
      nextEvent: null, emails: [] })).getToday("ar", NOW);
    const today = render(<TodayView lang="ar" hour={12} today={reconnect} now={NOW} />);
    expect(screen.queryByTestId("google-status")).toBeNull();
    expect(screen.getByTestId("plan-events")).toHaveTextContent("التقويم غير متاح الآن.");
    today.unmount();
    render(<Connections lang="ar" states={{ google: reconnect.google, yahoo: reconnect.yahoo, todoist: reconnect.todoist }} />);
    expect(screen.getByTestId("google-status")).toHaveTextContent("connect-google");
    expect(screen.getByTestId("google-status")).toHaveAttribute("data-state", "reconnect");
  });

  it("each user sees only their own feed in the memory mailbox", async () => {
    const store = createMemoryStore();
    store.feeds[ALICE] = FEED;
    expect(await new MemoryMailboxAdapter(store, ALICE).todayFeed()).toEqual(FEED);
    expect(await new MemoryMailboxAdapter(store, BOB).todayFeed()).toBeNull();
  });
});
