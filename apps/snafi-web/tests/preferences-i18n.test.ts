import { describe, expect, it } from "vitest";
import {
  dayPartFor,
  greetingFor,
  LANG_COOKIE,
  preferenceCookie,
  readPreferences,
  THEME_COOKIE,
} from "@/core/preferences";
import { direction, isLang, messages } from "@/i18n/messages";

describe("preferences", () => {
  it("defaults to dark and English, and ignores bad values", () => {
    expect(readPreferences(() => undefined)).toEqual({ theme: "dark", lang: "en" });
    expect(readPreferences(() => "<script>")).toEqual({ theme: "dark", lang: "en" });
    const cookies: Record<string, string> = { [THEME_COOKIE]: "light", [LANG_COOKIE]: "ar" };
    expect(readPreferences((n) => cookies[n])).toEqual({ theme: "light", lang: "ar" });
  });

  it("writes only valid cookie values", () => {
    expect(preferenceCookie(THEME_COOKIE, "light")).toMatch(/^snafi-theme=light; Path=\/; Max-Age=\d+; SameSite=Lax$/);
    expect(() => preferenceCookie(THEME_COOKIE, "ar" as never)).toThrow();
    expect(() => preferenceCookie(LANG_COOKIE, "fr" as never)).toThrow();
  });

  it("picks greeting and background bands by hour", () => {
    expect([5, 13, 19, 23, 2].map(greetingFor)).toEqual(["morning", "afternoon", "evening", "night", "night"]);
    expect([5, 12, 18, 22].map(dayPartFor)).toEqual(["dawn", "day", "dusk", "night"]);
  });
});

function shape(value: unknown): unknown {
  if (typeof value === "function") return "fn";
  if (typeof value === "string") return "str";
  return Object.fromEntries(Object.entries(value as object).map(([k, v]) => [k, shape(v)]).sort());
}

function strings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (typeof value === "object" && value) return Object.values(value).flatMap(strings);
  return [];
}

describe("Arabic and English", () => {
  it("are right-to-left and left-to-right", () => {
    expect(direction("ar")).toBe("rtl");
    expect(direction("en")).toBe("ltr");
    expect(isLang("ar") && isLang("en") && !isLang("fr")).toBe(true);
  });

  it("have the same keys and no empty strings", () => {
    expect(shape(messages("ar"))).toEqual(shape(messages("en")));
    for (const lang of ["en", "ar"] as const) {
      expect(strings(messages(lang)).every((s) => s.trim().length > 0)).toBe(true);
    }
  });

  it("really are Arabic in Arabic", () => {
    const arabic = /[؀-ۿ]/;
    expect(arabic.test(messages("ar").signIn.title)).toBe(true);
    expect(arabic.test(messages("ar").approve)).toBe(true);
    expect(messages("ar").prayerRingLabel("العصر", "15:12", 62)).toContain("62");
  });
});
