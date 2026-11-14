/** SEC-13 in the app: the card shows exactly what will run, binds Approve to it, and expires. */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createMemoryStore, MemoryMailboxAdapter } from "@/adapters/mailbox/memory";
import { effectiveStatus, type ApprovalCard as Card } from "@/adapters/mailbox/types";
import { ApprovalCard } from "@/components/ApprovalCard";
import { messages } from "@/i18n/messages";

const A = "11111111-1111-4111-8111-111111111111";
const ID = "22222222-2222-4222-8222-222222222222";
const HASH = "d".repeat(64);
const t = messages("en");
const labels = { approve: t.approve, reject: t.reject, status: t.cardStatus, failed: t.decideFailed, exactly: t.exactly, expires: t.expires };
const NOW = new Date("2026-11-09T10:00:00Z");

function card(over: Partial<Card> = {}): Card {
  return {
    id: ID, conversationId: A, tool: "send_test_message",
    args: { text: "Tell the architect: site visit moved to 16:30. لا تنسَ المخططات.", copies: 2 },
    argsHash: HASH, summary: "Test send (nothing leaves this PC): Tell the architect…", status: "pending",
    createdAt: "2026-11-09T09:00:00Z", expiresAt: "2026-11-10T09:00:00Z", ...over,
  };
}

describe("approval card shows exactly what will run", () => {
  it("lists the action and every argument in full, not the short summary", () => {
    render(<ApprovalCard card={card()} labels={labels} decide={vi.fn()} now={NOW} />);
    const args = screen.getByTestId("approval-args");
    expect(args).toHaveTextContent("send_test_message");
    expect(args).toHaveTextContent("Tell the architect: site visit moved to 16:30. لا تنسَ المخططات.");
    expect(args).toHaveTextContent("copies2");
    expect(screen.getByText(/Expires 10 Nov, 12:00 PM if not decided/)).toBeInTheDocument();
  });

  it("sends the arguments' hash with Approve", async () => {
    const decide = vi.fn(async () => ({ ok: true, status: "approved" }));
    render(<ApprovalCard card={card()} labels={labels} decide={decide} now={NOW} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Approve" })); });
    expect(decide).toHaveBeenCalledWith(ID, "approved", HASH);
  });

  it("shows expired, with no buttons, once the time has passed", () => {
    render(<ApprovalCard card={card()} labels={labels} decide={vi.fn()} now={new Date("2026-11-10T09:00:01Z")} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Expired")).toBeInTheDocument();
  });

  it("shows when the server answered that it had expired", async () => {
    const decide = vi.fn(async () => ({ ok: true, status: "expired" }));
    render(<ApprovalCard card={card()} labels={labels} decide={decide} now={NOW} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Approve" })); });
    expect(screen.getByText("Expired")).toBeInTheDocument();
  });

  it("explains a card stuck in executing and offers no buttons", () => {
    render(<ApprovalCard card={card({ status: "executing" })} labels={labels} decide={vi.fn()} now={NOW} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/it will not run again/)).toBeInTheDocument();
  });

  it("works out the shown status", () => {
    expect(effectiveStatus(card(), NOW)).toBe("pending");
    expect(effectiveStatus(card(), new Date("2026-11-11T00:00:00Z"))).toBe("expired");
    expect(effectiveStatus(card({ status: "executed" }), new Date("2026-11-11T00:00:00Z"))).toBe("executed");
  });
});

describe("mailbox expiry", () => {
  it("does not list or approve an expired card", async () => {
    const store = createMemoryStore();
    store.approvals.push({ ...card({ expiresAt: "2026-11-09T09:59:00Z" }), userId: A });
    const mailbox = new MemoryMailboxAdapter(store, A, () => NOW);
    expect(await mailbox.pendingApprovals()).toEqual([]);
    expect((await mailbox.decideApproval(ID, "approved", HASH)).status).toBe("expired");
    expect(store.jobs).toEqual([]);
  });
});
