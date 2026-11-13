import { checkKeys, THROTTLE_LIMIT, THROTTLE_WINDOW_SECONDS, type ThrottleAdapter } from "./types";

/** Same rule as signin_wait_seconds in migration 0005, kept in memory. Tests and preview mode only. */
export class MemoryThrottleAdapter implements ThrottleAdapter {
  private readonly failures = new Map<string, number[]>();

  constructor(private readonly now: () => number = () => Date.now()) {}

  private recent(key: string): number[] {
    const since = this.now() - THROTTLE_WINDOW_SECONDS * 1000;
    return (this.failures.get(key) ?? []).filter((t) => t > since).sort((a, b) => b - a);
  }

  async waitSeconds(keys: string[]) {
    let wait = 0;
    for (const key of checkKeys(keys)) {
      const fifth = this.recent(key)[THROTTLE_LIMIT - 1];
      if (fifth !== undefined) wait = Math.max(wait, Math.ceil((fifth + THROTTLE_WINDOW_SECONDS * 1000 - this.now()) / 1000));
    }
    return Math.max(wait, 0);
  }

  async recordFailure(keys: string[]) {
    for (const key of checkKeys(keys)) {
      const recent = this.recent(key);
      if (recent.length < 20) this.failures.set(key, [...recent, this.now()]);
    }
  }
}
