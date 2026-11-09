// @vitest-environment node
/** Step 2: Jeddah prayer times (Umm al-Qura), Hijri date, live Today, PC status, adapters chosen by config. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { isOnline, OFFLINE_AFTER_MS } from "@/adapters/mailbox/types";
import { LiveTodaySource } from "@/adapters/today/live";
import { clock, hijriDate, hijriMonth, nextPrayer, prayerTimesFor } from "@/adapters/today/prayer";
import { APP_SETTINGS } from "@/config/app";
import { ConfigError } from "@/config/env";
import { adapterChoice } from "@/config/services";
import { statusLines } from "@/components/PcStatus";
import { messages } from "@/i18n/messages";

const JEDDAH = APP_SETTINGS.city;
const TZ = JEDDAH.timeZone;
const times = (y: number, m: number, d: number) =>
  Object.fromEntries(Object.entries(prayerTimesFor(JEDDAH, y, m, d)).map(([k, v]) => [k, clock(v, TZ)]));

describe("prayer times for Jeddah (Umm al-Qura)", () => {
  it("matches the computed table for known days", () => {
    expect(times(2026, 11, 9)).toEqual({ fajr: "05:12", dhuhr: "12:07", asr: "15:19", maghrib: "17:43", isha: "19:13" });
    expect(times(2026, 6, 21)).toEqual({ fajr: "04:14", dhuhr: "12:25", asr: "15:45", maghrib: "19:08", isha: "20:38" });
  });

  it("puts Isha 90 minutes after Maghrib, and 120 in Ramadan", () => {
    const gap = (y: number, m: number, d: number) => {
      const t = prayerTimesFor(JEDDAH, y, m, d);
      return (t.isha.getTime() - t.maghrib.getTime()) / 60_000;
    };
    expect(gap(2026, 11, 9)).toBe(90);
    // 1 March 2027 falls in Ramadan 1448 on the Umm al-Qura calendar.
    expect(hijriMonth(new Date("2027-03-01T09:00:00Z"), TZ)).toBe(9);
    expect(gap(2027, 3, 1)).toBe(120);
  });

  it("finds the next prayer and how far the wait has gone", () => {
    const afterDhuhr = nextPrayer(JEDDAH, new Date("2026-11-09T11:00:00Z")); // 14:00 in Jeddah
    expect(afterDhuhr.key).toBe("asr");
    expect(afterDhuhr.time).toBe("15:19");
    expect(afterDhuhr.progress).toBeGreaterThan(0.5);
    expect(afterDhuhr.progress).toBeLessThan(0.7);
    const lateNight = nextPrayer(JEDDAH, new Date("2026-11-09T19:00:00Z")); // 22:00
    expect(lateNight.key).toBe("fajr");
    expect(lateNight.time).toBe("05:13"); // tomorrow's Fajr
    const beforeFajr = nextPrayer(JEDDAH, new Date("2026-11-09T01:00:00Z")); // 04:00
    expect(beforeFajr.key).toBe("fajr");
    expect(beforeFajr.time).toBe("05:12");
  });

  it("gives the Umm al-Qura Hijri date in both languages", () => {
    const now = new Date("2026-11-09T09:00:00Z");
    expect(hijriDate(now, "en", TZ)).toBe("29 Jumada I 1448 AH");
    expect(hijriDate(now, "ar", TZ)).toBe("29 جمادى الأولى 1448 هـ");
  });
});

describe("live Today", () => {
  it("has real prayer and dates, marks the rest as samples, and shows real approvals", async () => {
    const card = { id: "a", conversationId: "c", tool: "send_test_message", args: {}, argsHash: "", summary: "Test send",
      status: "pending" as const, createdAt: "", expiresAt: "2999-01-01T00:00:00Z" };
    const today = await new LiveTodaySource(async () => [card]).getToday("en", new Date("2026-11-09T11:00:00Z"));
    expect(today.samples).toEqual({ prayer: false, nextEvent: true, tasks: true, cards: true });
    expect(today.nextPrayer).toMatchObject({ key: "asr", time: "15:19" });
    expect(today.hijriDate).toBe("29 Jumada I 1448 AH");
    expect(today.approvals).toEqual([card]);
  });

  it("still shows when the mailbox is unreachable", async () => {
    const today = await new LiveTodaySource(async () => { throw new Error("down"); }).getToday("ar", new Date());
    expect(today.approvals).toEqual([]);
  });
});

describe("PC online / offline", () => {
  const now = new Date("2026-11-09T10:00:00Z");
  const status = (msAgo: number, ok: boolean | null = true) => ({
    lastSeen: new Date(now.getTime() - msAgo).toISOString(), lastBackupAt: "2026-11-09T00:30:00Z",
    lastBackupOk: ok, lastBackupError: null,
  });

  it("is offline after 45 seconds without a heartbeat, or with no worker at all", () => {
    expect(OFFLINE_AFTER_MS).toBe(45_000);
    expect(isOnline(status(10_000), now)).toBe(true);
    expect(isOnline(status(46_000), now)).toBe(false);
    expect(isOnline(null, now)).toBe(false);
  });

  it("shows the last backup's time and result in the menu", () => {
    expect(statusLines(status(1_000), now, messages("en"), "en")).toEqual(["PC online", "Last backup 9 Nov, 03:30 ✓"]);
    expect(statusLines(status(99_000, false), now, messages("en"), "en")[1]).toMatch(/^Last backup failed/);
    expect(statusLines(null, now, messages("ar"), "ar")).toEqual([messages("ar").pcOffline, messages("ar").noBackup]);
  });
});

describe("adapters are chosen by config", () => {
  it("defaults to Supabase and live Today", () => {
    expect(adapterChoice({})).toEqual({ auth: "supabase", mailbox: "supabase", today: "live" });
  });

  it("switches one adapter with one setting and nothing else", () => {
    expect(adapterChoice({ SNAFI_MAILBOX_ADAPTER: "memory" })).toEqual({ auth: "supabase", mailbox: "memory", today: "live" });
    expect(adapterChoice({ SNAFI_TODAY_ADAPTER: "placeholder" })).toEqual({ auth: "supabase", mailbox: "supabase", today: "placeholder" });
  });

  it("refuses unknown providers and uses memory in preview mode", () => {
    expect(() => adapterChoice({ SNAFI_MAILBOX_ADAPTER: "mongo" })).toThrow(ConfigError);
    expect(adapterChoice({}, true).mailbox).toBe("memory");
  });

  it("picks providers only from the settings in adapters/index.ts", () => {
    const src = readFileSync(resolve(process.cwd(), "src/adapters/index.ts"), "utf8");
    expect(src).toContain("currentChoice(");
    for (const fn of ["authAdapter", "mailboxAdapter", "todaySource"]) {
      const body = src.slice(src.indexOf(`export function ${fn}`)).split("\n}")[0];
      expect(body, fn).toMatch(/\[choice\(\)\.(auth|mailbox|today)\]/);
      expect(body, fn).not.toMatch(/new [A-Z]/);
    }
  });
});
