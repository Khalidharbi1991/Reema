import "server-only";
/**
 * The one place that picks which adapter backs each outside service.
 * Swapping a provider means changing one line here and adding its file.
 */
import { SupabaseAuthAdapter } from "./auth/supabase";
import type { AuthAdapter } from "./auth/types";
import { SupabaseMailboxAdapter } from "./mailbox/supabase";
import type { MailboxAdapter } from "./mailbox/types";
import { PlaceholderTodaySource } from "./today/placeholder";
import type { TodaySource } from "./today/types";

export function authAdapter(): AuthAdapter {
  return new SupabaseAuthAdapter();
}

export function mailboxAdapter(): MailboxAdapter {
  return new SupabaseMailboxAdapter();
}

export function todaySource(): TodaySource {
  return new PlaceholderTodaySource();
}
