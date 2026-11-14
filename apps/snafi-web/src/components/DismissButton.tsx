"use client";

import { useState, useTransition } from "react";
import { tapFeedback } from "@/core/haptics";

/** Hides one of Ahmad's cards from Today (dismiss_card); the card stays in the database. */
export function DismissButton({ id, label, dismiss }: { id: string; label: string; dismiss: (id: string) => Promise<{ ok: boolean }> }) {
  const [pending, start] = useTransition();
  const [gone, setGone] = useState(false);
  if (gone) return null;
  return (
    <button type="button" disabled={pending} data-testid="dismiss-card"
      onClick={() => { tapFeedback(); start(async () => setGone((await dismiss(id)).ok)); }}
      className="min-h-11 rounded-xl px-3 text-xs text-muted hover:text-ink disabled:opacity-50">
      {label}
    </button>
  );
}
