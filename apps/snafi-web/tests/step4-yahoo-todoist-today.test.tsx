/** Snafi step 4: Yahoo emails next to Gmail's and today's Todoist tasks on the Today screen. */
import { render, screen, within } from "@testing-library/react";
import type { PGlite } from "@electric-sql/pglite";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { toTodayFeed, type TodayFeed } from "@/adapters/mailbox/types";
import { LiveTodaySource, taskDue } from "@/adapters/today/live";
import { TodayView } from "@/app/(app)/today/TodayView";
import { ALICE, as, BOB, freshDb } from "./helpers/db";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const NOW = new Date("2026-11-14T09:00:00Z"); // 12:00 in Jeddah
const FEED: TodayFeed = {
  nextEvent: null,
  emails: [
    { from: "Ahmed Ali", subject: "Drawings for review", receivedAt: "2026-11-14T06:05:00Z", account: "gmail" },
    { from: "Bank Alerts", subject: "Statement ready", receivedAt: "2026-11-14T07:40:00Z", account: "yahoo" },
  ],
  tasks: [
    { content: "Renew car registration", due: "2026-11-12", priority: 1, overdue: true, recurring: false },
    { content: "Call the contractor", due: "2026-11-14T18:30:00+03:00", priority: 2, overdue: false, recurring: false },
    { content: "Water the plants", due: "2026-11-14", priority: 4, overdue: false, recurring: true },
  ],
  googleStatus: "ok",
  yahooStatus: "ok",
  todoistStatus: "ok",
  updatedAt: "2026-11-14T08:55:00Z",
};
const decide = vi.fn(async () => ({ ok: true }));

describe("today_feed after migration 0007", () => {
  let db: PGlite;
  beforeAll(async () => {
    db = await freshDb();
  }, 60_000);

  it("adds tasks and the Yahoo and Todoist states, still only the owner's row", async () => {
    await as(db, "service_role", null,
      `insert into public.today_feed (user_id, tasks, yahoo_status, todoist_status) values
       ($1, '[{"content":"alice task"}]', 'ok', 'reconnect'), ($2, '[{"content":"bob task"}]', 'ok', 'ok')`, [ALICE, BOB]);
    const mine = await as<{ tasks: { content: string }[]; todoist_status: string }>(db, "authenticated", ALICE,
      "select tasks, todoist_status from public.today_feed");
    expect(mine.rows).toEqual([{ tasks: [{ content: "alice task" }], todoist_status: "reconnect" }]);
    await expect(as(db, "authenticated", ALICE, "update public.today_feed set tasks = '[]'")).rejects.toThrow(/permission denied/);
    await expect(as(db, "anon", null, "select tasks from public.today_feed")).rejects.toThrow(/permission denied/);
  });

  it("holds at most ten tasks, ten emails and known states", async () => {
    const eleven = JSON.stringify(Array.from({ length: 11 }, (_, i) => ({ content: `t${i}` })));
    await expect(as(db, "service_role", null, "update public.today_feed set tasks = $1 where user_id = $2", [eleven, ALICE]))
      .rejects.toThrow(/check constraint/);
    const ten = JSON.stringify(Array.from({ length: 10 }, (_, i) => ({ from: "x", subject: `s${i}`, account: i % 2 ? "yahoo" : "gmail" })));
    await as(db, "service_role", null, "update public.today_feed set emails = $1 where user_id = $2", [ten, ALICE]);
    for (const column of ["yahoo_status", "todoist_status"]) {
      await expect(as(db, "service_role", null, `update public.today_feed set ${column} = 'hacked' where user_id = $1`, [ALICE]))
        .rejects.toThrow(/check constraint/);
    }
    await expect(as(db, "service_role", null, "update public.today_feed set tasks = '{}' where user_id = $1", [ALICE]))
      .rejects.toThrow(/check constraint/);
  });
});

describe("the step 4 feed on the screen", () => {
  it("keeps five emails per account, ten tasks, known fields only", () => {
    const feed = toTodayFeed({
      emails: [
        ...Array.from({ length: 7 }, (_, i) => ({ from: "g", subject: `g${i}`, received_at: "", account: "gmail", body: "never shown" })),
        ...Array.from({ length: 7 }, (_, i) => ({ from: "y", subject: `y${i}`, received_at: "", account: "yahoo" })),
        { from: "z", subject: "odd", account: "hotmail" },
      ],
      tasks: [...Array.from({ length: 12 }, (_, i) => ({ content: `t${i}`, due: "", priority: 9, description: "never shown" }))],
      google_status: "ok", yahoo_status: "ok", todoist_status: "weird", updated_at: "2026-11-14T08:55:00Z",
    });
    expect(feed.emails.filter((m) => m.account === "gmail")).toHaveLength(5);
    expect(feed.emails.filter((m) => m.account === "yahoo")).toHaveLength(5);
    expect(feed.tasks).toHaveLength(10);
    expect(feed.tasks[0].priority).toBe(4);
    expect(JSON.stringify(feed)).not.toContain("never shown");
    expect(feed.todoistStatus).toBe("error");
  });

  it("treats a row from before step 4 as Yahoo and Todoist switched off", () => {
    const feed = toTodayFeed({ emails: [{ from: "a", subject: "b", received_at: "c" }], google_status: "ok", updated_at: "x" });
    expect(feed.emails[0].account).toBe("gmail");
    expect(feed.tasks).toEqual([]);
    expect([feed.yahooStatus, feed.todoistStatus]).toEqual(["off", "off"]);
  });

  it("shows both inboxes newest first, each with its account, and real tasks", async () => {
    const today = await new LiveTodaySource(async () => [], async () => FEED).getToday("en", NOW);
    expect(today.emails.map((m) => [m.account, m.subject, m.time])).toEqual([
      ["yahoo", "Statement ready", "10:40 AM"], ["gmail", "Drawings for review", "9:05 AM"]]);
    expect(today.tasks.map((t) => [t.title, t.due])).toEqual([
      ["Renew car registration", "Overdue · Thu"], ["Call the contractor", "6:30 PM"], ["Water the plants", "Today"]]);
    expect(today.samples).toMatchObject({ emails: false, tasks: false });
    expect([today.yahoo, today.todoist]).toEqual(["ok", "ok"]);
  });

  it("formats task due dates in Arabic too", () => {
    expect(taskDue("2026-11-14", false, "ar", NOW, "Asia/Riyadh")).toBe("اليوم");
    expect(taskDue("", true, "en", NOW, "Asia/Riyadh")).toBe("Overdue");
    expect(taskDue("", false, "en", NOW, "Asia/Riyadh")).toBe("");
  });

  it("renders the account labels, the tasks and each source's note, in English and Arabic", async () => {
    const live = await new LiveTodaySource(async () => [], async () => FEED).getToday("en", NOW);
    const { unmount } = render(<TodayView lang="en" hour={12} today={live} decide={decide} />);
    const emails = screen.getByTestId("important-emails");
    expect(within(emails).getAllByTestId("email-account").map((b) => b.textContent)).toEqual(["Yahoo", "Gmail"]);
    expect(screen.getByTestId("top-tasks")).toHaveTextContent("Renew car registration");
    expect(screen.getByTestId("top-tasks").querySelector("[data-overdue='true']")).toHaveTextContent("Overdue");
    expect(screen.queryByTestId("yahoo-status")).toBeNull();
    expect(screen.queryByTestId("todoist-status")).toBeNull();
    unmount();
    const down = await new LiveTodaySource(async () => [], async () => ({ ...FEED, yahooStatus: "reconnect" as const,
      todoistStatus: "not_connected" as const, tasks: [] })).getToday("ar", NOW);
    render(<TodayView lang="ar" hour={12} today={down} decide={decide} />);
    expect(screen.getByTestId("yahoo-status")).toHaveTextContent("set-secrets");
    expect(screen.getByTestId("todoist-status")).toHaveTextContent("Todoist");
    expect(screen.queryByTestId("top-tasks")).toBeNull();
  });
});
