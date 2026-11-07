import { describe, expect, it } from "vitest";
import { ConfigError, isPreviewMode, readSupabaseConfig } from "@/config/env";
import { localHour } from "@/config/app";

const URL_OK = "https://abcd.supabase.co";
const jwt = (payload: object) =>
  ["eyJhbGciOiJIUzI1NiJ9", btoa(JSON.stringify(payload)).replace(/=+$/, ""), "sig"].join(".");

describe("readSupabaseConfig", () => {
  it("is null when nothing is set", () => {
    expect(readSupabaseConfig({})).toBeNull();
  });

  it("needs both values", () => {
    expect(() => readSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: URL_OK })).toThrow(ConfigError);
    expect(() => readSupabaseConfig({ NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_x" })).toThrow(ConfigError);
  });

  it("accepts https and a publishable key", () => {
    expect(readSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: URL_OK + "/", NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: " sb_publishable_x " }))
      .toEqual({ url: URL_OK, publishableKey: "sb_publishable_x" });
    expect(readSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: URL_OK, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: jwt({ role: "anon" }) }))
      .not.toBeNull();
  });

  it("refuses plain http except localhost", () => {
    expect(() => readSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: "http://abcd.supabase.co", NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "k" })).toThrow(/https/);
    expect(readSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: "http://localhost:54321", NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "k" })).not.toBeNull();
    expect(() => readSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: "not a url", NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "k" })).toThrow(/valid URL/);
  });

  it("refuses a secret or service_role key", () => {
    expect(() => readSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: URL_OK, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_secret_abc" })).toThrow(/secret/);
    expect(() => readSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: URL_OK, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: jwt({ role: "service_role" }) })).toThrow(/secret/);
  });
});

describe("isPreviewMode", () => {
  it("is on only for a development server without keys", () => {
    expect(isPreviewMode({}, "development")).toBe(true);
    expect(isPreviewMode({}, "production")).toBe(false);
    expect(isPreviewMode({ NEXT_PUBLIC_SUPABASE_URL: URL_OK, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "k" }, "development")).toBe(false);
  });
});

describe("localHour", () => {
  it("uses the configured time zone", () => {
    expect(localHour(new Date("2026-11-07T20:30:00Z"), "Asia/Riyadh")).toBe(23);
    expect(localHour(new Date("2026-11-07T21:30:00Z"), "Asia/Riyadh")).toBe(0);
  });
});
