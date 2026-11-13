import {
  checkKeys,
  THROTTLE_GLOBAL_CEILING,
  THROTTLE_LIMIT,
  THROTTLE_WINDOW_SECONDS,
  type ThrottleAdapter,
  type ThrottleTicket,
} from "./types";

type Row = { attempt: string; key: string; at: number };

/** Same rule as signin_begin in migration 0005, kept in memory. Tests and preview mode only. */
export class MemoryThrottleAdapter implements ThrottleAdapter {
  private rows: Row[] = [];

  constructor(private readonly now: () => number = () => Date.now()) {}

  async begin(keys: string[]): Promise<ThrottleTicket> {
    checkKeys(keys);
    const since = this.now() - THROTTLE_WINDOW_SECONDS * 1000;
    this.rows = this.rows.filter((r) => r.at > this.now() - 3_600_000);
    const recent = this.rows.filter((r) => r.at > since);
    if (recent.length >= THROTTLE_GLOBAL_CEILING) return { wait: 60, attempt: null };
    let wait = 0;
    for (const key of keys) {
      const fifth = recent.filter((r) => r.key === key).map((r) => r.at).sort((a, b) => b - a)[THROTTLE_LIMIT - 1];
      if (fifth !== undefined) wait = Math.max(wait, Math.ceil((fifth + THROTTLE_WINDOW_SECONDS * 1000 - this.now()) / 1000));
    }
    if (wait > 0) return { wait, attempt: null };
    const attempt = crypto.randomUUID();
    for (const key of keys) this.rows.push({ attempt, key, at: this.now() });
    return { wait: 0, attempt };
  }

  async forget(attempt: string) {
    this.rows = this.rows.filter((r) => r.attempt !== attempt);
  }
}
