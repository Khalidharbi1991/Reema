"use client";

import { useState } from "react";
import Link from "next/link";
import { badgeText } from "@/core/inbox";
import { messages, type Lang } from "@/i18n/messages";
import { BellIcon } from "./Icons";
import { useShell } from "./ShellState";

type Props = {
  lang: Lang;
  /** Ids of the unread items the server counted (no `test` cards); null when the count could not be read. */
  unreadIds: string[] | null;
  /** True on /inbox itself. */
  current?: boolean;
};

/**
 * The bell: a link to the Inbox with the unread badge (nothing at 0, the number to 9, "9+" from 10).
 * The label always says the real number. The count drops as soon as a card is opened or an
 * approval is decided, and a hidden status line then says the new count (never on first load).
 */
export function Bell({ lang, unreadIds, current = false }: Props) {
  const t = messages(lang).inbox;
  const { settled } = useShell();
  const count = unreadIds ? unreadIds.filter((id) => !settled.has(id)).length : null;
  const [first] = useState(count);
  const badge = count === null ? null : badgeText(count);
  const label = count === null ? t.title : count === 0 ? t.bellNone : t.bell(count);
  const changed = count !== null && count !== first;
  return (
    <>
      <Link href="/inbox" aria-label={label} aria-current={current ? "page" : undefined} className="icon-btn" data-testid="bell">
        <BellIcon />
        {badge && <span className="badge" dir="ltr" aria-hidden="true" data-testid="bell-badge">{badge}</span>}
      </Link>
      <span role="status" className="sr-only" data-testid="bell-status">
        {changed ? (count === 0 ? t.unreadNone : t.unreadNow(count)) : ""}
      </span>
    </>
  );
}
