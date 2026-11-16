"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { AhmadCard, ApprovalCard as Approval } from "@/adapters/mailbox/types";
import { ApprovalCard } from "@/components/ApprovalCard";
import { ChevronDownIcon } from "@/components/Icons";
import { useShell } from "@/components/ShellState";
import { APP_SETTINGS } from "@/config/app";
import { inboxTime, mailLines } from "@/core/inbox";
import { messages, type Lang } from "@/i18n/messages";

type Decide = (id: string, decision: "approved" | "rejected", argsHash: string) => Promise<{ ok: boolean; status?: string }>;
type Props = {
  lang: Lang;
  /** The server's time (ISO), so times read the same on the server and the phone. */
  now: string;
  /** Pending approvals, oldest first; null when they could not be read. */
  approvals: Approval[] | null;
  /** Ahmad's cards, newest first; null when they could not be read. */
  cards: AhmadCard[] | null;
  /** From `/inbox?open=<id>`: the item to open on arrival. An id not in the list is ignored. */
  open?: string;
  decide: Decide;
  /** `reported` means a real failure (not simply a database without mark_card_read yet). */
  markRead: (id: string) => Promise<{ ok: boolean; reported?: boolean }>;
};

const without = (set: ReadonlySet<string>, id: string) => {
  const next = new Set(set);
  next.delete(id);
  return next;
};

/**
 * The Inbox: pending approvals first (always open, with the exact arguments beside Approve and
 * Reject), then Ahmad's cards newest first. A card opens in place and is marked read the first
 * time it is opened; only opening the list marks nothing. There is no Dismiss.
 */
export function InboxView({ lang, now, approvals, cards, open, decide, markRead }: Props) {
  const t = messages(lang);
  const tz = APP_SETTINGS.timeZone;
  const nowDate = new Date(now);
  const router = useRouter();
  const { settle, unsettle } = useShell();
  const arrival = open && cards?.some((c) => c.id === open) ? open : undefined;
  const [opened, setOpened] = useState<ReadonlySet<string>>(() => new Set(arrival ? [arrival] : []));
  /** Cards read on this screen, before the server says so. */
  const [readNow, setReadNow] = useState<ReadonlySet<string>>(() => new Set(arrival ? [arrival] : []));
  const [decided, setDecided] = useState<Record<string, { card: Approval; decision: "approved" | "rejected" }>>({});
  /** A real mark-read failure, said once; the cards stay unread and readable. */
  const [readFailed, setReadFailed] = useState(false);
  /** mark-read is asked once per card on this screen, whatever the answer. */
  const asked = useRef(new Set<string>());

  const sendRead = useCallback((id: string) => {
    if (asked.current.has(id)) return;
    asked.current.add(id);
    settle(id);
    markRead(id).then((r) => r, () => ({ ok: false, reported: false })).then((r) => {
      if (r.ok) return;
      // The unread mark and the badge count come back; the row stays open and readable. Silent
      // when the database simply has no mark_card_read yet; a real failure is said once (SEC-172).
      unsettle(id);
      setReadNow((s) => without(s, id));
      if (r.reported) setReadFailed(true);
    });
  }, [markRead, settle, unsettle]);

  // Arriving from Today's message: bring that item into view, focus it, mark a card read, and
  // take ?open= off the address so a reload does not repeat it.
  const arrived = useRef(false);
  useEffect(() => {
    if (arrived.current || !open) return;
    arrived.current = true;
    const item = document.getElementById(`inbox-${open}`);
    if (item) {
      if (typeof item.scrollIntoView === "function") item.scrollIntoView({ block: "start", behavior: "auto" });
      (item.querySelector<HTMLElement>("button[aria-expanded]") ?? item).focus({ preventScroll: true });
    }
    const card = cards?.find((c) => c.id === open);
    if (card && !card.readAt) sendRead(card.id);
    window.history.replaceState(null, "", "/inbox");
  }, [open, cards, sendRead]);

  const toggle = (card: AhmadCard) => {
    const opening = !opened.has(card.id);
    setOpened((s) => (opening ? new Set(s).add(card.id) : without(s, card.id)));
    if (opening && !card.readAt) {
      setReadNow((s) => new Set(s).add(card.id));
      sendRead(card.id);
    }
  };

  /** The same binding as everywhere: Approve carries the hash of the arguments shown (SEC-13). */
  const decideHere: Decide = async (id, decision, argsHash) => {
    const result = await decide(id, decision, argsHash);
    if (result.ok) {
      settle(id); // decided or expired: it no longer counts in the badge
      const card = approvals?.find((a) => a.id === id);
      const status = result.status ?? decision;
      if (card && (status === "approved" || status === "rejected")) setDecided((d) => ({ ...d, [id]: { card, decision: status } }));
    }
    return result;
  };

  const waiting = [
    ...(approvals ?? []).filter((a) => !decided[a.id]).map((card) => ({ card, decision: null })),
    ...Object.values(decided),
  ].sort((a, b) => a.card.createdAt.localeCompare(b.card.createdAt));
  const list = cards ?? [];
  const failure = (
    <div data-testid="inbox-failed">
      <p className="t-body wrap">{t.inbox.loadFailed}</p>
      <button type="button" className="btn btn-secondary mt-4" onClick={() => router.refresh()}>{t.retry}</button>
    </div>
  );

  if (approvals === null && cards === null) return <div className="pt-12" data-screen="inbox">{failure}</div>;
  if (waiting.length === 0 && list.length === 0 && cards !== null && approvals !== null) {
    return (
      <div className="pt-12" data-screen="inbox" data-testid="inbox-empty">
        <p className="t-body">{t.inbox.emptyTitle}</p>
        <p className="t-small mt-1 text-muted">{t.inbox.emptyBody}</p>
      </div>
    );
  }

  return (
    <div className="pt-4" data-screen="inbox">
      {approvals === null && <div className="mb-6">{failure}</div>}
      {waiting.length > 0 && (
        <section aria-labelledby="inbox-approvals" data-testid="inbox-approvals">
          <h2 id="inbox-approvals" className="t-heading mb-3">{t.approvals}</h2>
          <ul className="space-y-3">
            {waiting.map(({ card, decision }) => decision ? (
              <li key={card.id}>
                <p role="status" className="t-small wrap text-muted" data-testid="inbox-decided">
                  {decision === "approved" ? t.inbox.approved : t.inbox.rejected}{" "}
                  <Link href="/chat" className="inline-flex min-h-11 items-center underline underline-offset-4">{t.inbox.openChat}</Link>
                </p>
              </li>
            ) : (
              <li key={card.id} id={`inbox-${card.id}`} tabIndex={-1} className="scroll-mt-4">
                <ApprovalCard card={card} decide={decideHere} lang={lang} now={nowDate}
                  asked={t.inbox.asked(inboxTime(card.createdAt, lang, nowDate, tz))} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {(list.length > 0 || cards === null) && (
        <section aria-label={t.inbox.notifications} data-testid="inbox-cards">
          {(waiting.length > 0 || cards === null) && <h2 className="t-heading mt-8 mb-1">{t.inbox.notifications}</h2>}
          {cards === null && <div className="mt-3">{failure}</div>}
          {readFailed && <p role="alert" className="t-small mt-3 text-muted" data-testid="inbox-read-failed">{t.decideFailed}</p>}
          <ul className="divide-y divide-edge">
            {list.map((card) => {
              const isOpen = opened.has(card.id);
              const unread = !card.readAt && !readNow.has(card.id);
              const mail = card.kind === "mail" ? mailLines(card) : null;
              const title = unread ? "t-strong" : "t-body";
              return (
                <li key={card.id} id={`inbox-${card.id}`} className="scroll-mt-4" data-testid="inbox-row" data-kind={card.kind}
                  data-unread={unread ? "true" : "false"}>
                  <button type="button" aria-expanded={isOpen} aria-controls={`inbox-body-${card.id}`} onClick={() => toggle(card)}
                    className="row-press -mx-2 grid min-h-11 w-[calc(100%+1rem)] gap-x-2 px-2 py-3 text-start"
                    style={{ gridTemplateColumns: "12px minmax(0, 1fr) auto" }}>
                    <span className="pt-1.5">{unread && <span className="unread-dot" data-testid="unread-mark" />}</span>
                    <span className="min-w-0">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="t-small text-muted">
                          {unread && <span className="sr-only">{t.inbox.unread} </span>}{t.inbox.kind[card.kind]}
                        </span>
                        <span className="t-caption nums flex-none text-muted"><bdi>{inboxTime(card.createdAt, lang, nowDate, tz)}</bdi></span>
                      </span>
                      {mail ? (
                        <>
                          <span className={`${title} block ${isOpen ? "wrap" : "truncate"}`} data-slot="mail-sender"><bdi>{mail.sender}</bdi></span>
                          <span className={`t-small block text-muted ${isOpen ? "wrap" : "truncate"}`} data-slot="mail-subject"><bdi>{mail.subject}</bdi></span>
                        </>
                      ) : (
                        <span className={`${title} wrap ${isOpen ? "block" : "clamp-2"}`} data-slot="card-title"><bdi>{card.title}</bdi></span>
                      )}
                    </span>
                    <span className="chevron self-center" data-open={isOpen}><ChevronDownIcon /></span>
                  </button>
                  {/* A mail row never shows more than its sender and subject, open or not (AC-8). */}
                  <div id={`inbox-body-${card.id}`} hidden={!isOpen || !!mail}>
                    {isOpen && !mail && (
                      <p className="t-body wrap fade-in whitespace-pre-line ps-5 pb-3" dir="auto" data-slot="card-body">{card.body}</p>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          {list.length > 0 && <p className="t-caption mt-4 text-muted">{t.inbox.clearNote}</p>}
        </section>
      )}
    </div>
  );
}
