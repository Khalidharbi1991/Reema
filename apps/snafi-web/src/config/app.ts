/** App settings that are not secrets. Change them here, not in the screens. */
export const APP_SETTINGS = {
  /** Used for the greeting and dates, so they match Khalid's day wherever the server runs. */
  timeZone: "Asia/Riyadh",
} as const;

/** Hour (0-23) of `now` in the configured time zone. */
export function localHour(now: Date, timeZone: string = APP_SETTINGS.timeZone): number {
  const hour = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", hourCycle: "h23", timeZone }).format(now);
  return Number.parseInt(hour, 10) % 24;
}
