"use client";

import { useActionState, useEffect, useRef } from "react";
import type { ChatState } from "../actions";

type Props = {
  send: (prev: ChatState, form: FormData) => Promise<ChatState>;
  labels: { placeholder: string; send: string; attach: string; failed: string };
  note: string;
};

/** Text only in step 2; attachments arrive with Drive in step 3. */
export function ChatComposer({ send, labels, note }: Props) {
  const [state, action, pending] = useActionState(send, { error: false, sentAt: 0 });
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (state.sentAt && !state.error) form.current?.reset();
  }, [state]);

  return (
    <form ref={form} action={action} className="sticky bottom-0 bg-bg pt-2 pb-[max(env(safe-area-inset-bottom),1rem)]">
      <div className="flex items-end gap-2 rounded-2xl border border-edge bg-card p-2">
        <button type="button" disabled aria-label={labels.attach}
          className="flex h-10 w-10 items-center justify-center rounded-full text-lg text-muted disabled:opacity-40">
          <span aria-hidden="true">＋</span>
        </button>
        <label htmlFor="chat-input" className="sr-only">{labels.placeholder}</label>
        <textarea id="chat-input" name="body" rows={1} required maxLength={8000} dir="auto"
          placeholder={labels.placeholder}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              form.current?.requestSubmit();
            }
          }}
          className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-ink placeholder:text-muted focus:outline-none" />
        <button type="submit" disabled={pending}
          className="min-h-10 rounded-xl bg-gold px-4 text-sm font-medium text-[#0E0E10] disabled:opacity-50">
          {labels.send}
        </button>
      </div>
      <p role="status" aria-live="polite" className="mt-2 min-h-4 text-center text-xs text-muted">
        {state.error ? labels.failed : note}
      </p>
    </form>
  );
}
