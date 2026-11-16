/**
 * Snafi UI job: Agent 15's acceptance tests for the parts of AC-1 to AC-33 that the build's own
 * tests (ui-inbox, ui-today, ui-chat-scroll, ui-overflow, rls-inbox) did not reach:
 *   - the real (Supabase) mailbox's card query and mark-read call, with a stand-in client;
 *   - the mark-read server action failing quietly;
 *   - Ahmad's message opening an approval in the Inbox (AC-18);
 *   - outside text that has no data-slot (AC-26);
 *   - fonts, theme tokens, 12-hour times, target sizes and reduced motion (AC-29, AC-31 to AC-33);
 *   - nothing but plain data crossing from a server component to a client component.
 *
 * jsdom has no layout and does not apply the stylesheet. Sizes, wrapping, mirroring, contrast and
 * motion are checked here by class and by the rule in globals.css, never by measuring. The real
 * check is a browser at 360 and 390 px (AC-25) and Khalid's phones.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const nav = vi.hoisted(() => ({ path: "/today" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => {} }),
  usePathname: () => nav.path,
  redirect: () => {},
}));
import { READ_KEEP_MS, type AhmadCard, type ApprovalCard, type MailboxMessage, type TodayFeed } from "@/adapters/mailbox/types";
import { LiveTodaySource } from "@/adapters/today/live";
import type { TodaySnapshot } from "@/adapters/today/types";
import { ChatView } from "@/app/(app)/chat/ChatView";
import { InboxView } from "@/app/(app)/inbox/InboxView";
import { TodayView } from "@/app/(app)/today/TodayView";
import { Bell } from "@/components/Bell";
import { ShellProvider } from "@/components/ShellState";
import { AppTopBar } from "@/components/TopBar";
import { unreadIds } from "@/core/inbox";
import { contentSecurityPolicy } from "@/core/security-headers";
import { messages } from "@/i18n/messages";

const ROOT = process.cwd();
const read = (path: string) => readFileSync(resolve(ROOT, path), "utf8");
const CSS = read("src/app/globals.css");
const rule = (name: string) => new RegExp(`\\.${name}\\s*\\{([^}]*)\\}`).exec(CSS)?.[1] ?? "";
const REDUCED = CSS.slice(CSS.indexOf("@media (prefers-reduced-motion: reduce)"));
function files(dir: string): string[] {
  return readdirSync(resolve(ROOT, dir)).flatMap((name) => {
    const path = join(dir, name);
    return statSync(resolve(ROOT, path)).isDirectory() ? files(path) : [path];
  });
}
const SOURCES = files("src").filter((f) => /\.(ts|tsx|css)$/.test(f));

const NOW = new Date("2026-11-14T07:00:00Z"); // 10:00 AM in Jeddah
const MIN = 60_000;
const DAY = 24 * 60 * MIN;
const ME = "11111111-1111-4111-8111-111111111111";
const at = (minutes: number) => new Date(NOW.getTime() + minutes * MIN).toISOString();
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const LONG = "W".repeat(200);
const URL_ = `https://example.com/${"a-very-long-path/".repeat(12)}page.html?query=${"x".repeat(60)}`;

const card = (n: number, over: Partial<AhmadCard> = {}): AhmadCard =>
  ({ id: id(n), kind: "reminder", title: `Reminder ${n}`, body: `Body of ${n}`, createdAt: at(-n), readAt: null, ...over });
const approval = (n: number, over: Partial<ApprovalCard> = {}): ApprovalCard =>
  ({ id: id(100 + n), conversationId: ME, tool: "gmail_send", args: { to: "sample@example.com", subject: "Running late" },
    argsHash: "c".repeat(64), summary: `Send email ${n}?`, status: "pending", createdAt: at(-n), expiresAt: at(600), ...over });
const FEED: TodayFeed = {
  nextEvent: { title: "Design review", start: at(60), end: at(120), location: "Room 3", allDay: false },
  emails: [], tasks: [{ content: "Call the bank", due: at(90), priority: 1, overdue: false, recurring: false }],
  googleStatus: "ok", yahooStatus: "ok", todoistStatus: "ok", updatedAt: at(-1),
};
const live = (approvals: ApprovalCard[], cards: AhmadCard[], lang: "en" | "ar" = "en"): Promise<TodaySnapshot> =>
  new LiveTodaySource(async () => approvals, async () => FEED, async () => cards).getToday(lang, NOW);

const ok = vi.fn(async () => ({ ok: true }));
const decide = vi.fn(async (_id: string, decision: string) => ({ ok: true, status: decision }));
function Inbox({ lang = "en" as "en" | "ar", approvals = [approval(1)], cards = [card(1)], open }:
  { lang?: "en" | "ar"; approvals?: ApprovalCard[]; cards?: AhmadCard[]; open?: string }) {
  return (
    <ShellProvider>
      <Bell lang={lang} unreadIds={unreadIds(approvals, cards, NOW)} current />
      <InboxView lang={lang} now={NOW.toISOString()} approvals={approvals} cards={cards} open={open} decide={decide} markRead={ok} />
    </ShellProvider>
  );
}

beforeEach(() => {
  nav.path = "/today";
  ok.mockClear();
  decide.mockClear();
});
afterEach(() => {
  vi.useRealTimers();
});

// ---------------------------------------------------------------------------------------------
describe("AC-1: the signed-in bar knows its screen from the address", () => {
  const labels = { menu: "Menu", closeMenu: "Close", theme: "Appearance", dark: "Dark", light: "Light", language: "Language", signOut: "Sign out" };
  it.each([["/today", null], ["/inbox", "Inbox"], ["/chat", "Ahmad"], ["/settings", "Settings"]] as const)(
    "%s has the bell, and only the Inbox's bell says it is the current page", (path, title) => {
      nav.path = path;
      render(<AppTopBar unreadIds={[id(1), id(2)]} theme="dark" lang="en" labels={labels} />);
      expect(screen.getByTestId("bell")).toHaveAttribute("href", "/inbox");
      expect(screen.getByTestId("bell")).toHaveAccessibleName("Inbox, 2 unread");
      expect(screen.getByTestId("bell").getAttribute("aria-current")).toBe(path === "/inbox" ? "page" : null);
      if (title) expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(title);
      else expect(screen.getByTestId("wordmark")).toBeInTheDocument();
    });
});

// ---------------------------------------------------------------------------------------------
// ---------------------------------------------------------------------------------------------
describe("AC-18: Ahmad's message opens the Inbox at that item", () => {
  let scrolled: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    scrolled = vi.fn();
    Element.prototype.scrollIntoView = scrolled as unknown as typeof Element.prototype.scrollIntoView;
  });
  afterEach(() => {
    delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView;
  });

  it("an approval: it is brought into view and focused, with its arguments, Approve and Reject; nothing is marked read", async () => {
    const today = await live([approval(1)], [card(1)]);
    const view = render(<TodayView lang="en" hour={10} today={today} now={NOW} />);
    const href = screen.getByTestId("ahmad-message").getAttribute("href")!;
    expect(href).toBe(`/inbox?open=${id(101)}`);
    view.unmount();

    window.history.replaceState(null, "", href);
    await act(async () => { render(<Inbox open={id(101)} />); });
    const item = document.getElementById(`inbox-${id(101)}`)!;
    expect(document.activeElement).toBe(item);
    expect(scrolled).toHaveBeenCalledWith({ block: "start", behavior: "auto" }); // no animated scroll (AC-33)
    expect(within(item).getByTestId("approval-args")).toHaveTextContent("sample@example.com");
    expect(within(item).getByRole("button", { name: "Approve" })).toBeEnabled();
    expect(within(item).getByRole("button", { name: "Reject" })).toBeEnabled();
    expect(ok).not.toHaveBeenCalled();
    expect(screen.getByTestId("bell-badge")).toHaveTextContent("2"); // opening it does not uncount it (AC-7)
    expect(document.getElementById(`inbox-${id(1)}`)).toHaveAttribute("data-unread", "true");
    expect(window.location.search).toBe("");
  });

  it("a card that is already read is opened and not marked again", async () => {
    window.history.replaceState(null, "", `/inbox?open=${id(1)}`);
    await act(async () => { render(<Inbox open={id(1)} approvals={[]} cards={[card(1, { readAt: at(-30) })]} />); });
    expect(screen.getByText("Body of 1")).toBeInTheDocument();
    expect(ok).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------------------------
describe("AC-26: outside text with no data-slot is guarded too", () => {
  /** Classes whose rule in globals.css wraps anywhere (inherited by what is inside) or cuts with an ellipsis. */
  const GUARDS = ["wrap", "bubble", "truncate", "btn", "option", "note"];
  /** Every piece of text with a run of 60 or more characters and no space must sit in a guarded element. */
  function unguarded(container: HTMLElement): string[] {
    const found: string[] = [];
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!/\S{60,}/.test(node.textContent ?? "")) continue;
      let el = node.parentElement;
      let guarded = false;
      for (; el && container.contains(el); el = el.parentElement) {
        if ((el.getAttribute("class") ?? "").split(/\s+/).some((c) => GUARDS.includes(c))) { guarded = true; break; }
      }
      const parent = node.parentElement!;
      if (!guarded) found.push(`<${parent.tagName.toLowerCase()} class="${parent.className}"> ${(node.textContent ?? "").slice(0, 24)}…`);
    }
    return found;
  }
  const LONG_APPROVAL = approval(1, { tool: LONG, summary: `${LONG} ${URL_}`, args: { [LONG.slice(0, 90)]: URL_, [URL_]: LONG } });
  const LONG_CARDS = [card(1, { title: LONG, body: `${LONG}\n${URL_}` }), card(2, { kind: "mail", title: URL_, body: LONG }),
    card(3, { kind: "brief", title: URL_, body: LONG }), card(4, { kind: "test", title: LONG, body: URL_ })];

  it("the guard rules exist in globals.css", () => {
    for (const name of GUARDS.filter((g) => g !== "truncate")) expect(rule(name), name).toContain("overflow-wrap: anywhere");
  });

  it.each(["en", "ar"] as const)("Inbox, open and closed, with a decided approval's line (%s)", async (lang) => {
    const { container } = render(<Inbox lang={lang} approvals={[LONG_APPROVAL, approval(2)]} cards={LONG_CARDS} />);
    expect(unguarded(container)).toEqual([]);
    for (const button of container.querySelectorAll<HTMLElement>("[data-testid='inbox-row'] > button")) {
      await act(async () => { fireEvent.click(button); });
    }
    expect(container.querySelectorAll("[data-slot='card-body']").length).toBe(3);
    expect(unguarded(container)).toEqual([]);
    // The argument names (dt) carry outside text and have no data-slot.
    expect(container.querySelector("dt[dir='ltr']")!.className).toContain("wrap");
  });

  it.each(["en", "ar"] as const)("Today: the task's due text, the event and Ahmad's message (%s)", async (lang) => {
    const base = await live([], [card(1, { title: `${LONG} ${URL_}` })], lang);
    const today: TodaySnapshot = { ...base,
      now: [{ kind: "event", title: URL_, place: LONG, at: at(30), time: "10:30 AM" }],
      events: [{ id: "e1", title: URL_, place: LONG, allDay: false, time: "10:30 AM" }],
      tasks: [{ id: "t1", title: URL_, due: LONG, overdue: true }, { id: "t2", title: LONG, due: URL_ }] };
    const { container } = render(<TodayView lang={lang} hour={10} today={today} now={NOW} />);
    expect(container.textContent).toContain(LONG);
    expect(unguarded(container)).toEqual([]);
    const withApproval = render(<TodayView lang={lang} hour={10} today={{ ...today, approvals: [LONG_APPROVAL] }} now={NOW} />);
    expect(unguarded(withApproval.container)).toEqual([]);
  });

  it.each(["en", "ar"] as const)("Chat: both speakers' messages and an approval card (%s)", (lang) => {
    const say = (n: number, role: "user" | "assistant", body: string, approvalId: string | null = null): MailboxMessage =>
      ({ id: `m${n}`, userId: ME, conversationId: ME, role, body, lang, jobId: null, approvalId, meta: {}, createdAt: "" });
    const { container } = render(
      <ChatView lang={lang} messages={[say(1, "user", LONG), say(2, "assistant", URL_), say(3, "assistant", "card", LONG_APPROVAL.id)]}
        cards={{ [LONG_APPROVAL.id]: LONG_APPROVAL }} actions={{}} preview decide={decide} undo={ok} send={async () => ({ error: false, sentAt: 1 })} />);
    expect(container.querySelectorAll("[data-slot='chat-message']").length).toBe(2);
    expect(unguarded(container)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------------------------
describe("AC-29: two themes, the gold accent and the four self-hosted fonts", () => {
  const block = (pattern: RegExp) => new Set([...(pattern.exec(CSS)?.[1] ?? "").matchAll(/(--[a-z-]+)\s*:/g)].map((m) => m[1]));
  const dark = block(/:root,\s*:root\[data-theme="dark"\]\s*\{([^}]*)\}/);
  const light = block(/:root\[data-theme="light"\]\s*\{([^}]*)\}/);

  it("light defines every colour token that dark defines, and both keep a gold", () => {
    expect(dark.size).toBeGreaterThan(15);
    expect([...light].sort()).toEqual([...dark].sort());
    for (const token of ["--gold", "--gold-ink", "--bg", "--card", "--text", "--muted", "--focus", "--danger", "--badge-bg", "--badge-fg"]) {
      expect(dark.has(token), token).toBe(true);
    }
    expect(CSS).toMatch(/--gold: #c9a96e;/);
    expect(CSS).toMatch(/--gold: #b8935a;/);
  });

  it("every colour the components use comes from a token, so both themes reach every screen", () => {
    const body = CSS.slice(CSS.indexOf("@layer base"));
    // Only two literal colours outside the token blocks: the black mixed into the orb's edge.
    const literals = [...body.matchAll(/#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)/g)].map((m) => m[0]);
    expect(literals).toEqual(["#000"]);
    // The PWA browser-chrome colour (viewport.themeColor) is the one place a literal is required:
    // the <meta name="theme-color"> value is read by the operating system, which cannot see a CSS
    // variable. It paints no screen, so it is taken out before the check; nothing else may hold one.
    const withoutChrome = (source: string) => source.replace(/themeColor:\s*\[[\s\S]*?\]/g, "themeColor: []");
    expect(withoutChrome(read("src/app/layout.tsx"))).not.toContain("#0E0E10"); // the exemption removed it
    for (const file of SOURCES.filter((f) => f.endsWith(".tsx"))) {
      expect(withoutChrome(read(file)), file).not.toMatch(/(?:bg|text|border)-\[#|#[0-9a-fA-F]{3,8}\b/);
    }
  });

  it("names only Cormorant Garamond, Inter, Amiri and IBM Plex Sans Arabic, plus the device's own fallbacks", () => {
    const allowed = ["Cormorant Garamond", "Inter Variable", "Inter", "Amiri", "IBM Plex Sans Arabic", "Times New Roman", "system-ui", "serif", "sans-serif"];
    const stacks = [...CSS.matchAll(/--font-(?:heading|body):\s*([^;]+);/g)].map((m) => m[1]).filter((v) => !v.startsWith("var("));
    expect(stacks).toHaveLength(4);
    for (const stack of stacks) {
      for (const family of stack.split(",").map((f) => f.trim().replace(/^"|"$/g, ""))) expect(allowed, family).toContain(family);
    }
    for (const m of CSS.matchAll(/font-family:\s*([^;]+);/g)) expect(m[1]).toMatch(/^var\(--font-(heading|body)\)$/);
    for (const file of SOURCES.filter((f) => f.endsWith(".tsx"))) expect(read(file), file).not.toMatch(/fontFamily|font-\[/);
  });

  it("loads the fonts from the installed packages only: no font service, no @font-face of its own, no outside address", () => {
    const layout = read("src/app/layout.tsx");
    const packages = [...layout.matchAll(/^import "(@fontsource(?:-variable)?\/[a-z-]+)/gm)].map((m) => m[1]);
    expect([...new Set(packages)].sort()).toEqual(
      ["@fontsource-variable/inter", "@fontsource/amiri", "@fontsource/cormorant-garamond", "@fontsource/ibm-plex-sans-arabic"]);
    expect(CSS).not.toMatch(/@font-face|url\(|@import\s+(?:url|["']https?:)/);
    for (const file of SOURCES) {
      expect(read(file), file).not.toMatch(/next\/font|fonts\.googleapis|fonts\.gstatic|typekit|cdn\.jsdelivr|unpkg\.com|<link[^>]+stylesheet/);
    }
    // The browser is told to refuse a font, style or connection from any other host.
    const csp = contentSecurityPolicy("A".repeat(22) + "==", false);
    expect(csp).toContain("font-src 'self'");
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("connect-src 'self'");
  });
});

// ---------------------------------------------------------------------------------------------
describe("AC-31: every time on Today and in the Inbox is 12-hour with AM/PM or ص/م", () => {
  /**
   * Every h:mm the screen shows, with what follows it, taken one text node (and one aria-label) at
   * a time. Joining the whole container would run one element's text straight into the next one's
   * ("11:00 AM" + "Design review"), which is not what a reader sees.
   */
  function times(container: HTMLElement): { hour: number; period: string | undefined; text: string }[] {
    const pieces: string[] = [...container.querySelectorAll("[aria-label]")].map((el) => el.getAttribute("aria-label") ?? "");
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) pieces.push(node.textContent ?? "");
    return pieces.flatMap((piece) => [...piece.matchAll(/(\d{1,2}):(\d{2})(?:\s?(AM|PM|ص|م)(?![A-Za-z؀-ۿ]))?/g)]
      .map((m) => ({ hour: Number(m[1]), period: m[3], text: m[0] })));
  }
  const cards = [card(2), card(3, { kind: "brief", title: "Morning brief" }), card(4, { kind: "mail", title: "Sample Sender", body: "Subject" }),
    card(5, { createdAt: at(-17 * 60) }), card(6, { createdAt: at(-3 * 24 * 60 - 13 * 60), readAt: at(-60) })];

  it.each([["en", ["AM", "PM"]], ["ar", ["ص", "م"]]] as const)("in %s", async (lang, periods) => {
    const today = render(<TodayView lang={lang} hour={10} today={await live([], cards, lang)} now={NOW} />);
    const onToday = times(today.container);
    expect(onToday.length).toBeGreaterThanOrEqual(4); // the Now card, its label, the plan's event, the task, Ahmad's message
    today.unmount();
    const inbox = render(<Inbox lang={lang} approvals={[approval(1), approval(200, { expiresAt: at(15 * 60) })]} cards={cards} />);
    const inInbox = times(inbox.container);
    expect(inInbox.length).toBeGreaterThanOrEqual(9); // 5 rows, 2 "asked", 2 "expires"
    for (const time of [...onToday, ...inInbox]) {
      expect(periods as readonly string[], time.text).toContain(time.period);
      expect(time.hour, time.text).toBeGreaterThanOrEqual(1);
      expect(time.hour, time.text).toBeLessThanOrEqual(12);
    }
    // Both halves of the day really appear, so a clock stuck on one period would show.
    expect(new Set(inInbox.map((time) => time.period)).size).toBe(2);
  });
});

// ---------------------------------------------------------------------------------------------
describe("AC-32: targets of 44px, names and keyboard reach", () => {
  it("the rules give 44px: icon buttons are 44 by 44, buttons at least 44 tall (48 for Approve and Reject)", () => {
    expect(rule("icon-btn")).toMatch(/width: 44px; height: 44px;/);
    expect(rule("btn")).toContain("min-height: 44px");
    expect(rule("btn-tall")).toContain("min-height: 48px");
    expect(rule("option")).toContain("min-height: 44px");
  });

  it.each([["en", "Approve", "Reject", "Back to Today"], ["ar", "موافقة", "رفض", "العودة إلى اليوم"]] as const)(
    "the bell, back, inbox rows, Approve and Reject are real links and buttons that take focus, in page order (%s)", (lang, approve, reject, back) => {
      nav.path = "/inbox";
      const labels = { menu: "Menu", closeMenu: "Close", theme: "Appearance", dark: "Dark", light: "Light", language: "Language", signOut: "Sign out" };
      render(
        <ShellProvider>
          <AppTopBar unreadIds={[id(101), id(1)]} theme="dark" lang={lang} labels={labels} />
          <InboxView lang={lang} now={NOW.toISOString()} approvals={[approval(1)]} cards={[card(1), card(2)]} decide={decide} markRead={ok} />
        </ShellProvider>);
      const bell = screen.getByTestId("bell");
      const targets: HTMLElement[] = [screen.getByRole("link", { name: back }), bell, screen.getByRole("button", { name: approve }),
        screen.getByRole("button", { name: reject }), ...screen.getAllByTestId("inbox-row").map((r) => within(r).getByRole("button"))];
      expect(targets).toHaveLength(6);
      for (const [i, target] of targets.entries()) {
        expect(["A", "BUTTON"], target.outerHTML.slice(0, 60)).toContain(target.tagName);
        expect(target).not.toHaveAttribute("tabindex", "-1");
        expect(target.closest("[aria-hidden='true'], [hidden], [inert]")).toBeNull();
        target.focus();
        expect(document.activeElement).toBe(target);
        if (i > 0) expect(targets[i - 1].compareDocumentPosition(target) & Node.DOCUMENT_POSITION_FOLLOWING, `order ${i}`).toBeTruthy();
      }
      expect(bell.className).toContain("icon-btn");
      expect(targets[0].className).toContain("icon-btn");
      for (const button of [targets[2], targets[3]]) expect(button.className).toMatch(/\bbtn\b.*\bbtn-tall\b/);
      for (const rowButton of targets.slice(4)) {
        expect(rowButton.className).toContain("min-h-11");
        expect(rowButton.className).toContain("w-[calc(100%+1rem)]"); // the whole row is the target
      }
      // Enter or Space on a focused <button> is a click: the row opens from the keyboard.
      fireEvent.click(targets[4]);
      expect(targets[4]).toHaveAttribute("aria-expanded", "true");
    });
});

// ---------------------------------------------------------------------------------------------
describe("AC-33: reduce motion", () => {
  it("the Inbox opens a card with one fade only, and the reduce-motion rules switch it and the chevron off", async () => {
    render(<Inbox approvals={[]} />);
    await act(async () => { fireEvent.click(within(screen.getByTestId("inbox-row")).getByRole("button")); });
    const body = screen.getByText("Body of 1");
    expect(body.className).toContain("fade-in");
    expect(body.getAttribute("style")).toBeNull(); // no height or transform is animated from the element itself
    expect(screen.getByTestId("inbox-row").querySelector(".chevron")).not.toBeNull();
    expect(rule("fade-in")).toMatch(/^\s*animation: snafi-fade /);
    expect(REDUCED).toMatch(/\.fade-in, \.now-swap, \.jump, \.screen-in \{ animation: none; \}/);
    expect(REDUCED).toContain(".chevron { transition: none; }");
    expect(REDUCED).toContain("animation-duration: 0.01ms !important");
    expect(REDUCED).toContain("transition-duration: 0.01ms !important");
    expect(REDUCED).toContain("scroll-behavior: auto !important");
  });

  it("no rule scrolls smoothly by itself: smooth scrolling is asked for only in code, which checks reduce motion", () => {
    expect(CSS).not.toMatch(/scroll-behavior:\s*smooth/);
    const smooth = SOURCES.filter((f) => /\.tsx?$/.test(f) && /["']smooth["']/.test(read(f)));
    expect(smooth.map((f) => f.replace(/\\/g, "/"))).toEqual(["src/core/chat-scroll.ts"]);
  });
});

// ---------------------------------------------------------------------------------------------
describe("server to client: only plain data and server actions cross (Agent 14's risk a)", () => {
  const functionsIn = (value: unknown, path: string): string[] =>
    typeof value === "function" ? [path]
      : value && typeof value === "object" ? Object.entries(value).flatMap(([k, v]) => functionsIn(v, `${path}.${k}`)) : [];
  const isClient = (file: string) => /^\s*["']use client["']/.test(read(file));
  const tsx = SOURCES.filter((f) => f.endsWith(".tsx"));

  it.each(["en", "ar"] as const)("the dictionary groups handed to client components hold no functions (%s)", (lang) => {
    // settings/page.tsx passes t.settings to SettingsForm; sign-in/page.tsx passes t.signIn to SignInForm.
    expect(read("src/app/(app)/settings/page.tsx")).toContain("t={t.settings}");
    expect(read("src/app/sign-in/page.tsx")).toContain("t={t.signIn}");
    expect(functionsIn(messages(lang).settings, "settings")).toEqual([]);
    expect(functionsIn(messages(lang).signIn, "signIn")).toEqual([]);
    // The whole dictionary does hold functions, so it must never be the prop.
    expect(functionsIn(messages(lang), "t").length).toBeGreaterThan(5);
  });

  it("no server component hands a client component the whole dictionary or a function written in place", () => {
    const clientNames = tsx.filter(isClient).flatMap((f) => [...read(f).matchAll(/export (?:default )?function (\w+)/g)].map((m) => m[1]));
    expect(clientNames).toEqual(expect.arrayContaining(["InboxView", "ChatView", "SettingsForm", "SignInForm", "NowCard", "AppTopBar", "TopBar"]));
    const servers = tsx.filter((f) => !isClient(f));
    expect(servers.length).toBeGreaterThan(8);
    for (const file of servers) {
      const source = read(file);
      // A server component cannot hold an event handler or any other function written inside its JSX.
      expect(source, file).not.toMatch(/=\{\s*(?:async\s*)?\([^)]*\)\s*=>/);
      expect(source, file).not.toMatch(/=\{\s*(?:async\s+)?function\b/);
      for (const name of clientNames) {
        for (const use of source.matchAll(new RegExp(`<${name}\\b[^<]*`, "g"))) {
          expect(use[0], `${file}: <${name}>`).not.toMatch(/\bt=\{t\}|=\{messages\(/);
        }
      }
    }
  });

  it("the functions the pages do pass are server actions", () => {
    expect(read("src/app/(app)/actions.ts")).toMatch(/^"use server";/);
    expect(read("src/app/sign-in/actions.ts")).toMatch(/^\s*"use server";/);
    for (const [file, names] of [
      ["src/app/(app)/inbox/page.tsx", ["decideApproval", "markCardRead"]],
      ["src/app/(app)/chat/page.tsx", ["decideApproval", "sendMessage", "undoAction"]],
      ["src/app/(app)/settings/page.tsx", ["removePushSubscription", "requestTestPush", "savePushSubscription", "saveSettings"]],
      ["src/app/(app)/layout.tsx", ["signOut"]],
    ] as const) {
      const imported = /import \{([^}]*)\} from "\.\.?\/actions";/.exec(read(file))?.[1].split(",").map((s) => s.trim()).sort();
      expect(imported, file).toEqual([...names].sort());
    }
  });
});

describe("Next 16.4 error boundary prop (Agent 14's risk b)", () => {
  it("error.tsx takes `retry`, the name this installed Next passes, and wires it to the Try again button", () => {
    const boundary = read("node_modules/next/dist/client/components/error-boundary.js");
    expect(boundary).toMatch(/retry: this\.retry/);
    for (const file of ["src/app/(app)/inbox/error.tsx", "src/app/(app)/today/error.tsx"]) {
      expect(read(file)).toMatch(/^"use client";/);
      expect(read(file)).toMatch(/\(\{ retry \}: \{ error: unknown; retry: \(\) => void \}\)/);
      expect(read(file)).toMatch(/retry=\{retry\}/);
    }
  });
});

// A day constant used above only through at(); kept explicit so the 7-day window reads in days.
describe("AC-6: the 7-day window is 7 days", () => {
  it("READ_KEEP_MS", () => {
    expect(READ_KEEP_MS).toBe(7 * DAY);
  });
});

// ---------------------------------------------------------------------------------------------
/**
 * The server half of AC-6 and AC-11 and of PRD risk 7 is now run for real in
 * ui-inbox-server.test.tsx (the Supabase mailbox against a stand-in client, and the page's check
 * of `?open=`), after `server-only` was aliased to a stub in vitest.config.ts. The source-text
 * checks that stood here, which could only catch a silent change and not a wrong result, are gone
 * with it. The database half of AC-11 is run in rls-inbox.test.ts, the screen half in
 * ui-inbox.test.tsx. What stays here is the one rule no behaviour test can see.
 */
describe("AC-11: the app never writes to cards itself", () => {
  it("mark-read is the only way the mailbox changes a card", () => {
    const mailbox = read("src/adapters/mailbox/supabase.ts");
    expect(mailbox).toContain('rpc("mark_card_read", { p_id: checkId(id) })');
    expect(mailbox).not.toMatch(/from\("cards"\)[\s\S]{0,80}\.(update|insert|delete)\(/);
  });
});

/** SEC-177: the preview script may not fetch anything or go through a shell. Read, not run: it starts a server. */
describe("AC-30: dev:preview runs the Next already installed here", () => {
  const script = read("scripts/dev-preview.mjs");
  it("uses no npx and no shell, and starts node with the resolved Next binary", () => {
    expect(script).not.toMatch(/npx|shell: true/);
    expect(script).toContain('createRequire(import.meta.url).resolve("next/dist/bin/next")');
    expect(script).toContain('spawn(process.execPath, [next, "dev", "--hostname", "127.0.0.1", "--port", "3100"]');
  });
  it("stops with a message and a non-zero code when Next is not installed", () => {
    expect(script).toMatch(/catch \{[\s\S]*console\.error\([\s\S]*process\.exit\(1\);/);
  });
});
