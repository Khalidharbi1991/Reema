import Link from "next/link";
import type { ActionEntry, ApprovalCard as Card, MailboxMessage } from "@/adapters/mailbox/types";
import { ApprovalCard } from "@/components/ApprovalCard";
import { Orb } from "@/components/Orb";
import { UndoButton } from "@/components/UndoButton";
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

/** The chat with Ahmad: messages, approval cards with Approve / Reject, and Undo on logged actions. */
export function ChatView({ lang, messages, cards, actions, preview, decide, undo, send }: Props) {
  const t = dict(lang);
  const waiting = messages.length > 0 && messages[messages.length - 1].role === "user";
  const cardLabels = { approve: t.approve, reject: t.reject, status: t.cardStatus, failed: t.decideFailed, exactly: t.exactly, expires: t.expires };
  return (
    <div className="flex min-h-[calc(100dvh-6rem)] flex-col">
      <div className="flex items-center gap-3 py-3">
        <Link href="/today" aria-label={t.back} className="flex h-11 w-11 items-center justify-center rounded-full text-xl text-muted">
          <span aria-hidden="true" className="rtl:rotate-180">←</span>
        </Link>
        <Orb label={t.chatTitle} size={36} state={waiting ? "thinking" : "idle"} />
        <div className="flex-1">
          <h1 className="text-xl leading-none">{t.chatTitle}</h1>
          <p className="text-xs text-muted">{waiting ? t.thinking : t.chatSubtitle}</p>
        </div>
      </div>

      <ol className="flex-1 space-y-4 py-4" aria-label={t.chatTitle} aria-live="polite">
        {messages.map((m, i) => {
          const mine = m.role === "user";
          const card = m.approvalId ? cards[m.approvalId] : undefined;
          const logged = (m.meta.actions ?? []).map((id) => actions[id]).filter(Boolean);
          return (
            <li key={m.id} className={`rise-in flex flex-col ${mine ? "items-end" : "items-start"}`}
              style={{ ["--i" as string]: Math.min(i, 6) }}>
              {card ? (
                <div className="w-full max-w-[85%]"><ApprovalCard card={card} labels={cardLabels} decide={decide} /></div>
              ) : (
                <div lang={m.lang} dir={m.lang === "ar" ? "rtl" : "ltr"}
                  className={`max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-3 text-sm ${
                    mine ? "rounded-se-md bg-gold/15" : "rounded-ss-md border border-edge bg-card"}`}>
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
          <li className="flex justify-start" aria-label={t.thinking}>
            <div className="skeleton h-10 w-40 rounded-2xl" />
          </li>
        )}
      </ol>

      <ChatComposer send={send} labels={{ placeholder: t.messagePlaceholder, send: t.send, attach: t.attach, failed: t.sendFailed }}
        note={preview ? t.chatPreview : ""} />
    </div>
  );
}
