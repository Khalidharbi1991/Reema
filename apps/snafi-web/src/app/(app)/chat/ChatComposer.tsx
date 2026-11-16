"use client";

import { startTransition, useActionState, useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import type { ChatState } from "../actions";

type Props = {
  send: (prev: ChatState, form: FormData) => Promise<ChatState>;
  labels: { placeholder: string; send: string; failed: string };
  note: string;
  /** The "jump to latest" button, placed 12px above the composer (after the list, before the text field). */
  jump?: ReactNode;
};

const noSubscribe = () => () => {};

/** Text only; attachments (and their button) arrive with a later step. */
export function ChatComposer({ send, labels, note, jump }: Props) {
  const [state, action, pending] = useActionState(send, { error: false, sentAt: 0 });
  const form = useRef<HTMLFormElement>(null);
  // SEC-73: Send stays off until the page has loaded, so a native submit can never
  // put the message in a URL; method="post" is a second guard.
  const ready = useSyncExternalStore(noSubscribe, () => true, () => false);
  // The failure note belongs to one attempt: typing again hides it, the next send replaces it.
  const [dismissed, setDismissed] = useState(0);
  const failed = state.error && dismissed !== state.sentAt;
  useEffect(() => {
    if (state.sentAt && !state.error) form.current?.reset();
  }, [state]);

  return (
    // Submitted by hand, not with action={...}: React clears a form after every form
    // action, which lost Khalid's text when the send failed. It is cleared only on success.
    <form ref={form} method="post" onSubmit={(e) => {
      e.preventDefault();
      if (!ready) return;
      const data = new FormData(e.currentTarget);
      startTransition(() => action(data));
    }} className="relative min-w-0 flex-none bg-bg pt-2 pb-[max(env(safe-area-inset-bottom),12px)]">
      {jump}
      <div className="composer-surface">
        <label htmlFor="chat-input" className="sr-only">{labels.placeholder}</label>
        {/* 16px text: an iPhone zooms the page when a smaller field gets focus. */}
        <textarea id="chat-input" name="body" rows={1} required maxLength={8000} dir="auto"
          placeholder={labels.placeholder}
          onInput={() => setDismissed(state.sentAt)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              form.current?.requestSubmit();
            }
          }}
          className="composer-input" />
        <button type="submit" disabled={pending || !ready} aria-busy={pending} className="btn btn-primary flex-none">
          {labels.send}
        </button>
      </div>
      <p role="status" aria-live="polite" className={`t-caption wrap mt-1 min-h-5 text-center ${failed ? "text-danger" : "text-muted"}`}>
        {failed ? labels.failed : note}
      </p>
    </form>
  );
}
