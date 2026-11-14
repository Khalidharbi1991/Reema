import "server-only";
/**
 * Maps the configured choice (config/services.ts) to an adapter. No provider is
 * picked here: only the settings decide. Adding a provider means its own file plus one
 * line in each table below.
 */
import { isPreviewMode } from "@/config/env";
import { currentChoice } from "@/config/services";
import { SupabaseAuthAdapter } from "./auth/supabase";
import type { AuthAdapter } from "./auth/types";
import { createMemoryStore, MemoryMailboxAdapter } from "./mailbox/memory";
import { SupabaseMailboxAdapter } from "./mailbox/supabase";
import type { MailboxAdapter } from "./mailbox/types";
import { MemoryThrottleAdapter } from "./throttle/memory";
import { SupabaseThrottleAdapter } from "./throttle/supabase";
import type { ThrottleAdapter } from "./throttle/types";
import { LiveTodaySource } from "./today/live";
import { PlaceholderTodaySource } from "./today/placeholder";
import type { TodaySource } from "./today/types";

/** Preview mode's owner and conversation (dev server without keys only). */
export const PREVIEW_USER = "00000000-0000-4000-8000-000000000000";
const previewStore = createMemoryStore();
const memoryThrottle = new MemoryThrottleAdapter();

const AUTH: Record<string, () => AuthAdapter> = {
  supabase: () => new SupabaseAuthAdapter(),
};
const MAILBOX: Record<string, (userId: string | null) => MailboxAdapter> = {
  supabase: () => new SupabaseMailboxAdapter(),
  memory: (userId) => new MemoryMailboxAdapter(previewStore, userId ?? PREVIEW_USER),
};
const TODAY: Record<string, (mailbox: MailboxAdapter) => TodaySource> = {
  live: (mailbox) => new LiveTodaySource(() => mailbox.pendingApprovals(5), () => mailbox.todayFeed(), () => mailbox.cards(10)),
  placeholder: () => new PlaceholderTodaySource(),
};

const THROTTLE: Record<string, () => ThrottleAdapter> = {
  supabase: () => new SupabaseThrottleAdapter(),
  memory: () => memoryThrottle,
};

const choice = () => currentChoice(isPreviewMode());

export function authAdapter(): AuthAdapter {
  return AUTH[choice().auth]();
}

export function mailboxAdapter(userId: string | null = null): MailboxAdapter {
  return MAILBOX[choice().mailbox](userId);
}

export function todaySource(mailbox: MailboxAdapter): TodaySource {
  return TODAY[choice().today](mailbox);
}

export function throttleAdapter(): ThrottleAdapter {
  return THROTTLE[choice().throttle]();
}
