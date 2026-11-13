/**
 * Which adapter backs each outside service, chosen by settings (never in the screens).
 *   SNAFI_AUTH_ADAPTER     supabase
 *   SNAFI_MAILBOX_ADAPTER  supabase | memory
 *   SNAFI_TODAY_ADAPTER    live | placeholder
 *   SNAFI_THROTTLE_ADAPTER supabase | memory   (sign-in throttle, SEC-4)
 * Switching one is a settings change plus the new adapter's own file.
 * Preview mode (dev server without keys) uses the in-memory mailbox and throttle.
 */
import { ConfigError } from "./env";

export const ADAPTER_CHOICES = {
  auth: ["supabase"],
  mailbox: ["supabase", "memory"],
  today: ["live", "placeholder"],
  throttle: ["supabase", "memory"],
} as const;

export type AdapterChoice = {
  auth: (typeof ADAPTER_CHOICES.auth)[number];
  mailbox: (typeof ADAPTER_CHOICES.mailbox)[number];
  today: (typeof ADAPTER_CHOICES.today)[number];
  throttle: (typeof ADAPTER_CHOICES.throttle)[number];
};

const DEFAULTS: AdapterChoice = { auth: "supabase", mailbox: "supabase", today: "live", throttle: "supabase" };
const VARS = { auth: "SNAFI_AUTH_ADAPTER", mailbox: "SNAFI_MAILBOX_ADAPTER", today: "SNAFI_TODAY_ADAPTER", throttle: "SNAFI_THROTTLE_ADAPTER" } as const;

export function adapterChoice(env: Record<string, string | undefined>, preview = false): AdapterChoice {
  const choice = { ...DEFAULTS };
  for (const kind of Object.keys(VARS) as (keyof typeof VARS)[]) {
    const value = env[VARS[kind]]?.trim();
    if (!value) continue;
    if (!(ADAPTER_CHOICES[kind] as readonly string[]).includes(value)) {
      throw new ConfigError(`${VARS[kind]}=${value} is not one of: ${ADAPTER_CHOICES[kind].join(", ")}`);
    }
    (choice as Record<string, string>)[kind] = value;
  }
  if (preview) {
    choice.mailbox = "memory";
    choice.throttle = "memory";
  }
  return choice;
}

export function currentChoice(preview: boolean): AdapterChoice {
  return adapterChoice({
    SNAFI_AUTH_ADAPTER: process.env.SNAFI_AUTH_ADAPTER,
    SNAFI_MAILBOX_ADAPTER: process.env.SNAFI_MAILBOX_ADAPTER,
    SNAFI_TODAY_ADAPTER: process.env.SNAFI_TODAY_ADAPTER,
    SNAFI_THROTTLE_ADAPTER: process.env.SNAFI_THROTTLE_ADAPTER,
  }, preview);
}
