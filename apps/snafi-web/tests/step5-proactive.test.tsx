/** Snafi step 5: Proactive Ahmad. Migration 0008, Settings, real cards, Web Push in the service worker, 12-hour times. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import type { PGlite } from "@electric-sql/pglite";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { createMemoryStore, MemoryMailboxAdapter } from "@/adapters/mailbox/memory";
import { checkPushKeys, DEFAULT_SETTINGS, PUSH_ENDPOINT, type Settings } from "@/adapters/mailbox/types";
import { LiveTodaySource } from "@/adapters/today/live";
import { hijriMonth, prayerTimesFor } from "@/adapters/today/prayer";
import { TodayView } from "@/app/(app)/today/TodayView";
import { SettingsForm, toBase64Url } from "@/app/(app)/settings/SettingsForm";
import { APP_SETTINGS } from "@/config/app";
import { ConfigError, readVapidPublicKey } from "@/config/env";
import { clock12, hm12, joinHHMM, splitHHMM } from "@/core/clock";
import { messages } from "@/i18n/messages";
import { ALICE, as, BOB, freshDb } from "./helpers/db";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const P256DH = "B" + "A".repeat(86);
const AUTH = "C".repeat(22);
const APPLE = "https://web.push.apple.com/QGuQyavXutnMH6mIqdJu8g";
const ENDPOINTS: [string, boolean][] = [
  [APPLE, true],
  ["https://fcm.googleapis.com/fcm/send/abc:def", true],
  ["https://updates.push.services.mozilla.com/wpush/v2/gAAAA", true],
  ["https://wns2-par02p.notify.windows.com/w/?token=BQYAAA", true],
  ["http://fcm.googleapis.com/fcm/send/abc", false],
  ["https://fcm.googleapis.com.evil.example/fcm/send/abc", false],
  ["https://evil.example/fcm.googleapis.com/abc", false],
  ["https://user@fcm.googleapis.com/fcm/send/abc", false],
  ["https://fcm.googleapis.com:8443/fcm/send/abc", false],
  ["https://169.254.169.254/latest/meta-data", false],
  ["https://web.push.apple.com/abc\nHost: x", false],
];

// ---------- the database ----------
describe("migration 0008", () => {
  let db: PGlite;
  beforeAll(async () => {
    db = await freshDb();
  }, 60_000);

  const TABLES = ["user_settings", "push_subscriptions", "notifications", "cards"];

  it("forces row-level security and gives the app no direct writes", async () => {
    const r = await db.query<{ relname: string; relrowsecurity: boolean; relforcerowsecurity: boolean }>(
      "select relname, relrowsecurity, relforcerowsecurity from pg_class where relname = any($1)", [TABLES]);
    expect(r.rows).toHaveLength(4);
    expect(r.rows.every((x) => x.relrowsecurity && x.relforcerowsecurity)).toBe(true);
    for (const t of TABLES) {
      await expect(as(db, "anon", null, `select * from public.${t}`)).rejects.toThrow(/permission denied/);
      await expect(as(db, "authenticated", ALICE, `insert into public.${t} (user_id) values ('${ALICE}')`)).rejects.toThrow(/permission denied/);
      await expect(as(db, "authenticated", ALICE, `delete from public.${t}`)).rejects.toThrow(/permission denied/);
    }
    // The app never reads push addresses or the ledger.
    await expect(as(db, "authenticated", ALICE, "select * from public.push_subscriptions")).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE, "select * from public.notifications")).rejects.toThrow(/permission denied/);
  });

  it("saves settings only within the limits, one row per user", async () => {
    await as(db, "authenticated", ALICE, "select public.save_settings(true, '19:30', 12, 'ar')");
    await as(db, "authenticated", ALICE, "select public.save_settings(true, '06:05', 3, 'en')");
    const mine = await as<{ brief_time: string; daily_cap: number }>(db, "authenticated", ALICE, "select * from public.user_settings");
    expect(mine.rows).toMatchObject([{ brief_time: "06:05", daily_cap: 3 }]);
    for (const bad of ["(true, '24:00', 10, 'en')", "(true, '7:00', 10, 'en')", "(true, '07:00', 0, 'en')",
      "(true, '07:00', 51, 'en')", "(true, '07:00', 10, 'fr')", "(null, '07:00', 10, 'en')"]) {
      await expect(as(db, "authenticated", ALICE, `select public.save_settings${bad}`)).rejects.toThrow(/invalid settings/);
    }
    expect((await as(db, "authenticated", BOB, "select * from public.user_settings")).rows).toEqual([]);
  });

  it("accepts push addresses only from the four browser push services", async () => {
    for (const [endpoint, ok] of ENDPOINTS) {
      const r = await as<{ ok: boolean }>(db, "authenticated", ALICE, "select public.push_endpoint_ok($1) as ok", [endpoint]);
      expect([endpoint, r.rows[0].ok]).toEqual([endpoint, ok]);
      expect([endpoint, PUSH_ENDPOINT.test(endpoint)]).toEqual([endpoint, ok]); // the app's check agrees
    }
    await expect(as(db, "authenticated", ALICE, "select public.save_push_subscription($1, $2, $3)",
      ["https://evil.example/push/abcdefghij", P256DH, AUTH])).rejects.toThrow(/not a known push service/);
    await expect(as(db, "authenticated", ALICE, "select public.save_push_subscription($1, $2, $3)",
      [APPLE, "short", AUTH])).rejects.toThrow(/invalid push keys/);
  });

  it("keeps each user's phones to themselves, at most five, and removes on request", async () => {
    await as(db, "authenticated", ALICE, "select public.save_push_subscription($1, $2, $3)", [APPLE, P256DH, AUTH]);
    await expect(as(db, "authenticated", BOB, "select public.save_push_subscription($1, $2, $3)", [APPLE, P256DH, AUTH]))
      .rejects.toThrow(/already in use/);
    for (let i = 0; i < 6; i++) {
      await as(db, "authenticated", ALICE, "select public.save_push_subscription($1, $2, $3)", [`${APPLE}${i}`, P256DH, AUTH]);
    }
    const count = async (user: string) => (await as<{ n: number }>(db, "service_role", null,
      "select count(*)::int as n from public.push_subscriptions where user_id = $1", [user])).rows[0].n;
    expect(await count(ALICE)).toBe(5);
    await as(db, "authenticated", BOB, "select public.remove_push_subscription($1)", [`${APPLE}5`]); // not Bob's
    expect(await count(ALICE)).toBe(5);
    await as(db, "authenticated", ALICE, "select public.remove_push_subscription($1)", [`${APPLE}5`]);
    expect(await count(ALICE)).toBe(4);
  });

  // Until the Inbox job this test also checked dismiss_card: the owner could dismiss her own card
  // once, and Bob was refused on hers ("no card"). Migration 0009 takes that right back from the
  // app (SEC-175), so what is checked now is that the app can no longer call it at all; the
  // function and the rows it wrote stay (see rls-inbox.test.ts).
  it("never stores the same notification twice, and no longer lets the app dismiss a card", async () => {
    const insert = "insert into public.notifications (user_id, kind, dedupe_key) values ($1, 'reminder', 'reminder:1')";
    await as(db, "service_role", null, insert, [ALICE]);
    await expect(as(db, "service_role", null, insert, [ALICE])).rejects.toThrow(/duplicate key/);
    const card = await as<{ id: string }>(db, "service_role", null,
      "insert into public.cards (user_id, kind, title, body) values ($1, 'reminder', 'Reminder', 'Call the bank') returning id", [ALICE]);
    const id = card.rows[0].id;
    expect((await as(db, "authenticated", BOB, "select * from public.cards")).rows).toEqual([]);
    await expect(as(db, "authenticated", BOB, "select public.dismiss_card($1)", [id])).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE, "select public.dismiss_card($1)", [id])).rejects.toThrow(/permission denied/);
    expect((await as<{ dismissed_at: string | null }>(db, "service_role", null,
      "select dismissed_at from public.cards where id = $1", [id])).rows[0].dismissed_at).toBeNull();
  });

  it("queues at most one test push, and the app still cannot queue jobs of its own", async () => {
    await as(db, "authenticated", ALICE, "select public.request_test_push()");
    await as(db, "authenticated", ALICE, "select public.request_test_push()");
    const jobs = await as<{ kind: string; lane: string }>(db, "service_role", null,
      "select kind, lane from public.jobs where user_id = $1 and kind = 'push.test'", [ALICE]);
    expect(jobs.rows).toEqual([{ kind: "push.test", lane: "background" }]);
    await expect(as(db, "authenticated", ALICE,
      `insert into public.jobs (user_id, kind, lane) values ('${ALICE}', 'push.test', 'background')`)).rejects.toThrow();
  });

  it("adds fired_at to reminders", async () => {
    const r = await db.query("select column_name from information_schema.columns where table_name = 'reminders' and column_name = 'fired_at'");
    expect(r.rows).toHaveLength(1);
  });
});

// ---------- 12-hour times ----------
describe("12-hour times everywhere", () => {
  const TZ = APP_SETTINGS.timeZone;
  it("formats AM/PM in English and ص/م in Arabic", () => {
    expect(clock12(new Date("2026-11-14T21:05:00Z"), "en", TZ)).toBe("12:05 AM");
    expect(clock12(new Date("2026-11-14T09:00:00Z"), "en", TZ)).toBe("12:00 PM");
    expect(clock12(new Date("2026-11-14T16:30:00Z"), "ar", TZ)).toBe("7:30 م");
    expect(clock12(new Date("2026-11-14T04:00:00Z"), "ar", TZ)).toBe("7:00 ص");
    expect(hm12(23, 59, "en")).toBe("11:59 PM");
  });

  it("turns the brief picker's hour, minute and AM/PM into the stored time and back", () => {
    expect(joinHHMM(7, 0, false)).toBe("07:00");
    expect(joinHHMM(12, 0, false)).toBe("00:00");
    expect(joinHHMM(12, 30, true)).toBe("12:30");
    expect(joinHHMM(7, 45, true)).toBe("19:45");
    expect(splitHHMM("19:45")).toEqual({ hour12: 7, minute: 45, pm: true });
    expect(splitHHMM("00:15")).toEqual({ hour12: 12, minute: 15, pm: false });
    expect(() => joinHHMM(13, 0, false)).toThrow();
  });
});

// ---------- the worker and the app agree on prayer times ----------
describe("prayer times shared with the PC worker", () => {
  const fixture = JSON.parse(readFileSync(resolve(process.cwd(), "../../tests/fixtures/snafi_prayer_times.json"), "utf8")) as {
    city: { latitude: number; longitude: number }; days: Record<string, Record<string, string>>;
  };

  it("adhan still gives the times the worker is tested against", () => {
    expect(fixture.city).toMatchObject({ latitude: APP_SETTINGS.city.latitude, longitude: APP_SETTINGS.city.longitude });
    for (const [day, expected] of Object.entries(fixture.days)) {
      const [y, m, d] = day.split("-").map(Number);
      const got = prayerTimesFor(APP_SETTINGS.city, y, m, d);
      for (const [prayer, iso] of Object.entries(expected)) {
        expect([day, prayer, got[prayer as keyof typeof got].toISOString()]).toEqual([day, prayer, iso]);
      }
    }
  });

  it("the worker's Ramadan table matches the Umm al-Qura calendar", () => {
    const source = readFileSync(resolve(process.cwd(), "../../src/snafi_worker/proactive/prayer.py"), "utf8");
    const pairs = [...source.matchAll(/\("(\d{4}-\d{2}-\d{2})", "(\d{4}-\d{2}-\d{2})"\)/g)].map((m) => [m[1], m[2]]);
    expect(pairs.length).toBeGreaterThanOrEqual(10);
    const tz = APP_SETTINGS.timeZone;
    const at = (iso: string, deltaDays = 0) => new Date(new Date(`${iso}T09:00:00Z`).getTime() + deltaDays * 86_400_000);
    for (const [first, last] of pairs) {
      expect([first, hijriMonth(at(first), tz)]).toEqual([first, 9]);
      expect([first, hijriMonth(at(first, -1), tz)]).toEqual([first, 8]);
      expect([last, hijriMonth(at(last), tz)]).toEqual([last, 9]);
      expect([last, hijriMonth(at(last, 1), tz)]).toEqual([last, 10]);
    }
  });
});

// ---------- the service worker: nothing private on the lock screen ----------
describe("Web Push in the service worker", () => {
  function loadWorker() {
    const listeners: Record<string, (event: unknown) => void> = {};
    const shown: { title: string; options: Record<string, unknown> }[] = [];
    const self = {
      addEventListener: (name: string, fn: (event: unknown) => void) => { listeners[name] = fn; },
      registration: { showNotification: (title: string, options: Record<string, unknown>) => { shown.push({ title, options }); return Promise.resolve(); } },
      location: { origin: "https://snafi.example.com" },
      clients: { matchAll: async () => [], openWindow: vi.fn(async () => null), claim: async () => undefined },
      skipWaiting: async () => undefined,
    };
    runInNewContext(readFileSync(resolve(process.cwd(), "public/sw.js"), "utf8"), { self, caches: {}, URL, fetch: () => null });
    const push = (data: unknown) => listeners.push({ data: { json: () => data }, waitUntil: () => undefined });
    return { listeners, shown, push, self };
  }

  it("shows fixed text for each kind, in the language given, whatever else the push carries", () => {
    const { shown, push } = loadWorker();
    push({ k: "reminder", l: "en", n: "33333333-3333-4333-8333-333333333333", title: "Call the bank about the loan", body: "secret" });
    push({ k: "mail", l: "ar", n: "33333333-3333-4333-8333-333333333333" });
    push({ k: "<script>", l: "xx" });
    push(null);
    expect(shown.map((s) => [s.title, s.options.body])).toEqual([
      ["Snafi", "You have a reminder"], ["سنافي", "لدى أحمد جديد لك"],
      ["Snafi", "Ahmad has an update for you"], ["Snafi", "Ahmad has an update for you"]]);
    expect(JSON.stringify(shown)).not.toMatch(/bank|secret|script/);
    expect(shown[1].options).toMatchObject({ dir: "rtl", lang: "ar", tag: "33333333-3333-4333-8333-333333333333" });
  });

  it("opens Today when tapped", async () => {
    const { listeners, self } = loadWorker();
    let done: Promise<unknown> = Promise.resolve();
    listeners.notificationclick({ notification: { close: vi.fn() }, waitUntil: (p: Promise<unknown>) => { done = p; } });
    await done;
    expect(self.clients.openWindow).toHaveBeenCalledWith("/today");
  });
});

// ---------- the app's own checks ----------
describe("push keys and settings in the app", () => {
  it("reads the VAPID public key and refuses anything else", () => {
    const key = "B" + "x".repeat(86);
    expect(readVapidPublicKey({ NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY: key })).toBe(key);
    expect(readVapidPublicKey({})).toBeNull();
    expect(() => readVapidPublicKey({ NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY: "q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94" })).toThrow(ConfigError);
  });

  it("refuses push addresses outside the push services before they leave the app", () => {
    for (const [endpoint, ok] of ENDPOINTS) {
      const call = () => checkPushKeys({ endpoint, p256dh: P256DH, auth: AUTH });
      if (ok) expect(call()).toBeTruthy();
      else expect(call).toThrow();
    }
    expect(toBase64Url("ab+/cd==")).toBe("ab-_cd");
  });

  it("memory mailbox mirrors the rules: own cards, read once, settings in range, one test job", async () => {
    const store = createMemoryStore();
    const alice = new MemoryMailboxAdapter(store, ALICE);
    const bob = new MemoryMailboxAdapter(store, BOB);
    expect(await alice.settings()).toEqual(DEFAULT_SETTINGS);
    await expect(alice.saveSettings({ ...DEFAULT_SETTINGS, dailyCap: 0 })).rejects.toThrow();
    await alice.saveSettings({ pushEnabled: true, briefTime: "19:30", dailyCap: 5, lang: "ar" });
    expect(await bob.settings()).toEqual(DEFAULT_SETTINGS);
    store.cards.push({ id: "44444444-4444-4444-8444-444444444444", userId: ALICE, kind: "reminder", title: "Reminder",
      body: "Call", createdAt: "2026-11-14T09:00:00Z" });
    expect(await bob.cards()).toEqual([]);
    await bob.markCardRead("44444444-4444-4444-8444-444444444444"); // not Bob's card: nothing changes
    expect((await alice.cards())[0].readAt).toBeNull();
    await alice.markCardRead("44444444-4444-4444-8444-444444444444");
    expect((await alice.cards())[0].readAt).not.toBeNull();
    // A card dismissed before the Inbox existed stays hidden (AC-10).
    store.cards[0].dismissed = true;
    expect(await alice.cards()).toEqual([]);
    await alice.requestTestPush();
    await alice.requestTestPush();
    expect(store.jobs.filter((j) => j.kind === "push.test")).toHaveLength(1);
  });
});

// ---------- the screens ----------
describe("Settings screen", () => {
  const t = messages("en").settings;
  const ok = async () => ({ ok: true });

  it("shows the brief time with AM/PM and saves it as the 24-hour value", async () => {
    const save = vi.fn(ok);
    render(<SettingsForm initial={{ pushEnabled: false, briefTime: "07:00", dailyCap: 10, lang: "en" } as Settings} lang="en" t={t}
      publicKey={null} save={save} subscribe={ok} unsubscribe={ok} test={ok} />);
    expect(screen.getByLabelText("Hour")).toHaveValue("7");
    expect(screen.getByRole("button", { name: "AM" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.change(screen.getByLabelText("Hour"), { target: { value: "9" } });
    fireEvent.change(screen.getByLabelText("Minute"), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "PM" }));
    fireEvent.change(screen.getByLabelText("Daily limit"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith({ pushEnabled: false, briefTime: "21:30", dailyCap: 4 }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("refuses a cap outside 1 to 50 and says when push is not set up", () => {
    render(<SettingsForm initial={DEFAULT_SETTINGS} lang="en" t={t} publicKey={null} save={ok} subscribe={ok} unsubscribe={ok} test={ok} />);
    fireEvent.change(screen.getByLabelText("Daily limit"), { target: { value: "51" } });
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(screen.getByTestId("push-not-set-up")).toBeInTheDocument();
  });

  it("shows ص and م in Arabic", () => {
    render(<SettingsForm initial={{ ...DEFAULT_SETTINGS, briefTime: "19:00" }} lang="ar" t={messages("ar").settings}
      publicKey={null} save={ok} subscribe={ok} unsubscribe={ok} test={ok} />);
    expect(screen.getByRole("button", { name: "م" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "ص" })).toHaveAttribute("aria-pressed", "false");
  });
});

describe("Ahmad's cards", () => {
  it("are real; Today shows one of them as Ahmad's message with a 12-hour time, without its body and with no Dismiss", async () => {
    const card = { id: "44444444-4444-4444-8444-444444444444", kind: "reminder" as const, title: "Reminder",
      body: "Call the bank\nSet for 3:00 PM", createdAt: "2026-11-14T12:00:00Z", readAt: null };
    const source = new LiveTodaySource(async () => [], async () => null, async () => [card]);
    const now = new Date("2026-11-14T13:00:00Z");
    const today = await source.getToday("en", now);
    expect(today.sample).toBe(false);
    expect(today.cards).toEqual([card]);
    render(<TodayView lang="en" hour={16} today={today} now={now} />);
    const message = screen.getByTestId("ahmad-message");
    expect(message).toHaveTextContent("Reminder");
    expect(message).toHaveTextContent("3:00 PM");
    expect(message).toHaveAttribute("href", "/inbox?open=44444444-4444-4444-8444-444444444444");
    expect(message).not.toHaveTextContent("Call the bank");
    expect(screen.queryByTestId("ahmad-card")).toBeNull();
    expect(screen.queryByTestId("dismiss-card")).toBeNull(); // AC-10
  });
});
