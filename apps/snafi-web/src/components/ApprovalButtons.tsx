"use client";

import { useState } from "react";
import { tapFeedback } from "@/core/haptics";

type Props = { approve: string; reject: string; disabledNote: string };

/**
 * Approve / Reject as plain buttons, never swipes. In step 1 they do nothing
 * except give tap feedback and say approvals arrive in step 2.
 */
export function ApprovalButtons({ approve, reject, disabledNote }: Props) {
  const [note, setNote] = useState("");
  const tap = () => {
    tapFeedback();
    setNote(disabledNote);
  };
  return (
    <div>
      <div className="mt-3 flex gap-3">
        <button
          type="button"
          onClick={tap}
          className="min-h-11 flex-1 rounded-xl bg-gold px-4 text-sm font-medium text-[#0E0E10] transition-opacity active:opacity-80"
        >
          {approve}
        </button>
        <button
          type="button"
          onClick={tap}
          className="min-h-11 flex-1 rounded-xl border border-edge px-4 text-sm text-ink transition-opacity active:opacity-80"
        >
          {reject}
        </button>
      </div>
      <p role="status" aria-live="polite" className="mt-2 min-h-4 text-xs text-muted">{note}</p>
    </div>
  );
}
