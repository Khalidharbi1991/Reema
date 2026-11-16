/** Snafi UI job, Story 1: the bell, its badge and the Inbox (AC-1 to AC-10; AC-11 is in rls-inbox.test.ts). */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryStore, MemoryMailboxAdapter } from "@/adapters/mailbox/memory";
import { READ_KEEP_MS, toCard, type AhmadCard, type ApprovalCard } from "@/adapters/mailbox/types";
import { InboxView } from "@/app/(app)/inbox/InboxView";
import { Bell } from "@/components/Bell";
import { ShellProvider } from "@/components/ShellState";
import { TopBar } from "@/components/TopBar";
import { badgeText, inboxCards, mailLines, unreadCount, unreadIds } from "@/core/inbox";
import { messages } from "@/i18n/messages";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }), usePathname: () => "/inbox" }));

const NOW = new Date("2026-11-15T13:10:00Z"); // 4:10 PM in Jeddah
const ME = "11111111-1111-4111-8111-111111111111";
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const ago = (ms: number) => new Date(NOW.getTime() - ms).toISOString();
const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;

function card(n: number, over: Partial<AhmadCard> = {}): AhmadCard {
  return { id: id(n), kind: "reminder", title: `Reminder ${n}`, body: `Body of ${n}`, createdAt: ago(n * 60_000), readAt: null, ...over };
}
function approval(n: number, over: Partial<ApprovalCard> = {}): ApprovalCard {
  return { id: id(100 + n), conversationId: ME, tool: "gmail_send", args: { to: "sample@example.com", subject: "Running late" },
    argsHash: "c".repeat(64), summary: `Send email ${n}?`, status: "pending", createdAt: ago(n * 60_000), expiresAt: "2999-01-01T00:00:00Z", ...over };
}

const CARDS = [
  card(1),
  card(2, { kind: "brief", title: "Morning brief", body: "3 events today." }),
  card(3, { kind: "mail", title: "Sample Sender", body: "Re: Tile samples\nBODY TEXT THAT MUST NEVER SHOW" }),
  card(4, { kind: "test", title: "Test notification", body: "push works" }),
  card(5, { title: "Old and read", readAt: ago(2 * DAY) }),
];
const ok = vi.fn(async () => ({ ok: true }));
const decide = vi.fn(async (_id: string, decision: string) => ({ ok: true, status: decision }));

/** The bell and the Inbox together, as the signed-in layout draws them. */
function Screen({ cards = CARDS, approvals = [approval(1)], markRead = ok, open, lang = "en" as "en" | "ar" }:
  { cards?: AhmadCard[]; approvals?: ApprovalCard[]; markRead?: (id: string) => Promise<{ ok: boolean }>; open?: string; lang?: "en" | "ar" }) {
  return (
    <ShellProvider>
      <Bell lang={lang} unreadIds={unreadIds(approvals, cards, NOW)} current />
      <InboxView lang={lang} now={NOW.toISOString()} approvals={approvals} cards={cards} open={open} decide={decide} markRead={markRead} />
    </ShellProvider>
  );
}
const badge = () => screen.queryByTestId("bell-badge")?.textContent ?? null;
const row = (cardId: string) => document.getElementById(`inbox-${cardId}`)!;
const rowButton = (cardId: string) => within(row(cardId)).getByRole("button");

beforeEach(() => {
  ok.mockClear();
  decide.mockClear();
});

describe("AC-1: the bell is on every signed-in screen and not on Sign-in", () => {
  const labels = { menu: "Menu", closeMenu: "Close", theme: "Appearance", dark: "Dark", light: "Light", language: "Language", signOut: "Sign out" };
  it.each(["today", "inbox", "chat", "settings"] as const)("%s has the bell, linking to the Inbox", (name) => {
    render(<TopBar screen={name} unreadIds={[id(1)]} theme="dark" lang="en" labels={labels} />);
    expect(screen.getByTestId("bell")).toHaveAttribute("href", "/inbox");
  });
  it("Sign-in has the menu only", () => {
    render(<TopBar screen="sign-in" theme="dark" lang="en" labels={labels} />);
    expect(screen.queryByTestId("bell")).toBeNull();
    expect(screen.getByRole("button", { name: "Menu" })).toBeInTheDocument();
  });
});

describe("AC-2 (with Q4): the unread count and the badge", () => {
  it("shows nothing at 0, the number for 1 to 9 and 9+ from 10", () => {
    expect(badgeText(0)).toBeNull();
    expect([1, 5, 9].map(badgeText)).toEqual(["1", "5", "9"]);
    expect([10, 11, 250].map(badgeText)).toEqual(["9+", "9+", "9+"]);
  });

  it("counts pending approvals and unread cards, never test cards or read cards", () => {
    expect(unreadCount([approval(1)], CARDS, NOW)).toBe(4); // approval + reminder + brief + mail
    expect(unreadCount([], [card(4, { kind: "test" })], NOW)).toBe(0); // Q4: a test card never counts
    expect(unreadCount([approval(1, { status: "approved" }), approval(2, { expiresAt: ago(1) })], [], NOW)).toBe(0);
  });

  it("draws the badge and says the real number in the label, in both languages", () => {
    const twelve = Array.from({ length: 12 }, (_, i) => id(i));
    const { unmount } = render(<Bell lang="en" unreadIds={twelve} />);
    expect(badge()).toBe("9+");
    expect(screen.getByTestId("bell")).toHaveAccessibleName("Inbox, 12 unread"); // AC-32
    expect(screen.getByTestId("bell-badge")).toHaveAttribute("dir", "ltr");
    unmount();
    const three = render(<Bell lang="ar" unreadIds={twelve.slice(0, 3)} />);
    expect(badge()).toBe("3");
    expect(screen.getByTestId("bell")).toHaveAccessibleName("الوارد، 3 غير مقروءة");
    three.unmount();
    const none = render(<Bell lang="en" unreadIds={[]} />);
    expect(badge()).toBeNull();
    expect(screen.getByTestId("bell")).toHaveAccessibleName("Inbox, no unread items");
    none.unmount();
    render(<Bell lang="en" unreadIds={null} />); // the count could not be read
    expect(badge()).toBeNull();
    expect(screen.getByTestId("bell")).toHaveAccessibleName("Inbox");
  });
});

describe("AC-3: the Inbox list", () => {
  it("lists pending approvals first (oldest first), then cards newest first, each with kind, title, 12-hour time and unread mark", () => {
    render(<Screen approvals={[approval(1), approval(9)]} />);
    const approvals = within(screen.getByTestId("inbox-approvals")).getAllByTestId("approval-card");
    expect(approvals.map((a) => a.textContent)).toEqual([expect.stringContaining("Send email 9?"), expect.stringContaining("Send email 1?")]);
    const rows = screen.getAllByTestId("inbox-row");
    expect(rows.map((r) => r.getAttribute("data-kind"))).toEqual(["reminder", "brief", "mail", "test", "reminder"]);
    expect(rows[0]).toHaveTextContent("Reminder");
    expect(rows[0]).toHaveTextContent("Reminder 1");
    expect(rows[0]).toHaveTextContent("4:09 PM");
    expect(rows[1]).toHaveTextContent("Brief");
    expect(rows[2]).toHaveTextContent("Mail");
    expect(rows[3]).toHaveTextContent("Test");
    expect(rows.map((r) => r.getAttribute("data-unread"))).toEqual(["true", "true", "true", "true", "false"]);
    expect(within(rows[0]).getByTestId("unread-mark")).toBeInTheDocument();
    expect(rows[0]).toHaveTextContent("Unread"); // not by colour alone
    expect(within(rows[4]).queryByTestId("unread-mark")).toBeNull();
    // The approvals section comes before the cards in the page.
    expect(screen.getByTestId("inbox-approvals").compareDocumentPosition(screen.getByTestId("inbox-cards")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows ص/م in Arabic and the day for an earlier day", () => {
    render(<Screen lang="ar" cards={[card(1), card(6, { createdAt: "2026-11-14T18:15:00Z" })]} approvals={[]} />);
    const rows = screen.getAllByTestId("inbox-row");
    expect(rows[0]).toHaveTextContent("4:09 م");
    expect(rows[0]).toHaveTextContent("تذكير");
    expect(rows[1]).toHaveTextContent("9:15 م");
    expect(rows[1].textContent).toMatch(/14/);
  });
});

describe("AC-4: only opening the list marks nothing", () => {
  it("leaves every card unread and the badge unchanged", () => {
    render(<Screen />);
    expect(badge()).toBe("4");
    expect(ok).not.toHaveBeenCalled();
    expect(screen.getAllByTestId("unread-mark")).toHaveLength(4);
    expect(screen.getByTestId("bell-status")).toHaveTextContent(""); // nothing is announced on first load
  });
});

describe("AC-5: tapping a card opens it and marks it read", () => {
  it("shows the body, calls mark-read once, drops the badge by 1 and keeps it read when closed", async () => {
    render(<Screen />);
    expect(screen.queryByText("Body of 1")).toBeNull();
    await act(async () => { fireEvent.click(rowButton(id(1))); });
    expect(screen.getByText("Body of 1")).toBeInTheDocument();
    expect(rowButton(id(1))).toHaveAttribute("aria-expanded", "true");
    expect(ok).toHaveBeenCalledTimes(1);
    expect(ok).toHaveBeenCalledWith(id(1));
    expect(badge()).toBe("3");
    expect(screen.getByTestId("bell-status")).toHaveTextContent("3 unread");
    expect(row(id(1))).toHaveAttribute("data-unread", "false");
    await act(async () => { fireEvent.click(rowButton(id(1))); }); // close
    await act(async () => { fireEvent.click(rowButton(id(1))); }); // open again
    expect(ok).toHaveBeenCalledTimes(1);
    expect(row(id(1))).toHaveAttribute("data-unread", "false");
    expect(badge()).toBe("3");
  });

  it("is still read after a reload: the mailbox keeps the first read time", async () => {
    const store = createMemoryStore();
    store.cards.push({ ...card(1), userId: ME });
    const mailbox = new MemoryMailboxAdapter(store, ME, () => NOW);
    await mailbox.markCardRead(id(1));
    const later = new MemoryMailboxAdapter(store, ME, () => new Date(NOW.getTime() + HOUR));
    await later.markCardRead(id(1));
    const [reloaded] = await later.cards();
    expect(reloaded.readAt).toBe(NOW.toISOString());
    render(<Screen cards={[reloaded]} approvals={[]} />);
    expect(row(id(1))).toHaveAttribute("data-unread", "false");
    expect(badge()).toBeNull();
  });

  it("a test card can be opened and marked read, and never moves the badge (Q4)", async () => {
    render(<Screen />);
    await act(async () => { fireEvent.click(rowButton(id(4))); });
    expect(ok).toHaveBeenCalledWith(id(4));
    expect(row(id(4))).toHaveAttribute("data-unread", "false");
    expect(badge()).toBe("4");
  });

  it("AC-18: arriving with ?open=<id> opens that card, marks it read and clears the address", async () => {
    window.history.replaceState(null, "", `/inbox?open=${id(2)}`);
    await act(async () => { render(<Screen open={id(2)} />); });
    expect(screen.getByText("3 events today.")).toBeInTheDocument();
    expect(ok).toHaveBeenCalledWith(id(2));
    expect(badge()).toBe("3");
    expect(window.location.search).toBe("");
    expect(document.activeElement).toBe(rowButton(id(2)));
  });

  it("an id that is not in the list is ignored", async () => {
    await act(async () => { render(<Screen open="not-a-card" />); });
    expect(ok).not.toHaveBeenCalled();
    expect(badge()).toBe("4");
  });
});

describe("mark-read fails quietly (the live database has no mark_card_read yet)", () => {
  it("keeps the card unread, the badge unchanged and the Inbox working, with no message", async () => {
    const failing = vi.fn(async () => ({ ok: false }));
    render(<Screen markRead={failing} />);
    await act(async () => { fireEvent.click(rowButton(id(1))); });
    expect(failing).toHaveBeenCalledWith(id(1));
    expect(screen.getByText("Body of 1")).toBeInTheDocument(); // still open and readable
    expect(row(id(1))).toHaveAttribute("data-unread", "true");
    expect(badge()).toBe("4");
    expect(screen.queryByRole("alert")).toBeNull();
    await act(async () => { fireEvent.click(rowButton(id(2))); }); // other rows still open
    expect(screen.getByText("3 events today.")).toBeInTheDocument();
  });

  it("is quiet when the call itself throws", async () => {
    const throwing = vi.fn(async () => { throw new Error("function public.mark_card_read(uuid) does not exist"); });
    render(<Screen markRead={throwing} />);
    await act(async () => { fireEvent.click(rowButton(id(1))); });
    expect(row(id(1))).toHaveAttribute("data-unread", "true");
    expect(badge()).toBe("4");
  });

  it("a row from before migration 0009 (no read_at) is an unread card", () => {
    expect(toCard({ id: id(1), kind: "reminder", title: "t", body: "b", created_at: "2026-11-15T10:00:00Z" }).readAt).toBeNull();
  });
});

describe("AC-6: read cards clear after 7 days", () => {
  it("hides a card read more than 7 days ago, shows one read 6 days 23 hours ago, and any unread card", async () => {
    const cards = [
      card(1, { title: "read 7d 1m ago", readAt: ago(READ_KEEP_MS + 60_000) }),
      card(2, { title: "read 6d 23h ago", readAt: ago(6 * DAY + 23 * HOUR) }),
      card(3, { title: "unread for 90 days", createdAt: ago(90 * DAY) }),
    ];
    expect(inboxCards(cards, NOW).map((c) => c.title)).toEqual(["read 6d 23h ago", "unread for 90 days"]);
    const store = createMemoryStore();
    store.cards.push(...cards.map((c) => ({ ...c, userId: ME })));
    const listed = await new MemoryMailboxAdapter(store, ME, () => NOW).cards(100);
    expect(listed.map((c) => c.title)).toEqual(["read 6d 23h ago", "unread for 90 days"]);
    render(<Screen cards={listed} approvals={[]} />);
    expect(screen.queryByText("read 7d 1m ago")).toBeNull();
    expect(screen.getByText("read 6d 23h ago")).toBeInTheDocument();
    expect(screen.getByText("unread for 90 days")).toBeInTheDocument();
    expect(screen.getByText("Read items clear after 7 days.")).toBeInTheDocument();
  });
});

describe("AC-7: approvals in the Inbox", () => {
  it("are always open with the exact arguments, Approve and Reject, and count until decided", async () => {
    render(<Screen cards={[]} approvals={[approval(1)]} />);
    const item = screen.getByTestId("approval-card");
    expect(within(item).getByTestId("approval-args")).toHaveTextContent("gmail_send");
    expect(within(item).getByTestId("approval-args")).toHaveTextContent("sample@example.com");
    expect(within(item).getByTestId("approval-args")).toHaveTextContent("Running late");
    expect(item).toHaveTextContent("Asked 4:09 PM");
    expect(within(item).queryByRole("button", { expanded: true })).toBeNull(); // it cannot be closed
    expect(badge()).toBe("1"); // seeing it does not uncount it
    // AC-31 / SEC-13: Approve carries the hash of exactly the arguments shown.
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Approve" })); });
    expect(decide).toHaveBeenCalledWith(id(101), "approved", "c".repeat(64));
    expect(screen.queryByTestId("approval-card")).toBeNull();
    expect(screen.getByTestId("inbox-decided")).toHaveTextContent("Approved. Ahmad carries on in Chat.");
    expect(screen.getByRole("link", { name: "Open chat" })).toHaveAttribute("href", "/chat");
    expect(badge()).toBeNull();
  });

  it("a rejected approval leaves the Inbox and the badge too", async () => {
    render(<Screen cards={[]} approvals={[approval(1), approval(2)]} />);
    expect(badge()).toBe("2");
    await act(async () => { fireEvent.click(screen.getAllByRole("button", { name: "Reject" })[0]); });
    expect(screen.getByTestId("inbox-decided")).toHaveTextContent("Rejected. Nothing was run.");
    expect(screen.getAllByTestId("approval-card")).toHaveLength(1);
    expect(badge()).toBe("1");
  });

  it("a failed decision keeps the item, the buttons and the count, and says so", async () => {
    decide.mockResolvedValueOnce({ ok: false, status: "" });
    render(<Screen cards={[]} approvals={[approval(1)]} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Approve" })); });
    expect(screen.getByRole("alert")).toHaveTextContent("didn't go through");
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
    expect(badge()).toBe("1");
  });

  it("a pending approval is never cleared by the 7-day rule, and a decided one is not listed after a reload", async () => {
    const store = createMemoryStore();
    store.approvals.push({ ...approval(1, { createdAt: ago(40 * DAY) }), userId: ME }, { ...approval(2, { status: "approved" }), userId: ME });
    const pending = await new MemoryMailboxAdapter(store, ME, () => NOW).pendingApprovals(50);
    expect(pending.map((a) => a.id)).toEqual([id(101)]);
  });
});

describe("AC-8: a mail alert shows the sender and the subject only", () => {
  it("closed or open, and opening still marks it read", async () => {
    expect(mailLines(CARDS[2])).toEqual({ sender: "Sample Sender", subject: "Re: Tile samples" });
    render(<Screen />);
    const mail = row(id(3));
    expect(mail).toHaveTextContent("Sample Sender");
    expect(mail).toHaveTextContent("Re: Tile samples");
    expect(mail).not.toHaveTextContent("BODY TEXT THAT MUST NEVER SHOW");
    await act(async () => { fireEvent.click(rowButton(id(3))); });
    expect(rowButton(id(3))).toHaveAttribute("aria-expanded", "true");
    expect(mail).toHaveTextContent("Re: Tile samples");
    expect(document.body).not.toHaveTextContent("BODY TEXT THAT MUST NEVER SHOW");
    expect(within(mail).queryByRole("link")).toBeNull();
    expect(ok).toHaveBeenCalledWith(id(3));
  });
});

describe("AC-9: the empty state", () => {
  it.each([["en", "Nothing in your inbox."], ["ar", "لا شيء في الوارد."]] as const)("is quiet, in %s", (lang, text) => {
    render(<Screen lang={lang} cards={[]} approvals={[]} />);
    expect(screen.getByTestId("inbox-empty")).toHaveTextContent(text);
    expect(screen.queryByRole("heading")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
    expect(badge()).toBeNull();
  });

  it("says so when the lists could not be read, and offers to try again", () => {
    render(<ShellProvider><InboxView lang="en" now={NOW.toISOString()} approvals={null} cards={null} decide={decide} markRead={ok} /></ShellProvider>);
    expect(screen.getByTestId("inbox-failed")).toHaveTextContent(messages("en").inbox.loadFailed);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(refresh).toHaveBeenCalled();
  });

  it("still shows the approvals when only the cards could not be read", () => {
    render(<ShellProvider><InboxView lang="en" now={NOW.toISOString()} approvals={[approval(1)]} cards={null} decide={decide} markRead={ok} /></ShellProvider>);
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(within(screen.getByTestId("inbox-cards")).getByTestId("inbox-failed")).toBeInTheDocument();
  });
});

describe("AC-10: no Dismiss", () => {
  it("has no Dismiss button in the Inbox, open or closed, in either language", async () => {
    for (const lang of ["en", "ar"] as const) {
      const { unmount } = render(<Screen lang={lang} />);
      await act(async () => { fireEvent.click(rowButton(id(1))); });
      expect(screen.queryByTestId("dismiss-card")).toBeNull();
      expect(screen.queryByRole("button", { name: /dismiss|إخفاء/i })).toBeNull();
      unmount();
    }
  });

  it("does not list a card dismissed before this job", async () => {
    const store = createMemoryStore();
    store.cards.push({ ...card(1), userId: ME, dismissed: true }, { ...card(2), userId: ME });
    expect((await new MemoryMailboxAdapter(store, ME, () => NOW).cards()).map((c) => c.id)).toEqual([id(2)]);
  });
});

describe("AC-32: reachable by keyboard, with names", () => {
  it("rows are real buttons that say open or closed; the bell and back are links", () => {
    render(<Screen />);
    for (const r of screen.getAllByTestId("inbox-row")) {
      const button = within(r).getByRole("button");
      expect(button).toHaveAttribute("aria-expanded", "false");
      expect(document.getElementById(button.getAttribute("aria-controls")!)).not.toBeNull();
      expect(button.className).toContain("min-h-11"); // 44px
    }
    expect(screen.getByTestId("bell").tagName).toBe("A");
    expect(screen.getByTestId("bell")).toHaveAttribute("aria-current", "page");
  });
});
