/**
 * Snafi UI job, Story 3: Chat scroll (AC-20 to AC-24) and reduced motion (AC-33).
 * jsdom has no layout, so the list's scroll metrics (scrollHeight, clientHeight, scrollTop) are
 * set by hand here; how it feels on a real phone is checked in a browser and by Khalid.
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MailboxMessage } from "@/adapters/mailbox/types";
import { ChatView } from "@/app/(app)/chat/ChatView";
import { isAtBottom, NEAR_BOTTOM_PX, onNewItem, scrollBehavior } from "@/core/chat-scroll";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }), usePathname: () => "/chat" }));

let n = 0;
const msg = (role: "user" | "assistant", body: string, over: Partial<MailboxMessage> = {}): MailboxMessage => ({
  id: `m${++n}`, userId: "u", conversationId: "x", role, body, lang: "en", jobId: null, approvalId: null, meta: {}, createdAt: "", ...over,
});
const decide = vi.fn(async () => ({ ok: true }));
const undo = vi.fn(async () => ({ ok: true }));
const send = vi.fn(async () => ({ error: false, sentAt: 1 }));
const view = (messages: MailboxMessage[], cards = {}) => (
  <ChatView lang="en" messages={messages} cards={cards} actions={{}} preview={false} decide={decide} undo={undo} send={send} />
);

/** A list 500px tall holding 2000px of messages; scrollTo is recorded and moves scrollTop like a browser. */
const HEIGHT = 500;
let content = 2000;
let scrollTo: ReturnType<typeof vi.fn>;
let reduced = false;

beforeEach(() => {
  content = 2000;
  reduced = false;
  scrollTo = vi.fn(function (this: HTMLElement, options: { top: number }) { this.scrollTop = Math.min(options.top, content - HEIGHT); });
  vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(() => content);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockImplementation(() => HEIGHT);
  HTMLElement.prototype.scrollTo = scrollTo as unknown as typeof HTMLElement.prototype.scrollTo;
  window.matchMedia = ((query: string) => ({ matches: reduced && query.includes("reduce"), media: query,
    addEventListener: () => {}, removeEventListener: () => {} })) as unknown as typeof window.matchMedia;
});
afterEach(() => {
  vi.restoreAllMocks();
});

const list = () => screen.getByTestId("chat-list");
const jump = () => screen.queryByTestId("jump-latest");
/** Khalid scrolls: the browser moves scrollTop and fires a scroll event. */
const scrollUserTo = (top: number) => act(() => { list().scrollTop = top; fireEvent.scroll(list()); });
const HISTORY = [msg("user", "one"), msg("assistant", "two"), msg("user", "three"), msg("assistant", "four")];

describe("the scroll rules, as pure functions", () => {
  it("at the bottom means within 80px of the end", () => {
    expect(NEAR_BOTTOM_PX).toBe(80);
    expect(isAtBottom({ scrollTop: 1500, scrollHeight: 2000, clientHeight: 500 })).toBe(true);
    expect(isAtBottom({ scrollTop: 1420, scrollHeight: 2000, clientHeight: 500 })).toBe(true);
    expect(isAtBottom({ scrollTop: 1419, scrollHeight: 2000, clientHeight: 500 })).toBe(false);
    expect(isAtBottom({ scrollTop: 0, scrollHeight: 300, clientHeight: 500 })).toBe(true); // everything fits
  });

  it("a new item is followed at the bottom, or when it is Khalid's own; otherwise the list holds still", () => {
    expect(onNewItem({ atBottom: true, mine: false })).toBe("scroll");
    expect(onNewItem({ atBottom: true, mine: true })).toBe("scroll");
    expect(onNewItem({ atBottom: false, mine: true })).toBe("scroll");
    expect(onNewItem({ atBottom: false, mine: false })).toBe("hold");
  });

  it("AC-33: scrolling done by code is instant with reduced motion", () => {
    expect(scrollBehavior(true)).toBe("auto");
    expect(scrollBehavior(false)).toBe("smooth");
  });
});

describe("AC-20: Chat opens at the latest message", () => {
  it("is at the end at once, with no animation and no jump button", () => {
    render(view(HISTORY));
    expect(list().scrollTop).toBe(content);
    expect(scrollTo).not.toHaveBeenCalled(); // set directly: nothing is animated on open
    expect(jump()).toBeNull();
    expect(list()).toHaveAttribute("role", "log");
  });
});

describe("AC-21: at the bottom, any new item is scrolled into view", () => {
  it.each([
    ["Ahmad's reply", () => [...HISTORY, msg("assistant", "five")]],
    ["Khalid's message and the thinking placeholder", () => [...HISTORY, msg("user", "five")]],
    ["an approval card", () => [...HISTORY, msg("assistant", "Send?", { approvalId: "c1" })]],
  ])("%s", (_name, next) => {
    const { rerender } = render(view(HISTORY));
    content = 2300;
    rerender(view(next()));
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(scrollTo).toHaveBeenCalledWith({ top: 2300, behavior: "smooth" });
    expect(jump()).toBeNull();
  });

  it("the 3-second refresh, with nothing new, never moves the list", () => {
    const { rerender } = render(view(HISTORY));
    rerender(view([...HISTORY]));
    rerender(view(HISTORY.map((m) => ({ ...m }))));
    expect(scrollTo).not.toHaveBeenCalled();
  });
});

describe("AC-22: scrolled up, a new item from Ahmad does not move the list", () => {
  it("keeps the position and shows the jump button with its 'new' mark", async () => {
    const { rerender } = render(view(HISTORY));
    await scrollUserTo(400);
    expect(jump()).toHaveAccessibleName("Jump to latest"); // scrolled up, nothing new yet
    expect(jump()).not.toHaveAttribute("data-new");
    content = 2300;
    rerender(view([...HISTORY, msg("assistant", "five")]));
    expect(scrollTo).not.toHaveBeenCalled();
    expect(list().scrollTop).toBe(400);
    expect(jump()).toHaveAccessibleName("Jump to latest, new messages");
    expect(jump()).toHaveAttribute("data-new", "true");
  });
});

describe("AC-23: the jump button", () => {
  it("scrolls to the bottom, hides, and turns auto-scroll back on", async () => {
    const { rerender } = render(view(HISTORY));
    await scrollUserTo(400);
    await act(async () => { fireEvent.click(jump()!); });
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 2000, behavior: "smooth" });
    expect(jump()).toBeNull();
    expect(document.activeElement).toBe(list()); // not the text field: the keyboard stays closed
    content = 2300;
    rerender(view([...HISTORY, msg("assistant", "five")]));
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 2300, behavior: "smooth" }); // auto-scroll is on again
  });

  it("is hidden whenever Khalid is at the bottom, and is not in the page then", async () => {
    render(view(HISTORY));
    await scrollUserTo(400);
    expect(jump()).not.toBeNull();
    await scrollUserTo(1450); // within 80px of the end
    expect(jump()).toBeNull();
  });

  it("AC-32: has a label in both languages, is a real button of 44px, and sits after the list and before the text field", async () => {
    const { unmount } = render(view(HISTORY));
    await scrollUserTo(400);
    expect(jump()!.tagName).toBe("BUTTON");
    expect(jump()!.className).toContain("icon-btn");
    expect(list().compareDocumentPosition(jump()!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(jump()!.compareDocumentPosition(screen.getByRole("textbox")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    unmount();
    render(<ChatView lang="ar" messages={HISTORY} cards={{}} actions={{}} preview={false} decide={decide} undo={undo} send={send} />);
    await scrollUserTo(400);
    expect(jump()).toHaveAccessibleName("الانتقال إلى آخر الرسائل");
  });
});

describe("AC-24: scrolled up, sending a message scrolls to the bottom", () => {
  it("follows Khalid's own message, and shows no 'new' mark for it", async () => {
    const { rerender } = render(view(HISTORY));
    await scrollUserTo(400);
    content = 2300;
    rerender(view([...HISTORY, msg("user", "my new message")]));
    expect(scrollTo).toHaveBeenCalledWith({ top: 2300, behavior: "smooth" });
    expect(list().scrollTop).toBe(1800);
    await act(async () => { fireEvent.scroll(list()); }); // the browser's scroll event after the move
    expect(jump()).toBeNull();
  });
});

describe("AC-33: reduce motion", () => {
  it("scrolls to the latest message without animation, for a new item and for the jump button", async () => {
    reduced = true;
    const { rerender } = render(view(HISTORY));
    content = 2300;
    rerender(view([...HISTORY, msg("assistant", "five")]));
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 2300, behavior: "auto" });
    await scrollUserTo(400);
    await act(async () => { fireEvent.click(jump()!); });
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 2300, behavior: "auto" });
  });
});

describe("the chat's shape", () => {
  it("shows a quiet line when there are no messages, and no attach button", () => {
    render(view([]));
    expect(screen.getByText("Say hello to Ahmad.")).toBeInTheDocument();
    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual(["Send"]);
  });
});
