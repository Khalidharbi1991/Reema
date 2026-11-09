"use client";

import { useState, useTransition } from "react";
import type { ApprovalCard as Card } from "@/adapters/mailbox/types";
import { tapFeedback } from "@/core/haptics";

type Labels = { approve: string; reject: string; status: Record<Card["status"], string>; failed: string };
type Props = {
  card: Card;
  labels: Labels;
  decide: (id: string, decision: "approved" | "rejected") => Promise<{ ok: boolean }>;
};

/** Approve / Reject as plain buttons, never swipes, with light tap feedback. Nothing runs until Approve. */
export function ApprovalCard({ card, labels, decide }: Props) {
  const [pending, start] = useTransition();
  const [failed, setFailed] = useState(false);
  const [local, setLocal] = useState<Card["status"] | null>(null);
  const status = local ?? card.status;

  const choose = (decision: "approved" | "rejected") => {
    tapFeedback();
    setFailed(false);
    start(async () => {
      const result = await decide(card.id, decision);
      if (result.ok) setLocal(decision);
      else setFailed(true);
    });
  };

  return (
    <div className="rounded-2xl border border-gold/40 bg-card p-4" data-testid="approval-card">
      <p className="text-sm">{card.summary}</p>
      {status === "pending" ? (
        <div className="mt-3 flex gap-3">
          <button type="button" disabled={pending} onClick={() => choose("approved")}
            className="min-h-11 flex-1 rounded-xl bg-gold px-4 text-sm font-medium text-[#0E0E10] disabled:opacity-60">
            {labels.approve}
          </button>
          <button type="button" disabled={pending} onClick={() => choose("rejected")}
            className="min-h-11 flex-1 rounded-xl border border-edge px-4 text-sm text-ink disabled:opacity-60">
            {labels.reject}
          </button>
        </div>
      ) : (
        <p className="mt-2 text-xs text-gold-ink" data-status={status}>{labels.status[status]}</p>
      )}
      <p role="status" aria-live="polite" className="mt-1 min-h-4 text-xs text-muted">{failed ? labels.failed : ""}</p>
    </div>
  );
}
