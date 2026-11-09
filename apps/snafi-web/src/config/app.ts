/** App settings that are not secrets. Change them here, not in the screens. */
export const APP_SETTINGS = {
  /** Used for the greeting, dates and prayer times, wherever the server runs. */
  timeZone: "Asia/Riyadh",
  /** Prayer times (Umm al-Qura) are computed for this city. */
  city: { name: "Jeddah", latitude: 21.4858, longitude: 39.1925, timeZone: "Asia/Riyadh" },
} as const;

/** Hour (0-23) of `now` in the configured time zone. */
export function localHour(now: Date, timeZone: string = APP_SETTINGS.timeZone): number {
  const hour = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", hourCycle: "h23", timeZone }).format(now);
  return Number.parseInt(hour, 10) % 24;
}
