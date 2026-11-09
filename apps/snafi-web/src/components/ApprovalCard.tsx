"use client";

import { useState, useTransition } from "react";
import { effectiveStatus, type ApprovalCard as Card, type ApprovalStatus } from "@/adapters/mailbox/types";
import { APP_SETTINGS } from "@/config/app";
import { tapFeedback } from "@/core/haptics";

type Labels = {
  approve: string;
  reject: string;
  status: Record<ApprovalStatus, string>;
  failed: string;
  exactly: string;
  expires: (time: string) => string;
};
type Props = {
  card: Card;
  labels: Labels;
  decide: (id: string, decision: "approved" | "rejected", argsHash: string) => Promise<{ ok: boolean; status?: string }>;
  now?: Date;
};

function show(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

/**
 * Approve / Reject as plain buttons, never swipes, with light tap feedback. The card shows
 * the exact action and every argument in full (SEC-13), and Approve carries their hash, so
 * the database approves only what was shown. Nothing runs until Approve.
 */
export function ApprovalCard({ card, labels, decide, now = new Date() }: Props) {
  const [pending, start] = useTransition();
  const [failed, setFailed] = useState(false);
  const [local, setLocal] = useState<ApprovalStatus | null>(null);
  const status = local ?? effectiveStatus(card, now);
  const expiry = new Intl.DateTimeFormat("en-GB", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: APP_SETTINGS.timeZone,
  }).format(new Date(card.expiresAt));

  const choose = (decision: "approved" | "rejected") => {
    tapFeedback();
    setFailed(false);
    start(async () => {
      const result = await decide(card.id, decision, card.argsHash);
      if (result.ok) setLocal((result.status as ApprovalStatus | undefined) ?? decision);
      else setFailed(true);
    });
  };

  return (
    <div className="rounded-2xl border border-gold/40 bg-card p-4" data-testid="approval-card">
      <p className="text-sm">{card.summary}</p>
      <div className="mt-3 rounded-xl border border-edge px-3 py-2" data-testid="approval-args">
        <p className="text-[11px] uppercase tracking-[0.12em] text-muted">{labels.exactly}</p>
        <dl className="mt-1 space-y-1 text-xs" dir="auto">
          <div className="flex gap-2"><dt className="text-muted">action</dt><dd className="font-mono break-all">{card.tool}</dd></div>
          {Object.entries(card.args).map(([key, value]) => (
            <div key={key} className="flex gap-2">
              <dt className="shrink-0 text-muted">{key}</dt>
              <dd className="whitespace-pre-wrap break-words">{show(value)}</dd>
            </div>
          ))}
        </dl>
      </div>
      {status === "pending" ? (
        <>
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
          <p className="mt-2 text-[11px] text-muted" dir="ltr">{labels.expires(expiry)}</p>
        </>
      ) : (
        <p className="mt-2 text-xs text-gold-ink" data-status={status}>{labels.status[status]}</p>
      )}
      <p role="status" aria-live="polite" className="mt-1 min-h-4 text-xs text-muted">{failed ? labels.failed : ""}</p>
    </div>
  );
}
