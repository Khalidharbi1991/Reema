/**
 * Which adapter backs each outside service, chosen by settings (never in the screens).
 *   SNAFI_AUTH_ADAPTER     supabase
 *   SNAFI_MAILBOX_ADAPTER  supabase | memory
 *   SNAFI_TODAY_ADAPTER    live | placeholder
 *   SNAFI_THROTTLE_ADAPTER supabase | memory   (sign-in throttle, SEC-4)
 *   SNAFI_MEMORY_ADAPTER   supabase | memory   (step 6: the About me page's memory)
 * Switching one is a settings change plus the new adapter's own file.
 * Preview mode (dev server without keys) uses the in-memory mailbox, throttle and memory.
 */
import { ConfigError } from "./env";

export const ADAPTER_CHOICES = {
  auth: ["supabase"],
  mailbox: ["supabase", "memory"],
  today: ["live", "placeholder"],
  throttle: ["supabase", "memory"],
  memory: ["supabase", "memory"],
} as const;

export type AdapterChoice = {
  auth: (typeof ADAPTER_CHOICES.auth)[number];
  mailbox: (typeof ADAPTER_CHOICES.mailbox)[number];
  today: (typeof ADAPTER_CHOICES.today)[number];
  throttle: (typeof ADAPTER_CHOICES.throttle)[number];
  memory: (typeof ADAPTER_CHOICES.memory)[number];
};

const DEFAULTS: AdapterChoice = { auth: "supabase", mailbox: "supabase", today: "live", throttle: "supabase", memory: "supabase" };
const VARS = {
  auth: "SNAFI_AUTH_ADAPTER", mailbox: "SNAFI_MAILBOX_ADAPTER", today: "SNAFI_TODAY_ADAPTER",
  throttle: "SNAFI_THROTTLE_ADAPTER", memory: "SNAFI_MEMORY_ADAPTER",
} as const;

/** SEC-74: a production build never runs on the in-memory stand-ins (no throttle, no shared mailbox). */
const MEMORY_ONLY_OFF_PRODUCTION = new Set(["memory"]);

export function adapterChoice(
  env: Record<string, string | undefined>, preview = false, nodeEnv: string | undefined = "development",
): AdapterChoice {
  const choice = { ...DEFAULTS };
  for (const kind of Object.keys(VARS) as (keyof typeof VARS)[]) {
    const value = env[VARS[kind]]?.trim();
    if (!value) continue;
    if (!(ADAPTER_CHOICES[kind] as readonly string[]).includes(value)) {
      throw new ConfigError(`${VARS[kind]}=${value} is not one of: ${ADAPTER_CHOICES[kind].join(", ")}`);
    }
    if (nodeEnv === "production" && MEMORY_ONLY_OFF_PRODUCTION.has(value)) {
      throw new ConfigError(`${VARS[kind]}=${value} is for tests and the development server only.`);
    }
    (choice as Record<string, string>)[kind] = value;
  }
  if (preview) {
    choice.mailbox = "memory";
    choice.throttle = "memory";
    choice.memory = "memory";
  }
  return choice;
}

export function currentChoice(preview: boolean): AdapterChoice {
  return adapterChoice({
    SNAFI_AUTH_ADAPTER: process.env.SNAFI_AUTH_ADAPTER,
    SNAFI_MAILBOX_ADAPTER: process.env.SNAFI_MAILBOX_ADAPTER,
    SNAFI_TODAY_ADAPTER: process.env.SNAFI_TODAY_ADAPTER,
    SNAFI_THROTTLE_ADAPTER: process.env.SNAFI_THROTTLE_ADAPTER,
    SNAFI_MEMORY_ADAPTER: process.env.SNAFI_MEMORY_ADAPTER,
  }, preview, process.env.NODE_ENV);
}
