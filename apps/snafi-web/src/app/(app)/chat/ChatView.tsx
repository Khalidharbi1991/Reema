"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ActionEntry, ApprovalCard as Card, MailboxMessage } from "@/adapters/mailbox/types";
import { ApprovalCard } from "@/components/ApprovalCard";
import { ArrowDownIcon } from "@/components/Icons";
import { useShell } from "@/components/ShellState";
import { UndoButton } from "@/components/UndoButton";
import { isAtBottom, onNewItem, prefersReducedMotion, scrollBehavior, scrollToEnd } from "@/core/chat-scroll";
import { messages as dict, type Lang } from "@/i18n/messages";
import { ChatComposer } from "./ChatComposer";

type Props = {
  lang: Lang;
  messages: MailboxMessage[];
  cards: Record<string, Card>;
  actions: Record<string, ActionEntry>;
  preview: boolean;
  decide: (id: string, decision: "approved" | "rejected", argsHash: string) => Promise<{ ok: boolean; status?: string }>;
  undo: (id: string) => Promise<{ ok: boolean }>;
  send: Parameters<typeof ChatComposer>[0]["send"];
};

/**
 * The chat with Ahmad: messages, approval cards with Approve / Reject, and Undo on logged actions.
 * The message list is the only thing that scrolls. It opens at the latest message and follows new
 * items while Khalid is at the bottom; when he has scrolled up, it stays where he is and shows a
 * "jump to latest" button (AC-20 to AC-24).
 */
export function ChatView({ lang, messages, cards, actions, preview, decide, undo, send }: Props) {
  const t = dict(lang);
  const last = messages[messages.length - 1];
  const waiting = !!last && last.role === "user";
  const mine = waiting;
  /** Changes whenever a new item is at the end: a message, an approval card or the thinking bubble. */
  const lastKey = `${last?.id ?? ""}:${waiting}`;

  const list = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLOListElement>(null);
  const pinned = useRef(true);
  const seen = useRef(lastKey);
  const [away, setAway] = useState(false);
  /** The last item when Khalid scrolled away: anything newer from Ahmad shows the "new" mark. */
  const [awayKey, setAwayKey] = useState(lastKey);
  const fresh = away && lastKey !== awayKey && !mine;

  const { setThinking } = useShell();
  useEffect(() => {
    setThinking(waiting);
    return () => setThinking(false);
  }, [waiting, setThinking]);

  // Chat opens at the latest message, before the first paint, with no animation.
  useLayoutEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  }, []);

  // A new item: follow it when at the bottom or when it is Khalid's own; otherwise hold still.
  // The 3-second refresh brings the same last item, so it never moves the list.
  useEffect(() => {
    if (seen.current === lastKey) return;
    seen.current = lastKey;
    const el = list.current;
    if (el && onNewItem({ atBottom: pinned.current, mine }) === "scroll") {
      pinned.current = true;
      scrollToEnd(el, scrollBehavior(prefersReducedMotion()));
    }
  }, [lastKey, mine]);

  // At the bottom, stay there when the content grows (a font loads, a long reply wraps).
  useEffect(() => {
    const el = list.current;
    if (!el || !content.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (pinned.current) el.scrollTop = el.scrollHeight;
    });
    observer.observe(content.current);
    return () => observer.disconnect();
  }, []);

  const onScroll = () => {
    const el = list.current;
    if (!el) return;
    const bottom = isAtBottom(el);
    if (!bottom && pinned.current) setAwayKey(lastKey);
    pinned.current = bottom;
    setAway(!bottom);
  };

  const jump = () => {
    const el = list.current;
    if (!el) return;
    pinned.current = true; // auto-scroll is on again
    setAway(false);
    scrollToEnd(el, scrollBehavior(prefersReducedMotion()));
    el.focus({ preventScroll: true }); // not the text field: the keyboard must not open
  };

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col" data-screen="chat">
      <div ref={list} role="log" aria-label={t.chatTitle} tabIndex={-1} onScroll={onScroll} className="chat-list py-4" data-testid="chat-list">
        {messages.length === 0 && <p className="t-small text-center text-muted">{t.chat.empty}</p>}
        <ol ref={content} className="space-y-4">
          {messages.map((m) => {
            const own = m.role === "user";
            const card = m.approvalId ? cards[m.approvalId] : undefined;
            const logged = (m.meta.actions ?? []).map((id) => actions[id]).filter(Boolean);
            return (
              <li key={m.id} className={`flex min-w-0 flex-col ${own ? "items-end" : "items-start"}`}>
                {card ? (
                  <div className="w-full min-w-0"><ApprovalCard card={card} decide={decide} lang={lang} /></div>
                ) : (
                  <div lang={m.lang} dir={m.lang === "ar" ? "rtl" : "ltr"} data-slot="chat-message"
                    className={`bubble ${own ? "bubble-mine" : "bubble-ahmad"}`}>
                    {m.body}
                  </div>
                )}
                {logged.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {logged.map((a) => (
                      <UndoButton key={a.id} action={a} undo={undo}
                        labels={{ undo: t.undo, undoing: t.undoing, undone: t.undone }} />
                    ))}
                  </div>
                )}
              </li>
            );
          })}
          {waiting && (
            <li className="flex justify-start">
              <div className="skeleton h-11 w-40 rounded-2xl"><span className="sr-only">{t.thinking}</span></div>
            </li>
          )}
        </ol>
      </div>

      <ChatComposer send={send} labels={{ placeholder: t.messagePlaceholder, send: t.send, failed: t.sendFailed }}
        note={preview ? t.chatPreview : ""}
        jump={away && (
          <button type="button" onClick={jump} aria-label={fresh ? t.chat.jumpNew : t.chat.jump} data-testid="jump-latest"
            data-new={fresh ? "true" : undefined} className="icon-btn jump">
            <ArrowDownIcon />
            {fresh && <span className="jump-new" aria-hidden="true" />}
          </button>
        )} />
    </div>
  );
}
