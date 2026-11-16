import "server-only";
import { cache } from "react";
import { todaySource } from "@/adapters";
import { getPreferences } from "@/core/server-preferences";
import { mailboxFor, requireSession } from "@/core/session";

/**
 * One read per request, shared by the signed-in layout (the bell's count, the Settings mark) and
 * the page under it (Today, the Inbox, Settings), so the bell adds no reads of its own.
 */
export const loadToday = cache(async () => {
  const session = await requireSession();
  const { theme, lang } = await getPreferences();
  const now = new Date();
  const today = await todaySource(mailboxFor(session)).getToday(lang, now);
  return { session, theme, lang, now, today };
});
