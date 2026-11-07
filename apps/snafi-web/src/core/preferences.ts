import { isLang, type Lang } from "@/i18n/messages";

export type Theme = "dark" | "light";

export const THEME_COOKIE = "snafi-theme";
export const LANG_COOKIE = "snafi-lang";
export const DEFAULT_THEME: Theme = "dark";
export const DEFAULT_LANG: Lang = "en";
// One year; these hold only display preferences, never personal data.
export const PREF_MAX_AGE = 60 * 60 * 24 * 365;

export function isTheme(value: unknown): value is Theme {
  return value === "dark" || value === "light";
}

export function readPreferences(get: (name: string) => string | undefined): { theme: Theme; lang: Lang } {
  const theme = get(THEME_COOKIE);
  const lang = get(LANG_COOKIE);
  return {
    theme: isTheme(theme) ? theme : DEFAULT_THEME,
    lang: isLang(lang) ? lang : DEFAULT_LANG,
  };
}

/** Cookie string for document.cookie; values are validated so nothing else can be written. */
export function preferenceCookie(name: typeof THEME_COOKIE | typeof LANG_COOKIE, value: Theme | Lang): string {
  if (name === THEME_COOKIE && !isTheme(value)) throw new Error("invalid theme");
  if (name === LANG_COOKIE && !isLang(value)) throw new Error("invalid language");
  return `${name}=${value}; Path=/; Max-Age=${PREF_MAX_AGE}; SameSite=Lax`;
}

export type DayPart = "dawn" | "day" | "dusk" | "night";

/** Greeting band for an hour of the day (0-23). */
export function greetingFor(hour: number): "morning" | "afternoon" | "evening" | "night" {
  if (hour >= 4 && hour < 12) return "morning";
  if (hour >= 12 && hour < 17) return "afternoon";
  if (hour >= 17 && hour < 22) return "evening";
  return "night";
}

/** Background tone band; shifts subtly through the day. */
export function dayPartFor(hour: number): DayPart {
  if (hour >= 4 && hour < 8) return "dawn";
  if (hour >= 8 && hour < 16) return "day";
  if (hour >= 16 && hour < 20) return "dusk";
  return "night";
}
