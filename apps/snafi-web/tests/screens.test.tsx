import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApprovalCard } from "@/components/ApprovalCard";
import { UndoButton } from "@/components/UndoButton";
import { Menu } from "@/components/Menu";
import { PrayerRing } from "@/components/PrayerRing";
import { ChatView } from "@/app/(app)/chat/ChatView";
import { TodayView } from "@/app/(app)/today/TodayView";
import { PlaceholderTodaySource } from "@/adapters/today/placeholder";
import { messages } from "@/i18n/messages";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const labels = (lang: "en" | "ar") => {
  const t = messages(lang);
  return { menu: t.menu, closeMenu: t.closeMenu, theme: t.theme, dark: t.dark, light: t.light, language: t.language, signOut: t.signOut };
};

const CARD = { id: "c1", conversationId: "x", tool: "send_test_message", args: { text: "Site visit at 4 — الساعة ٤" },
  argsHash: "a".repeat(64), summary: "Test send: hello", status: "pending" as const, createdAt: "", expiresAt: "2999-01-01T00:00:00Z" };
const decide = vi.fn(async () => ({ ok: true }));
const undo = vi.fn(async () => ({ ok: true }));
const send = vi.fn(async () => ({ error: false, sentAt: 1 }));

async function today(lang: "en" | "ar", withCard = true) {
  const snapshot = await new PlaceholderTodaySource().getToday(lang, new Date("2026-11-07T15:00:00Z"));
  return { ...snapshot, approvals: withCard ? [CARD] : [] };
}

describe("Today screen", () => {
  it("shows the greeting, prayer ring, sample badges and the orb link (English)", async () => {
    render(<TodayView lang="en" hour={19} today={await today("en")} decide={decide} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Good evening, Khalid");
    expect(screen.getByRole("img", { name: /Next prayer Asr at 15:12, 62%/ })).toBeInTheDocument();
    // event, tasks and Ahmad's cards are still samples; approvals are real since step 2
    expect(screen.getAllByText("Sample")).toHaveLength(3);
    expect(screen.getByRole("link", { name: "Talk to Ahmad" })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("renders in Arabic", async () => {
    render(<TodayView lang="ar" hour={8} today={await today("ar")} decide={decide} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("صباح الخير، خالد");
    expect(screen.getByRole("link", { name: "تحدّث مع أحمد" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "موافقة" })).toBeInTheDocument();
  });

  it("says when nothing waits for approval", async () => {
    render(<TodayView lang="en" hour={9} today={await today("en", false)} decide={decide} />);
    expect(screen.getByText("Nothing is waiting for your approval.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });
});

const cardLabels = { approve: "Approve", reject: "Reject", status: messages("en").cardStatus, failed: "That didn't go through.",
  exactly: "Exactly what will run", expires: messages("en").expires };

describe("approval cards", () => {
  it("send the decision with tap feedback, then show the result instead of buttons", async () => {
    const vibrate = vi.fn(() => true);
    vi.stubGlobal("navigator", { ...navigator, vibrate });
    render(<ApprovalCard card={CARD} labels={cardLabels} decide={decide} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Approve" })); });
    expect(decide).toHaveBeenCalledWith("c1", "approved", "a".repeat(64));
    expect(vibrate).toHaveBeenCalledWith(12);
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.getByText("Approved, running…")).toBeInTheDocument();
    vi.unstubAllGlobals();
    vi.stubGlobal("fetch", () => { throw new Error("Network access is forbidden in Snafi tests"); });
  });

  it("keep the buttons and say so when the decision fails", async () => {
    const failing = vi.fn(async () => ({ ok: false }));
    render(<ApprovalCard card={CARD} labels={cardLabels} decide={failing} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Reject" })); });
    expect(failing).toHaveBeenCalledWith("c1", "rejected", "a".repeat(64));
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("didn't go through");
  });

  it("show the final state with no buttons once decided", () => {
    render(<ApprovalCard card={{ ...CARD, status: "executed" }} labels={cardLabels} decide={decide} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });
});

describe("Undo", () => {
  const labels = { undo: "Undo", undoing: "Undoing…", undone: "Undone" };
  const entry = { id: "a1", summary: "Saved a note", level: 2, status: "done" as const, undoable: true, undoRequested: false };

  it("appears only for undoable actions and asks once", async () => {
    const { rerender } = render(<UndoButton action={entry} labels={labels} undo={undo} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Undo" })); });
    expect(undo).toHaveBeenCalledWith("a1");
    expect(screen.getByText("Undoing…")).toBeInTheDocument();
    rerender(<UndoButton action={{ ...entry, id: "a2", undoable: false }} labels={labels} undo={undo} />);
    expect(screen.queryByRole("button")).toBeNull();
    rerender(<UndoButton action={{ ...entry, id: "a3", status: "undone" }} labels={labels} undo={undo} />);
    expect(screen.getByText("Undone")).toBeInTheDocument();
  });
});

describe("prayer ring", () => {
  it("clamps progress and fills the ring", () => {
    const { rerender } = render(<PrayerRing name="Asr" time="15:12" progress={0.5} label="l" size={100} />);
    const ring = screen.getByTestId("prayer-progress");
    const c = Number(ring.getAttribute("stroke-dasharray"));
    expect(Number(ring.getAttribute("stroke-dashoffset"))).toBeCloseTo(c / 2);
    rerender(<PrayerRing name="Asr" time="15:12" progress={7} label="l" size={100} />);
    expect(Number(screen.getByTestId("prayer-progress").getAttribute("stroke-dashoffset"))).toBeCloseTo(0);
    rerender(<PrayerRing name="Asr" time="15:12" progress={Number.NaN} label="l" size={100} />);
    expect(Number(screen.getByTestId("prayer-progress").getAttribute("stroke-dashoffset"))).toBeCloseTo(c);
  });
});

const msg = (over: Record<string, unknown>) => ({
  id: crypto.randomUUID(), userId: "u", conversationId: "x", role: "assistant", body: "", lang: "en",
  jobId: null, approvalId: null, meta: {}, createdAt: "", ...over,
}) as import("@/adapters/mailbox/types").MailboxMessage;

describe("chat screen", () => {
  it("shows the conversation, an approval card and Undo on a logged action", () => {
    const messages_ = [
      msg({ role: "user", body: "note: drawings" }),
      msg({ body: "Sure.\n\nSaved a note: drawings", meta: { actions: ["a1"] } }),
      msg({ body: "Test send", approvalId: "c1", meta: { kind: "approval_card" } }),
    ];
    render(<ChatView lang="en" messages={messages_} preview={false} decide={decide} undo={undo} send={send}
      cards={{ c1: CARD }}
      actions={{ a1: { id: "a1", summary: "Saved a note", level: 2, status: "done", undoable: true, undoRequested: false } }} />);
    expect(screen.getByText(/Saved a note: drawings/)).toBeInTheDocument();
    expect(screen.getByTestId("approval-card")).toHaveTextContent("Test send: hello");
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("shows Ahmad thinking while the last message is Khalid's, in Arabic right to left", () => {
    render(<ChatView lang="ar" messages={[msg({ role: "user", body: "مرحبا", lang: "ar" })]} preview={false}
      decide={decide} undo={undo} send={send} cards={{}} actions={{}} />);
    expect(screen.getByText("أحمد يفكّر…")).toBeInTheDocument();
    expect(screen.getByText("مرحبا")).toHaveAttribute("dir", "rtl");
  });

  it("says when it is only a preview", () => {
    render(<ChatView lang="en" messages={[]} preview decide={decide} undo={undo} send={send} cards={{}} actions={{}} />);
    expect(screen.getByText(/Preview mode: messages stay on this PC/)).toBeInTheDocument();
  });
});

describe("menu", () => {
  beforeEach(() => {
    document.documentElement.dataset.theme = "dark";
    document.documentElement.lang = "en";
    document.documentElement.dir = "ltr";
    document.cookie = "snafi-theme=; Max-Age=0; Path=/";
    document.cookie = "snafi-lang=; Max-Age=0; Path=/";
    refresh.mockClear();
  });

  it("opens, switches to light, and closes with Escape", () => {
    render(<Menu labels={labels("en")} theme="dark" lang="en" />);
    const button = screen.getByRole("button", { name: "Menu" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: "Light" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.cookie).toContain("snafi-theme=light");
    expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("switches to Arabic with right-to-left layout", () => {
    render(<Menu labels={labels("en")} theme="dark" lang="en" />);
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
    expect(document.cookie).toContain("snafi-lang=ar");
    expect(refresh).toHaveBeenCalled();
  });

  it("offers sign-out when signed in", () => {
    render(<Menu labels={labels("ar")} theme="light" lang="ar" signOutAction={async () => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "القائمة" }));
    expect(screen.getByRole("button", { name: "تسجيل الخروج" })).toBeInTheDocument();
  });
});
