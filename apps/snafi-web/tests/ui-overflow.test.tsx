/**
 * Snafi UI job, Story 4: the structural guards of AC-26, AC-27 and AC-28.
 *
 * IMPORTANT: jsdom has no layout. It does not compute widths, wrap text or apply the stylesheet,
 * so these tests cannot see a real overflow and the 360 and 390 "widths" below do not change what
 * jsdom draws. They check the guards that keep a page inside the screen: the wrapping or
 * truncation class on every slot that holds outside text, min-width:0 on the flex and grid items
 * around it, no fixed or minimum width above 360px in inline styles, class names or globals.css,
 * inputs of at least 16px, the root overflow backstop and logical (mirroring) properties.
 * Real overflow (AC-25: scrollWidth equals the viewport width) is measured in a browser,
 * separately, per page, width and language; real phones are checked by Khalid.
 */
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, fireEvent, render, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AhmadCard, ApprovalCard, MailboxMessage } from "@/adapters/mailbox/types";
import { PlaceholderTodaySource } from "@/adapters/today/placeholder";
import type { TodaySnapshot } from "@/adapters/today/types";
import { ChatView } from "@/app/(app)/chat/ChatView";
import { InboxView } from "@/app/(app)/inbox/InboxView";
import { Connections } from "@/app/(app)/settings/Connections";
import { SettingsForm } from "@/app/(app)/settings/SettingsForm";
import { TodayView } from "@/app/(app)/today/TodayView";
import { SignInForm } from "@/app/sign-in/SignInForm";
import { ShellProvider } from "@/components/ShellState";
import { TopBar, type Screen } from "@/components/TopBar";
import { DEFAULT_SETTINGS } from "@/adapters/mailbox/types";
import { direction, messages } from "@/i18n/messages";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }), usePathname: () => "/today" }));

const CSS = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");
const LONG = "W".repeat(200); // 200 characters with no space
const URL_ = `https://example.com/${"a-very-long-path/".repeat(12)}page.html?query=${"x".repeat(60)}`;
const NOW = new Date("2026-11-14T07:00:00Z");
const soon = (minutes: number) => new Date(NOW.getTime() + minutes * 60_000).toISOString();
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

const CARDS: AhmadCard[] = [
  { id: id(1), kind: "reminder", title: LONG, body: `${LONG}\n${URL_}`, createdAt: soon(-5), readAt: null },
  { id: id(2), kind: "mail", title: LONG, body: URL_, createdAt: soon(-6), readAt: null },
  { id: id(3), kind: "brief", title: URL_, body: LONG, createdAt: soon(-7), readAt: soon(-1) },
];
const APPROVAL: ApprovalCard = { id: id(9), conversationId: id(0), tool: LONG, args: { [LONG.slice(0, 80)]: URL_, body: LONG },
  argsHash: "c".repeat(64), summary: `${LONG} ${URL_}`, status: "pending", createdAt: soon(-9), expiresAt: soon(600) };
const MESSAGES: MailboxMessage[] = [
  ...[LONG, URL_, `نص عربي ${LONG}`].flatMap((body, i) => (["user", "assistant"] as const).map((role, j): MailboxMessage => ({
    id: `m${i}${j}`, userId: "u", conversationId: "x", role, body, lang: i === 2 ? "ar" : "en", jobId: null,
    approvalId: null, meta: {}, createdAt: "" }))),
  { id: "mc", userId: "u", conversationId: "x", role: "assistant", body: "card", lang: "en", jobId: null, approvalId: id(9), meta: {}, createdAt: "" },
];

async function longToday(lang: "en" | "ar"): Promise<TodaySnapshot> {
  const base = await new PlaceholderTodaySource().getToday(lang, NOW);
  return {
    ...base,
    now: [{ kind: "event", title: LONG, place: URL_, at: soon(30), time: "10:30 AM" }],
    events: [{ id: "e1", title: LONG, place: URL_, allDay: false, time: "10:30 AM" }, { id: "e2", title: URL_, place: "", allDay: true, time: "" }],
    tasks: [{ id: "t1", title: LONG, due: "Today" }, { id: "t2", title: URL_, due: LONG.slice(0, 40), overdue: true }],
    approvals: [{ ...APPROVAL }],
    cards: CARDS,
  };
}

const ok = async () => ({ ok: true });
const labels = (lang: "en" | "ar") => {
  const t = messages(lang);
  return { menu: t.menu, closeMenu: t.closeMenu, theme: t.theme, dark: t.dark, light: t.light, language: t.language, signOut: t.signOut,
    settings: t.settingsLink, needsAttention: t.settings.needsAttention };
};
const bar = (screen_: Screen, lang: "en" | "ar") => (
  <TopBar screen={screen_} unreadIds={Array.from({ length: 12 }, (_, i) => id(i))} theme="dark" lang={lang} labels={labels(lang)}
    signOutAction={async () => {}} statusLines={[`${LONG} ${URL_}`]} settingsAttention />
);

/** Each page as the app draws it: its top bar and its screen, with the long strings in every outside-text slot. */
const PAGES: Record<string, { slots: string[]; draw: (lang: "en" | "ar") => Promise<React.ReactNode> }> = {
  "Sign-in": { slots: [], draw: async (lang) => (
    <>{bar("sign-in", lang)}<SignInForm t={messages(lang).signIn} action={async () => ({ error: "invalid" as const })} serverSecure={false} /></>
  ) },
  Today: { slots: ["now-name", "now-place", "event-title", "task-title", "message-title"], draw: async (lang) => (
    <>{bar("today", lang)}<TodayView lang={lang} hour={10} today={await longToday(lang)} now={NOW} /></>
  ) },
  Inbox: { slots: ["approval-summary", "approval-arg", "card-title", "card-body", "mail-sender", "mail-subject"], draw: async (lang) => (
    <>{bar("inbox", lang)}<InboxView lang={lang} now={NOW.toISOString()} approvals={[APPROVAL]} cards={CARDS} decide={ok} markRead={ok} /></>
  ) },
  Chat: { slots: ["chat-message", "approval-summary", "approval-arg"], draw: async (lang) => (
    <>{bar("chat", lang)}<ChatView lang={lang} messages={MESSAGES} cards={{ [id(9)]: APPROVAL }} actions={{}} preview decide={ok} undo={ok} send={async () => ({ error: true, sentAt: 1 })} /></>
  ) },
  Settings: { slots: [], draw: async (lang) => (
    <>{bar("settings", lang)}
      <Connections lang={lang} states={{ google: "reconnect", yahoo: "error", todoist: "not_connected" }} />
      <SettingsForm initial={{ ...DEFAULT_SETTINGS, pushEnabled: true }} lang={lang} t={messages(lang).settings} publicKey={null}
        save={ok} subscribe={ok} unsubscribe={ok} test={ok} env={() => null} /></>
  ) },
};

async function draw(page: string, lang: "en" | "ar") {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
  document.documentElement.lang = lang;
  document.documentElement.dir = direction(lang);
  const node = await PAGES[page].draw(lang);
  const view = render(<ShellProvider>{node}</ShellProvider>);
  vi.useRealTimers();
  // Open what can be opened, so the open states are checked too: the menu and every Inbox row.
  await act(async () => { fireEvent.click(within(view.container).getByTestId("menu-button")); });
  for (const row of view.container.querySelectorAll<HTMLElement>("[data-testid='inbox-row'] > button")) {
    await act(async () => { fireEvent.click(row); });
  }
  return view;
}

// ---------- the guards ----------
const tokens = (el: Element) => (el.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);
const rule = (name: string) => {
  const match = new RegExp(`\\.${name}\\s*\\{([^}]*)\\}`).exec(CSS);
  return match ? match[1] : "";
};
/** Classes that wrap or cut text, and classes that let a flex or grid item shrink (checked against globals.css below). */
const TEXT_GUARDS = ["wrap", "bubble", "truncate"];
const MIN_ZERO = ["min-w-0", "wrap", "bubble", "surface", "btn", "option", "field", "note", "with-icon", "composer-input", "truncate"];
const ROW_FLEX = ["flex", "inline-flex", "with-icon", "note", "composer-surface", "topbar", "btn", "option"];
const isRowFlex = (el: Element) => tokens(el).some((t) => ROW_FLEX.includes(t)) && !tokens(el).includes("flex-col");
const gridTemplate = (el: HTMLElement) =>
  el.style.gridTemplateColumns || (tokens(el).includes("plan-row") ? /grid-template-columns:\s*([^;]+);/.exec(rule("plan-row"))?.[1] ?? "" : "");

const PX_PER_REM = 16;
/** A plain length in px, or null for anything else (percentages, auto, min(), calc(), fit-content…). */
function px(value: string): number | null {
  const m = /^\s*(-?\d*\.?\d+)(px|rem)\s*$/.exec(value);
  return m ? Number(m[1]) * (m[2] === "rem" ? PX_PER_REM : 1) : null;
}

describe("globals.css: the rules the guards rest on", () => {
  it("AC-27: the root backstop is there, and the gutter is 16px under 390px and 20px from 390px", () => {
    expect(CSS).toMatch(/html, body \{\s*overflow-x: clip;/);
    expect(CSS).toMatch(/--gutter: 16px;/);
    expect(CSS).toMatch(/@media \(min-width: 390px\) \{\s*:root \{ --gutter: 20px; \}/);
  });

  it("AC-26: the wrapping classes wrap anywhere, and the shrinkable classes have min-width: 0", () => {
    for (const name of ["wrap", "bubble", "btn", "option", "note"]) expect(rule(name), name).toContain("overflow-wrap: anywhere");
    for (const name of MIN_ZERO.filter((n) => n !== "min-w-0" && n !== "truncate")) expect(rule(name), name).toContain("min-width: 0");
    expect(rule("bubble")).toContain("max-inline-size: min(85%, 34rem)");
    expect(rule("plan-row")).toContain("minmax(0, 1fr)");
  });

  it("AC-27: no fixed or minimum width above 360px, and nothing as wide as the viewport", () => {
    const found: string[] = [];
    for (const m of CSS.matchAll(/(?:^|[\s;{])((?:min-)?(?:width|inline-size))\s*:\s*([^;}]+)/g)) {
      const size = px(m[2]);
      if (size !== null && size > 360) found.push(`${m[1]}: ${m[2]}`);
    }
    expect(found).toEqual([]);
    expect(CSS).not.toMatch(/(?:width|inline-size)\s*:\s*100vw/);
    expect(CSS).not.toContain("translateX"); // nothing animates sideways
  });

  it("AC-27: inputs, selects and textareas are 16px", () => {
    expect(rule("field")).toContain("font-size: 1rem");
    expect(rule("composer-input")).toContain("font-size: 1rem");
  });

  it("AC-28: positions and corners are logical, so they mirror in Arabic", () => {
    expect(rule("badge")).toContain("inset-inline-end");
    expect(rule("jump")).toContain("inset-inline-end: 0");
    expect(rule("jump-new")).toContain("inset-inline-end");
    expect(rule("bubble-mine")).toContain("border-end-end-radius");
    expect(rule("bubble-ahmad")).toContain("border-end-start-radius");
    expect(rule("skip-link")).toContain("inset-inline-start");
    expect(CSS).toContain('[dir="rtl"] .icon-mirror { transform: scaleX(-1); }');
    // Physical sides appear once only, on purpose: the safe-area insets on the page frame (UI.md section 5, rule 6).
    const physical = CSS.split("\n").filter((line) => /(margin|padding)-(left|right)|(^|[\s;{])(left|right)\s*:|text-align:\s*(left|right)/.test(line));
    expect(physical).toHaveLength(1);
    expect(physical[0]).toContain(".gutter {");
    expect(physical[0]).toContain("env(safe-area-inset-left)");
  });

  /**
   * Spacing that keeps a page off the orb lives in a named rule, not in an arbitrary pb-[…] class.
   * An arbitrary class only exists if Tailwind's scanner emitted it, and nothing in this suite can
   * see whether it did: jsdom applies no stylesheet, so a class that generates no CSS still reads
   * back from className. A named rule is in globals.css, where `rule()` can read it. The three
   * arbitrary values with a CSS function inside are the ones already measured in a browser
   * (MEASUREMENTS_ui_inbox.md); a new one must be a named rule here instead, or be measured and
   * added to this list on purpose. The real proof of the clearance is still a browser measurement.
   */
  it("AC-12/AC-27: the orb clearance is a named rule, and no new arbitrary class hides a CSS function", () => {
    expect(rule("orb-clear")).toContain("padding-block-end: calc(9rem + env(safe-area-inset-bottom))");
    const today = readFileSync(resolve(process.cwd(), "src/app/(app)/today/TodayView.tsx"), "utf8");
    expect(today).toContain('className="orb-clear pt-4"');
    expect(today).not.toMatch(/pb-\[/);

    const MEASURED = ["pb-[max(env(safe-area-inset-bottom),12px)]", "w-[calc(100%+1rem)]"];
    const files = readdirSync(resolve(process.cwd(), "src"), { recursive: true, encoding: "utf8" })
      .filter((name) => name.endsWith(".tsx") || name.endsWith(".ts"));
    const found = new Set<string>();
    for (const name of files) {
      const source = readFileSync(resolve(process.cwd(), "src", name), "utf8");
      for (const m of source.matchAll(/class[A-Za-z]*=["'`]([^"'`]*)["'`]/g)) {
        for (const token of m[1].split(/\s+/).filter(Boolean)) {
          if (/-\[[^\]]*\w\(/.test(token) && !MEASURED.includes(token)) found.add(`${name}: ${token}`);
        }
      }
    }
    expect([...found]).toEqual([]);
  });

  it("AC-25/A10: the page may be pinch-zoomed (no maximum-scale, no user-scalable=no)", () => {
    const layout = readFileSync(resolve(process.cwd(), "src/app/layout.tsx"), "utf8");
    expect(layout).not.toMatch(/maximumScale|userScalable|maximum-scale|user-scalable/);
    expect(layout).toContain('viewportFit: "cover"');
  });
});

describe.each([360, 390])("structural guards at %ipx", (width) => {
  const gutter = width >= 390 ? 20 : 16;

  describe.each(["en", "ar"] as const)("in %s", (lang) => {
    it.each(Object.keys(PAGES))("%s: outside text wraps or is cut, and its flex and grid parents can shrink (AC-26)", async (page) => {
      const { container } = await draw(page, lang);
      const slots = [...container.querySelectorAll<HTMLElement>("[data-slot]")];
      for (const name of PAGES[page].slots) {
        expect(slots.filter((s) => s.dataset.slot === name).length, `${page} has a ${name} slot`).toBeGreaterThan(0);
      }
      const long = slots.filter((s) => (s.textContent ?? "").includes(LONG.slice(0, 80)) || (s.textContent ?? "").includes("https://example.com/"));
      expect(long.length).toBeGreaterThanOrEqual(PAGES[page].slots.length);
      for (const slot of long) {
        const where = `${page}/${lang}/${slot.dataset.slot}`;
        expect(tokens(slot).some((t) => TEXT_GUARDS.includes(t)), `${where} wraps or truncates`).toBe(true);
        for (let el: HTMLElement = slot; el.parentElement && el !== container; el = el.parentElement) {
          const parent = el.parentElement;
          if (isRowFlex(parent)) expect(tokens(el).some((t) => MIN_ZERO.includes(t)), `${where}: <${el.tagName.toLowerCase()} class="${el.className}"> in a flex row has min-width: 0`).toBe(true);
          const template = gridTemplate(parent);
          if (template || tokens(parent).includes("grid")) {
            expect(template, `${where}: grid text column is minmax(0, 1fr)`).toMatch(/minmax\(0(px)?, 1fr\)/);
            expect(template.replace(/minmax\(0(px)?, 1fr\)/g, ""), `${where}: no bare 1fr`).not.toContain("1fr");
          }
        }
      }
    });

    it.each(Object.keys(PAGES))("%s: no fixed or minimum width above the screen, inputs are 16px, and nothing is physical (AC-27, AC-28)", async (page) => {
      const { container } = await draw(page, lang);
      const all = [...container.querySelectorAll<HTMLElement>("*")];
      for (const el of all) {
        // Inline styles.
        for (const prop of ["width", "minWidth", "inlineSize", "minInlineSize"] as const) {
          const size = px(el.style[prop] ?? "");
          if (size !== null) expect(size, `${page}: inline ${prop} on <${el.tagName.toLowerCase()}>`).toBeLessThanOrEqual(Math.min(360, width - 2 * gutter));
        }
        for (const t of tokens(el)) {
          // Tailwind width classes: w-11 is 44px; w-[…] and min-w-[…] may only be relative.
          const step = /^(?:min-)?w-(\d+(?:\.\d+)?)$/.exec(t);
          if (step) expect(Number(step[1]) * 4, `${page}: ${t}`).toBeLessThanOrEqual(360);
          const free = /^(?:min-)?w-\[(.+)\]$/.exec(t);
          if (free) expect(px(free[1].replace(/_/g, " ")) ?? 0, `${page}: ${t}`).toBeLessThanOrEqual(360);
          expect(t, `${page}: physical class on <${el.tagName.toLowerCase()}>`).not.toMatch(
            /^-?(ml|mr|pl|pr|left|right|rounded-[lr]|rounded-[tb][lr]|border-[lr]|scroll-m[lr]|scroll-p[lr])-|^text-(left|right)$|^float-|^(left|right)-/);
          expect(t, `${page}: text under 13px`).not.toMatch(/^text-(xs|\[1[0-2]px\]|\[0?\.[0-7]\d*rem\])$/);
          expect(t, `${page}: uppercase or mono`).not.toMatch(/^(uppercase|font-mono)$/);
        }
      }
      const fields = [...container.querySelectorAll<HTMLElement>("input, select, textarea")];
      for (const field of fields) {
        const where = `${page}: <${field.tagName.toLowerCase()} id="${field.id}">`;
        expect(tokens(field).some((t) => t === "field" || t === "composer-input"), `${where} is 16px`).toBe(true);
        expect(tokens(field).some((t) => /^text-(xs|sm)$/.test(t)), `${where} has no smaller text class`).toBe(false);
      }
      if (page !== "Today" && page !== "Inbox") expect(fields.length).toBeGreaterThan(0);
      // The widest fixed things on any page are the menu popover and the plan's first column.
      expect(Math.min(18 * PX_PER_REM, width - 2 * gutter)).toBeLessThanOrEqual(width - 2 * gutter);
      const panel = container.querySelector<HTMLElement>("[role='dialog']")!;
      expect(panel.getAttribute("style")).toContain("min(18rem, calc(100vw - 2 * var(--gutter)))");
      expect(within(panel).getByTestId("menu-status").className).toContain("wrap");
    });
  });

  it("AC-28: in Arabic the page is right-to-left, and the bell, badge, unread mark and jump button are placed by logical rules", async () => {
    expect(direction("ar")).toBe("rtl");
    const inbox = await draw("Inbox", "ar");
    expect(document.documentElement.dir).toBe("rtl");
    const header = inbox.container.querySelector("header")!;
    // DOM order is the reading order: start group, then the bell, then the menu (outermost). RTL mirrors it.
    const bell = within(header).getByTestId("bell");
    const menu = within(header).getByTestId("menu-button");
    expect(within(header).getByTestId("back").compareDocumentPosition(bell) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(bell.compareDocumentPosition(menu) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(bell).getByTestId("bell-badge").className).toBe("badge");
    expect(within(bell).getByTestId("bell-badge")).toHaveAttribute("dir", "ltr"); // "9+" never becomes "+9"
    expect(within(header).getByTestId("back").querySelector("svg")!.getAttribute("class")).toContain("icon-mirror");
    // The unread mark is the first cell of the row's grid: on the right in Arabic.
    const row = inbox.container.querySelector("[data-testid='inbox-row'][data-kind='brief']")!;
    expect(row.querySelector("button")!.firstElementChild!.tagName).toBe("SPAN");
    inbox.unmount();
    const chat = await draw("Chat", "ar");
    const list = within(chat.container).getByTestId("chat-list");
    vi.spyOn(list, "scrollHeight", "get").mockReturnValue(2000);
    vi.spyOn(list, "clientHeight", "get").mockReturnValue(500);
    await act(async () => { list.scrollTop = 100; fireEvent.scroll(list); });
    expect(within(chat.container).getByTestId("jump-latest").className).toContain("jump");
  });
});
