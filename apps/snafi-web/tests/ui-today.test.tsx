/** Snafi UI job, Story 2: the simpler Today (AC-12 to AC-19), with the Now card on fake timers. */
import { act, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AhmadCard, ApprovalCard, TodayFeed } from "@/adapters/mailbox/types";
import { LiveTodaySource, nowItems } from "@/adapters/today/live";
import type { NowItem, TodaySnapshot } from "@/adapters/today/types";
import { Connections } from "@/app/(app)/settings/Connections";
import { TodayView } from "@/app/(app)/today/TodayView";
import { Menu } from "@/components/Menu";
import { NowCard } from "@/components/NowCard";
import { chooseAhmadMessage } from "@/core/inbox";
import { messages } from "@/i18n/messages";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }), usePathname: () => "/today" }));

const NOW = new Date("2026-11-14T07:00:00Z"); // 10:00 AM in Jeddah; Dhuhr is a little after noon
const TZ = "Asia/Riyadh";
const MIN = 60_000;
const at = (minutes: number) => new Date(NOW.getTime() + minutes * MIN).toISOString();
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

const FEED: TodayFeed = {
  nextEvent: null, emails: [{ from: "Sample Sender", subject: "IMPORTANT EMAIL SUBJECT", receivedAt: at(-30), account: "gmail" }],
  tasks: [], googleStatus: "ok", yahooStatus: "ok", todoistStatus: "ok", updatedAt: at(-1),
};
const event = (startMinutes: number, title = "Design review") =>
  ({ title, start: at(startMinutes), end: at(startMinutes + 60), location: "Room 3", allDay: false });
const card = (n: number, over: Partial<AhmadCard> = {}): AhmadCard =>
  ({ id: id(n), kind: "reminder", title: `Reminder ${n}`, body: `BODY ${n}`, createdAt: at(-n), readAt: null, ...over });
const approval = (n: number, over: Partial<ApprovalCard> = {}): ApprovalCard =>
  ({ id: id(100 + n), conversationId: id(0), tool: "gmail_send", args: { to: "sample@example.com" }, argsHash: "c".repeat(64),
    summary: `Send email ${n}?`, status: "pending", createdAt: at(-n), expiresAt: at(600), ...over });

async function live(feed: TodayFeed | null = FEED, approvals: ApprovalCard[] = [], cards: AhmadCard[] = [], lang: "en" | "ar" = "en") {
  return new LiveTodaySource(async () => approvals, async () => feed, async () => cards).getToday(lang, NOW);
}
const draw = (today: TodaySnapshot, lang: "en" | "ar" = "en") => render(<TodayView lang={lang} hour={10} today={today} now={NOW} />);

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});
afterEach(() => {
  vi.useRealTimers();
});

describe("AC-12: what Today shows", () => {
  it("shows the greeting with both dates, the Now card, the plan, Ahmad's message and the orb, in Khalid's order", async () => {
    draw(await live({ ...FEED, nextEvent: event(30) }, [], [card(1)]));
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toHaveTextContent("Good morning, Khalid");
    expect(screen.getByTestId("today-dates")).toHaveTextContent("Saturday, 14 November 2026");
    expect(screen.getByTestId("today-dates")).toHaveTextContent("1448");
    const parts = [h1, screen.getByTestId("now-card"), screen.getByTestId("plan"), screen.getByTestId("ahmad"),
      screen.getByRole("link", { name: "Talk to Ahmad" })];
    for (let i = 1; i < parts.length; i++) {
      expect(parts[i - 1].compareDocumentPosition(parts[i]) & Node.DOCUMENT_POSITION_FOLLOWING, `part ${i}`).toBeTruthy();
    }
    expect(screen.getByRole("link", { name: "Talk to Ahmad" })).toHaveAttribute("href", "/chat");
    // One h1 and two h2: the plan and Ahmad. Nothing else has a heading.
    expect(screen.getAllByRole("heading").map((h) => h.textContent)).toEqual([h1.textContent, "Today's plan", "From Ahmad"]);
    expect(screen.queryByTestId("sample-note")).toBeNull();
  });
});

describe("AC-13: what Today no longer shows", () => {
  it("has no connection notes, Important email, card list, test card, Approve/Reject, Dismiss or prayer ring", async () => {
    const broken = { ...FEED, googleStatus: "reconnect" as const, yahooStatus: "not_connected" as const, todoistStatus: "error" as const };
    const cards = [card(1, { kind: "test", title: "TEST CARD TITLE" }), card(2, { kind: "mail", title: "MAIL CARD SENDER" }), card(3), card(4)];
    draw(await live(broken, [approval(1)], cards));
    for (const source of ["google", "yahoo", "todoist"]) expect(screen.queryByTestId(`${source}-status`)).toBeNull();
    expect(document.body).not.toHaveTextContent(/connect-google|set-secrets/);
    expect(document.body).not.toHaveTextContent("IMPORTANT EMAIL SUBJECT");
    expect(screen.queryByTestId("important-emails")).toBeNull();
    expect(screen.queryAllByTestId("ahmad-card")).toHaveLength(0);
    expect(screen.getAllByTestId("ahmad-message")).toHaveLength(1);
    expect(document.body).not.toHaveTextContent(/TEST CARD TITLE|MAIL CARD SENDER|BODY \d/);
    expect(screen.queryByRole("button")).toBeNull(); // no Approve, Reject or Dismiss: Today has no buttons at all
    expect(screen.queryByTestId("approval-card")).toBeNull();
    expect(screen.queryByTestId("prayer-progress")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("AC-14: the Now card shows whichever starts first", () => {
  const name = () => screen.getByTestId("now-name").textContent;
  const kind = () => screen.getByTestId("now-card").getAttribute("data-kind");

  it("the event when it starts before the next prayer, with its name, 12-hour time, countdown and place", async () => {
    draw(await live({ ...FEED, nextEvent: event(60) }));
    expect([kind(), name()]).toEqual(["event", "Design review"]);
    expect(screen.getByTestId("now-time")).toHaveTextContent("11:00 AM");
    expect(screen.getByTestId("now-countdown")).toHaveTextContent("in 1 hr");
    expect(screen.getByTestId("now-card")).toHaveTextContent("Room 3");
    expect(screen.getByTestId("now-card")).toHaveAccessibleName("Next event: Design review at 11:00 AM, in 1 hr");
  });

  it("the prayer when it starts before the event", async () => {
    draw(await live({ ...FEED, nextEvent: event(300) }));
    expect([kind(), name()]).toEqual(["prayer", "Dhuhr"]);
    expect(screen.getByTestId("now-time").textContent).toMatch(/^12:\d\d PM$/);
    expect(screen.getByTestId("now-card").getAttribute("aria-label")).toMatch(/^Next prayer: Dhuhr at 12:\d\d PM, in 2 hr( \d+ min)?$/);
  });

  it("the prayer on a tie", async () => {
    const prayer = (await live()).now[0];
    const tied = await live({ ...FEED, nextEvent: { ...event(0), start: prayer.at, end: at(600) } });
    expect(tied.now.slice(0, 2).map((item) => item.kind)).toEqual(["prayer", "event"]);
    draw(tied);
    expect([kind(), name()]).toEqual(["prayer", "Dhuhr"]);
    // The rule itself, whatever order the items arrive in.
    const items: NowItem[] = [{ kind: "event", title: "E", place: "", at: at(5), time: "" }, { kind: "prayer", key: "asr", at: at(5), time: "" }];
    expect(nowItems(items).map((item) => item.kind)).toEqual(["prayer", "event"]);
  });

  it("the next prayer with no calendar connected, no event left today, or an all-day event", async () => {
    for (const feed of [null, { ...FEED, googleStatus: "not_connected" as const }, { ...FEED, nextEvent: event(-120) },
      { ...FEED, nextEvent: event(60 * 30) }, { ...FEED, nextEvent: { ...event(0), start: "2026-11-14", end: "2026-11-15", allDay: true } }]) {
      const view = draw(await live(feed));
      expect([kind(), name()]).toEqual(["prayer", "Dhuhr"]);
      view.unmount();
    }
  });

  it("shows ص/م and the Arabic countdown in Arabic", async () => {
    draw(await live({ ...FEED, nextEvent: event(42) }, [], [], "ar"), "ar");
    expect(screen.getByTestId("now-time")).toHaveTextContent("10:42 ص");
    expect(screen.getByTestId("now-countdown")).toHaveTextContent("بعد 42 دقيقة");
    expect(screen.getByTestId("now-time")).not.toHaveAttribute("dir"); // follows the page, never forced left-to-right
  });
});

describe("AC-15: the countdown ticks once a minute and moves on at zero without a reload", () => {
  const ITEMS: NowItem[] = [
    { kind: "event", title: "Stand-up", place: "", at: at(2), time: "10:02 AM" },
    { kind: "prayer", key: "dhuhr", at: at(10), time: "10:10 AM" },
  ];
  const countdown = () => screen.getByTestId("now-countdown").textContent;

  it("counts down each minute, then shows the next item when the first one starts", () => {
    render(<NowCard lang="en" items={ITEMS} serverNow={NOW.toISOString()} />);
    expect([screen.getByTestId("now-name").textContent, countdown()]).toEqual(["Stand-up", "in 2 min"]);
    act(() => { vi.advanceTimersByTime(MIN); });
    expect(countdown()).toBe("in 1 min");
    act(() => { vi.advanceTimersByTime(MIN); }); // zero: the card moves on at once
    expect([screen.getByTestId("now-name").textContent, countdown()]).toEqual(["Dhuhr", "in 8 min"]);
    expect(screen.getByTestId("now-card")).toHaveAttribute("data-kind", "prayer");
    act(() => { vi.advanceTimersByTime(3 * MIN); });
    expect(countdown()).toBe("in 5 min");
  });

  it("uses one timer a minute, not one a second", () => {
    render(<NowCard lang="en" items={ITEMS} serverNow={NOW.toISOString()} />);
    expect(vi.getTimerCount()).toBe(1);
    act(() => { vi.advanceTimersByTime(59_000); });
    expect(countdown()).toBe("in 2 min");
  });

  it("stops while the page is hidden and catches up when it is shown again", () => {
    render(<NowCard lang="en" items={ITEMS} serverNow={NOW.toISOString()} />);
    const visibility = vi.spyOn(document, "visibilityState", "get");
    visibility.mockReturnValue("hidden");
    act(() => { document.dispatchEvent(new Event("visibilitychange")); });
    expect(vi.getTimerCount()).toBe(0);
    vi.setSystemTime(new Date(NOW.getTime() + 4 * MIN));
    visibility.mockReturnValue("visible");
    act(() => { document.dispatchEvent(new Event("visibilitychange")); });
    expect([screen.getByTestId("now-name").textContent, countdown()]).toEqual(["Dhuhr", "in 6 min"]);
    visibility.mockRestore();
  });

  it("is not a live region: a tick is never read out", () => {
    render(<NowCard lang="en" items={ITEMS} serverNow={NOW.toISOString()} />);
    const section = screen.getByTestId("now-card");
    expect(section).not.toHaveAttribute("aria-live");
    expect(section.querySelector("[aria-live], [role='status'], [role='timer']")).toBeNull();
  });

  it("words the countdown as the table in UI.md gives it, in both languages", () => {
    const en = messages("en").now.countdown;
    const ar = messages("ar").now.countdown;
    expect([en(0, 1), en(0, 42), en(1, 0), en(2, 12)]).toEqual(["in 1 min", "in 42 min", "in 1 hr", "in 2 hr 12 min"]);
    expect([ar(0, 1), ar(0, 2), ar(0, 5), ar(0, 42)]).toEqual(["بعد دقيقة", "بعد دقيقتين", "بعد 5 دقائق", "بعد 42 دقيقة"]);
    expect([ar(1, 0), ar(2, 0), ar(3, 0), ar(11, 0)]).toEqual(["بعد ساعة", "بعد ساعتين", "بعد 3 ساعات", "بعد 11 ساعة"]);
    expect([ar(1, 5), ar(2, 12), ar(3, 2)]).toEqual(["بعد ساعة و5 دقائق", "بعد ساعتين و12 دقيقة", "بعد 3 ساعات ودقيقتين"]);
  });
});

describe("AC-16 (with Q3): today's plan", () => {
  const withPlan = async (events: number, tasks: number, over: Partial<TodaySnapshot> = {}): Promise<TodaySnapshot> => ({
    ...(await live()),
    events: Array.from({ length: events }, (_, i) => ({ id: `e${i}`, title: `Event ${i}`, place: "", allDay: i === 0, time: `${i}:00 PM` })),
    tasks: Array.from({ length: tasks }, (_, i) => ({ id: `t${i}`, title: `Task ${i}`, due: "Today", overdue: i === 1 })),
    ...over,
  });
  const rows = (testId: string) => within(screen.getByTestId(testId)).getAllByRole("listitem").map((li) => li.textContent);

  it("lists at most 5 events (all-day first, then in time order) and 3 tasks, each with +N more", async () => {
    draw(await withPlan(7, 5));
    expect(rows("plan-events")).toEqual(["All dayEvent 0", "1:00 PMEvent 1", "2:00 PMEvent 2", "3:00 PMEvent 3", "4:00 PMEvent 4", "+2 more"]);
    expect(screen.getByLabelText("2 more events not shown")).toBeInTheDocument();
    expect(rows("plan-tasks")).toEqual(["Task 0Today", "Task 1Overdue, Today", "Task 2Today", "+2 more"]);
    expect(screen.getByLabelText("2 more tasks not shown")).toBeInTheDocument();
    expect(screen.getByTestId("plan-events")).toHaveAccessibleName("Events");
    expect(screen.getByTestId("plan-tasks")).toHaveAccessibleName("Tasks");
  });

  it("shows no count at exactly 5 events and 3 tasks", async () => {
    draw(await withPlan(5, 3));
    expect(rows("plan-events")).toHaveLength(5);
    expect(rows("plan-tasks")).toHaveLength(3);
    expect(document.body).not.toHaveTextContent("more");
  });

  it("an overdue task says Overdue in words", async () => {
    draw(await withPlan(0, 2));
    expect(screen.getByTestId("plan-tasks").querySelector("[data-overdue='true']")).toHaveTextContent("Overdue");
  });

  it("shows a short neutral line, not an error, with no events or no tasks", async () => {
    draw(await withPlan(0, 0));
    expect(rows("plan-events")).toEqual(["No more events today."]);
    expect(rows("plan-tasks")).toEqual(["No tasks due today."]);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("says a source is not available without naming the fault or the fix, in both languages", async () => {
    const first = draw(await withPlan(0, 0, { google: "reconnect", todoist: "not_connected" }));
    expect(rows("plan-events")).toEqual(["Calendar isn't available right now."]);
    expect(rows("plan-tasks")).toEqual(["Tasks aren't available right now."]);
    first.unmount();
    draw(await withPlan(7, 5, { google: "waiting", todoist: "stale" }), "ar");
    expect(rows("plan-events").at(-1)).toBe("و2 غيرها");
    expect(rows("plan-tasks").at(-1)).toBe("و2 غيرها");
  });

  it("the live source gives today's remaining event only: not tomorrow's, not one that is over", async () => {
    expect((await live({ ...FEED, nextEvent: event(60) })).events).toHaveLength(1);
    expect((await live({ ...FEED, nextEvent: event(-30) })).events).toHaveLength(1); // started, not over yet
    expect((await live({ ...FEED, nextEvent: event(-120) })).events).toEqual([]);
    expect((await live({ ...FEED, nextEvent: event(60 * 30) })).events).toEqual([]);
    const allDay = await live({ ...FEED, nextEvent: { ...event(0), start: "2026-11-14", end: "2026-11-15", allDay: true } });
    expect(allDay.events).toMatchObject([{ allDay: true, time: "All day" }]);
  });
});

describe("AC-17: Ahmad's one message", () => {
  const choose = (approvals: ApprovalCard[], cards: AhmadCard[]) => chooseAhmadMessage(approvals, cards, NOW, TZ);
  const brief = card(9, { kind: "brief", title: "Morning brief" });

  it("(1) the oldest pending approval, with a count of the others", () => {
    expect(choose([approval(1), approval(30), approval(5)], [card(1), brief]))
      .toEqual({ kind: "approval", id: id(130), title: "Send email 30?", more: 2 });
    expect(choose([approval(1)], [])).toMatchObject({ more: 0 });
    // Decided or expired approvals are not waiting.
    expect(choose([approval(1, { status: "rejected" }), approval(2, { expiresAt: at(-1) })], [])).toBeNull();
  });

  it("(2) the newest unread reminder, (3) today's unread brief, (4) nothing", () => {
    expect(choose([], [card(8), card(2), brief])).toMatchObject({ kind: "reminder", id: id(2) });
    expect(choose([], [card(2, { readAt: at(-1) }), brief])).toMatchObject({ kind: "brief", id: id(9) });
    expect(choose([], [{ ...brief, readAt: at(-1) }])).toBeNull();
    expect(choose([], [{ ...brief, createdAt: at(-24 * 60) }])).toBeNull(); // yesterday's brief
    expect(choose([], [])).toBeNull();
  });

  it("never chooses a mail or a test card", () => {
    expect(choose([], [card(1, { kind: "mail" }), card(2, { kind: "test" })])).toBeNull();
  });

  it("shows exactly one item, or one quiet line", async () => {
    const some = draw(await live(FEED, [approval(1), approval(30)], [card(1), brief]));
    expect(screen.getAllByTestId("ahmad-message")).toHaveLength(1);
    expect(screen.getByTestId("ahmad-message")).toHaveTextContent("Send email 30?");
    expect(screen.getByTestId("ahmad-message")).toHaveTextContent("Waiting for your approval, and 1 more");
    some.unmount();
    const reminder = draw(await live(FEED, [], [card(2), brief]));
    expect(screen.getByTestId("ahmad-message")).toHaveTextContent("Reminder 2");
    expect(screen.getByTestId("ahmad-message")).toHaveTextContent("9:58 AM"); // 12-hour (AC-31)
    reminder.unmount();
    draw(await live(FEED, [], [card(1, { kind: "mail" })]));
    expect(screen.queryByTestId("ahmad-message")).toBeNull();
    expect(screen.getByTestId("ahmad-empty")).toHaveTextContent("Nothing from Ahmad right now.");
  });

  it("an approval still shows when the cards could not be read", async () => {
    const today = await new LiveTodaySource(async () => [approval(1)], async () => FEED, async () => { throw new Error("down"); }).getToday("en", NOW);
    expect(today.cards).toBeNull();
    draw(today);
    expect(screen.getByTestId("ahmad-message")).toHaveTextContent("Send email 1?");
  });
});

describe("AC-18: Ahmad's message opens the Inbox with that item", () => {
  it("links to /inbox?open=<id> for a card and for an approval, with a full name for screen readers", async () => {
    const first = draw(await live(FEED, [], [card(2)]));
    expect(screen.getByTestId("ahmad-message")).toHaveAttribute("href", `/inbox?open=${id(2)}`);
    expect(screen.getByTestId("ahmad-message")).toHaveAccessibleName("Reminder 2. Reminder 9:58 AM. Open in Inbox.");
    first.unmount();
    draw(await live(FEED, [approval(1)], [card(2)]));
    expect(screen.getByTestId("ahmad-message")).toHaveAttribute("href", `/inbox?open=${id(101)}`);
    expect(screen.getByTestId("ahmad-message").className).toContain("min-h-11");
  });
});

describe("AC-19: the connection notes are in Settings, with the same states", () => {
  it("shows Google, Yahoo and Todoist always, each with its state's sentence", async () => {
    const today = await live({ ...FEED, googleStatus: "reconnect", yahooStatus: "not_connected", todoistStatus: "error" });
    render(<Connections lang="en" states={{ google: today.google, yahoo: today.yahoo, todoist: today.todoist }} />);
    const t = messages("en");
    expect(screen.getByTestId("google-status")).toHaveTextContent(t.google.reconnect);
    expect(screen.getByTestId("yahoo-status")).toHaveTextContent(t.yahoo.not_connected);
    expect(screen.getByTestId("todoist-status")).toHaveTextContent(t.todoist.error);
    expect(["google", "yahoo", "todoist"].map((s) => screen.getByTestId(`${s}-status`).getAttribute("data-state")))
      .toEqual(["reconnect", "not_connected", "error"]);
    for (const s of ["google", "yahoo", "todoist"]) {
      expect(screen.getByTestId(`${s}-status`)).toHaveAttribute("role", "status");
      expect(screen.getByTestId(`${s}-status`)).toHaveTextContent("Needs attention"); // not by colour alone
    }
  });

  it("shows ok, waiting and stale too, in Arabic", async () => {
    const waiting = await live(null, [], [], "ar");
    const first = render(<Connections lang="ar" states={{ google: waiting.google, yahoo: waiting.yahoo, todoist: waiting.todoist }} />);
    expect(screen.getByTestId("google-status")).toHaveTextContent(messages("ar").google.waiting);
    expect(screen.getByTestId("google-status")).not.toHaveTextContent(messages("ar").settings.needsAttention);
    first.unmount();
    render(<Connections lang="ar" states={{ google: "ok", yahoo: "stale", todoist: "off" }} />);
    expect(screen.getByTestId("google-status")).toHaveTextContent(messages("ar").google.ok);
    expect(screen.getByTestId("yahoo-status")).toHaveTextContent(messages("ar").yahoo.stale);
    expect(screen.getByTestId("yahoo-status")).toHaveTextContent(messages("ar").settings.needsAttention);
    expect(screen.getByTestId("todoist-status")).toHaveTextContent(messages("ar").todoist.off);
  });

  it("the menu's Settings item carries a mark when a connection is broken", () => {
    const labels = { menu: "Menu", closeMenu: "Close", theme: "Appearance", dark: "Dark", light: "Light", language: "Language",
      signOut: "Sign out", settings: "Settings", needsAttention: "Needs attention" };
    const { unmount } = render(<Menu labels={labels} theme="dark" lang="en" signOutAction={async () => {}} settingsAttention />);
    act(() => { screen.getByRole("button", { name: "Menu" }).click(); });
    expect(screen.getByTestId("menu-settings")).toHaveTextContent("Needs attention");
    unmount();
    render(<Menu labels={labels} theme="dark" lang="en" signOutAction={async () => {}} />);
    act(() => { screen.getByRole("button", { name: "Menu" }).click(); });
    expect(screen.queryByTestId("settings-attention")).toBeNull();
  });
});
