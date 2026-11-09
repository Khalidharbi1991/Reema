"use client";

import { useState, useTransition } from "react";
import type { ActionEntry } from "@/adapters/mailbox/types";
import { tapFeedback } from "@/core/haptics";

type Props = {
  action: ActionEntry;
  labels: { undo: string; undoing: string; undone: string };
  undo: (id: string) => Promise<{ ok: boolean }>;
};

/** Undo for a Level 2 action. Shown only while it can still be undone. */
export function UndoButton({ action, labels, undo }: Props) {
  const [pending, start] = useTransition();
  const [asked, setAsked] = useState(action.undoRequested);
  if (action.status === "undone") return <span className="text-xs text-muted">{labels.undone}</span>;
  if (!action.undoable || action.status !== "done") return null;
  if (asked) return <span className="text-xs text-muted">{labels.undoing}</span>;
  return (
    <button type="button" disabled={pending}
      onClick={() => {
        tapFeedback();
        start(async () => setAsked((await undo(action.id)).ok));
      }}
      className="min-h-9 rounded-full border border-edge px-3 text-xs text-gold-ink disabled:opacity-60">
      {labels.undo}
    </button>
  );
}
