"use client";

import { useState, useTransition } from "react";
import { effectiveStatus, type ApprovalCard as Card, type ApprovalStatus } from "@/adapters/mailbox/types";
import { APP_SETTINGS } from "@/config/app";
import { dayMonthClock } from "@/core/clock";
import { tapFeedback } from "@/core/haptics";
import { messages, type Lang } from "@/i18n/messages";
import { AttentionIcon } from "./Icons";

type Labels = {
  approve: string;
  reject: string;
  status: Record<ApprovalStatus, string>;
  failed: string;
  exactly: string;
  expires: (time: string) => string;
  action?: string;
};
type Props = {
  card: Card;
  /** Defaults to the app's own words in `lang`. */
  labels?: Labels;
  decide: (id: string, decision: "approved" | "rejected", argsHash: string) => Promise<{ ok: boolean; status?: string }>;
  now?: Date;
  lang?: Lang;
  /** Inbox only: "Asked 4:05 PM". */
  asked?: string;
};

function show(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

/**
 * Approve / Reject as plain buttons, never swipes, with light tap feedback. The card shows
 * the exact action and every argument in full (SEC-13), and Approve carries their hash, so
 * the database approves only what was shown. Nothing runs until Approve. The same item is
 * used in the Inbox (always open) and in Chat.
 */
export function ApprovalCard({ card, labels, decide, now = new Date(), lang = "en", asked }: Props) {
  const t = messages(lang);
  const l: Labels = labels ?? { approve: t.approve, reject: t.reject, status: t.cardStatus, failed: t.decideFailed,
    exactly: t.exactly, expires: t.expires, action: t.approval.action };
  const [pending, start] = useTransition();
  const [failed, setFailed] = useState(false);
  const [local, setLocal] = useState<ApprovalStatus | null>(null);
  const status = local ?? effectiveStatus(card, now);
  const expiry = dayMonthClock(new Date(card.expiresAt), lang, APP_SETTINGS.timeZone);

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
    <div className="surface" data-testid="approval-card" aria-busy={pending}>
      <p className="t-body wrap" dir="auto" data-slot="approval-summary">{card.summary}</p>
      {asked && <p className="t-caption nums mt-1 text-muted">{asked}</p>}
      <hr className="hairline my-3" />
      <div data-testid="approval-args">
        <p className="t-small text-muted">{l.exactly}</p>
        <dl className="mt-2 grid gap-x-3 gap-y-1" style={{ gridTemplateColumns: "fit-content(40%) minmax(0, 1fr)" }}>
          <dt className="t-small wrap text-muted">{l.action ?? t.approval.action}</dt>
          <dd className="t-body wrap" dir="auto" data-slot="approval-arg">{card.tool}</dd>
          {Object.entries(card.args).flatMap(([key, value]) => [
            <dt key={`k-${key}`} className="t-small wrap text-muted" dir="ltr">{key}</dt>,
            <dd key={`v-${key}`} className="t-body wrap whitespace-pre-wrap" dir="auto" data-slot="approval-arg">{show(value)}</dd>,
          ])}
        </dl>
      </div>
      <hr className="hairline my-3" />
      {status === "pending" ? (
        <>
          <div className="flex gap-3">
            <button type="button" disabled={pending} onClick={() => choose("approved")} className="btn btn-primary btn-tall flex-1">
              {l.approve}
            </button>
            <button type="button" disabled={pending} onClick={() => choose("rejected")} className="btn btn-secondary btn-tall flex-1">
              {l.reject}
            </button>
          </div>
          <p className="t-caption wrap mt-2 text-muted"><bdi>{l.expires(expiry)}</bdi></p>
        </>
      ) : (
        <p className="t-small text-muted" data-status={status}>{l.status[status]}</p>
      )}
      {failed && (
        <p role="alert" className="t-small with-icon mt-2 text-danger"><AttentionIcon /><span className="wrap">{l.failed}</span></p>
      )}
    </div>
  );
}
