// @vitest-environment node
/** Phase 1 (SEC-3 headers, SEC-4 throttle, fixed site URL) and the phase 2 chat send fix. */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { PGlite } from "@electric-sql/pglite";
import { NextRequest } from "next/server";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { MemoryThrottleAdapter } from "@/adapters/throttle/memory";
import { ConfigError, readSiteUrl } from "@/config/env";
import { contentSecurityPolicy, HSTS, newNonce } from "@/core/security-headers";
import { ALICE, as, BOB, CONV, freshDb, migrationFiles } from "./helpers/db";

vi.mock("server-only", () => ({}));
const { throttleKeys, throttlePepper, trustedClientIp } = await import("@/core/signin-throttle");

const read = (p: string) => readFileSync(fileURLToPath(new URL(`../${p}`, import.meta.url)), "utf8");
const KEY = (c: string) => c.repeat(64);

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("phase 2: a chat message and its reply job are saved together (send_chat)", () => {
  let db: PGlite;
  beforeAll(async () => {
    db = await freshDb();
  }, 60_000);

  it("saves the message and queues exactly one chat.reply for it", async () => {
    const r = await as<{ id: string; role: string }>(db, "authenticated", ALICE,
      "select id, role from public.send_chat($1, 'hello', 'en')", [CONV]);
    expect(r.rows[0].role).toBe("user");
    const jobs = await as<{ kind: string; lane: string; payload: { message_id: string } }>(db, "authenticated", ALICE,
      "select kind, lane, payload from public.jobs where payload->>'message_id' = $1", [r.rows[0].id]);
    expect(jobs.rows).toEqual([{ kind: "chat.reply", lane: "chat", payload: { message_id: r.rows[0].id } }]);
    // RLS still applies: Bob sees neither row.
    const bob = await as(db, "authenticated", BOB, "select 1 from public.messages where id = $1", [r.rows[0].id]);
    expect(bob.rows).toHaveLength(0);
  });

  it("refuses anonymous callers", async () => {
    await expect(as(db, "anon", null, "select public.send_chat($1, 'hi', 'en')", [CONV])).rejects.toThrow(/permission denied/);
  });

  it("leaves no message behind when the job cannot be queued", async () => {
    const broken = await freshDb();
    await broken.exec("revoke insert (conversation_id) on public.jobs from authenticated");
    await expect(as(broken, "authenticated", ALICE, "select public.send_chat($1, 'lost?', 'en')", [CONV]))
      .rejects.toThrow(/permission denied/);
    const left = await as(broken, "authenticated", ALICE, "select 1 from public.messages");
    expect(left.rows).toHaveLength(0);
  }, 60_000);

  it("is what the Supabase adapter calls, in one request", () => {
    const src = read("src/adapters/mailbox/supabase.ts");
    expect(src).toContain('rpc("send_chat"');
    expect(src).not.toMatch(/from\("jobs"\)/);
  });
});

describe("SEC-4: sign-in throttle in the database (migration 0005)", () => {
  let db: PGlite;
  beforeAll(async () => {
    db = await freshDb();
  }, 60_000);

  const wait = async (keys: string[]) =>
    (await as<{ w: number }>(db, "anon", null, "select public.signin_wait_seconds($1) as w", [keys])).rows[0].w;
  const fail = (keys: string[]) => as(db, "anon", null, "select public.signin_record_failure($1)", [keys]);

  it("allows 4 wrong tries and blocks after the 5th for about 15 minutes", async () => {
    const k = [KEY("a")];
    for (let i = 0; i < 4; i++) await fail(k);
    expect(await wait(k)).toBe(0);
    await fail(k);
    const w = await wait(k);
    expect(w).toBeGreaterThan(14 * 60);
    expect(w).toBeLessThanOrEqual(15 * 60);
  });

  it("blocks on either key: a blocked email stays blocked from a new IP", async () => {
    expect(await wait([KEY("a"), KEY("b")])).toBeGreaterThan(0);
    expect(await wait([KEY("b")])).toBe(0);
  });

  it("frees a key once its failures are older than 15 minutes", async () => {
    await db.exec(`update public.signin_failures set created_at = now() - interval '16 minutes' where key_hash = '${KEY("a")}'`);
    expect(await wait([KEY("a")])).toBe(0);
  });

  it("keeps the table hidden from the app", async () => {
    await expect(as(db, "anon", null, "select * from public.signin_failures")).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE, "delete from public.signin_failures")).rejects.toThrow(/permission denied/);
  });

  it("refuses anything but 1 or 2 hex keys", async () => {
    for (const bad of [[], ["khalid@example.com"], [KEY("a"), KEY("b"), KEY("c")], [KEY("A")]]) {
      await expect(fail(bad)).rejects.toThrow(/invalid throttle keys/);
      await expect(wait(bad)).rejects.toThrow(/invalid throttle keys/);
    }
  });

  it("caps rows per key and deletes rows older than a day", async () => {
    const k = [KEY("c")];
    for (let i = 0; i < 25; i++) await fail(k);
    const n = await db.query<{ n: number }>(`select count(*)::int as n from public.signin_failures where key_hash = '${KEY("c")}'`);
    expect(n.rows[0].n).toBe(20);
    await db.exec("update public.signin_failures set created_at = now() - interval '2 days'");
    await fail([KEY("d")]);
    const all = await db.query<{ n: number }>("select count(*)::int as n from public.signin_failures");
    expect(all.rows[0].n).toBe(1);
  });

  it("is applied after the earlier migrations", () => {
    expect(migrationFiles().slice(-2)).toEqual(["0004_send_chat.sql", "0005_signin_throttle.sql"]);
  });
});

describe("SEC-4: throttle keys and the in-memory store", () => {
  it("uses the same rule as the database", async () => {
    let now = 1_000_000;
    const store = new MemoryThrottleAdapter(() => now);
    const k = [KEY("e")];
    for (let i = 0; i < 4; i++) await store.recordFailure(k);
    expect(await store.waitSeconds(k)).toBe(0);
    await store.recordFailure(k);
    expect(await store.waitSeconds(k)).toBe(900);
    now += 901_000;
    expect(await store.waitSeconds(k)).toBe(0);
  });

  it("never sends the email or IP, only keyed hashes that differ per secret", () => {
    const pepper = "x".repeat(32);
    const keys = throttleKeys(pepper, " Khalid@Example.com ", "203.0.113.9");
    expect(keys).toHaveLength(2);
    for (const k of keys) expect(k).toMatch(/^[0-9a-f]{64}$/);
    expect(keys.join()).not.toContain("khalid");
    expect(throttleKeys(pepper, "khalid@example.com", null)).toEqual([keys[0]]);
    expect(throttleKeys("y".repeat(32), "khalid@example.com", null)[0]).not.toBe(keys[0]);
  });

  it("trusts the client IP only on Vercel", () => {
    const get = (n: string) => (n === "x-real-ip" ? "203.0.113.9" : null);
    expect(trustedClientIp(get, {})).toBeNull();
    expect(trustedClientIp(get, { VERCEL: "1" })).toBe("203.0.113.9");
    expect(trustedClientIp(() => "<script>", { VERCEL: "1" })).toBeNull();
  });

  it("needs SNAFI_THROTTLE_SECRET outside a development server", () => {
    expect(() => throttlePepper({}, "production")).toThrow(ConfigError);
    expect(() => throttlePepper({ SNAFI_THROTTLE_SECRET: "short" }, "production")).toThrow(ConfigError);
    expect(throttlePepper({ SNAFI_THROTTLE_SECRET: "s".repeat(40) }, "production")).toBe("s".repeat(40));
    expect(throttlePepper({}, "development")).toMatch(/^[0-9a-f]{64}$/);
  });

  it("is checked before Supabase and records only wrong passwords", () => {
    const src = read("src/app/sign-in/actions.ts");
    expect(src.indexOf("waitSeconds()")).toBeLessThan(src.indexOf("signInWithPassword("));
    expect(src).toMatch(/result\.error === "invalid"[\s\S]*recordFailure\(\)/);
    expect(src).toMatch(/catch \{\s*return \{ error: "unavailable" \}/);
  });
});

describe("fixed site URL for redirects", () => {
  it("prefers SNAFI_SITE_URL, then Vercel's own address", () => {
    expect(readSiteUrl({ SNAFI_SITE_URL: "https://snafi.example.com" }, "production")).toBe("https://snafi.example.com");
    expect(readSiteUrl({ VERCEL_ENV: "production", VERCEL_PROJECT_PRODUCTION_URL: "snafi.vercel.app" }, "production"))
      .toBe("https://snafi.vercel.app");
    expect(readSiteUrl({ VERCEL_ENV: "preview", VERCEL_BRANCH_URL: "snafi-git-x.vercel.app", VERCEL_URL: "snafi-abc.vercel.app" }, "production"))
      .toBe("https://snafi-git-x.vercel.app");
  });

  it("refuses plain HTTP off localhost, paths, and a production build with no address", () => {
    expect(() => readSiteUrl({ SNAFI_SITE_URL: "http://snafi.example.com" }, "production")).toThrow(ConfigError);
    expect(() => readSiteUrl({ SNAFI_SITE_URL: "https://snafi.example.com/x" }, "production")).toThrow(ConfigError);
    expect(() => readSiteUrl({}, "production")).toThrow(ConfigError);
    expect(readSiteUrl({ SNAFI_SITE_URL: "http://127.0.0.1:3000" }, "production")).toBe("http://127.0.0.1:3000");
    expect(readSiteUrl({}, "development")).toBeNull();
  });

  it("redirects to the site address, not the Host the request claims, with the CSP set", async () => {
    vi.stubEnv("SNAFI_SITE_URL", "https://snafi.example.com");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "");
    const { proxy } = await import("@/proxy");
    const res = await proxy(new NextRequest("https://evil.example.net/today", { headers: { host: "evil.example.net" } }));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe("https://snafi.example.com/sign-in");
    expect(res.headers.get("content-security-policy")).toMatch(/frame-ancestors 'none'/);
  });

  it("fails closed when a production build has no site address", async () => {
    vi.stubEnv("SNAFI_SITE_URL", "");
    const { proxy } = await import("@/proxy");
    const res = await proxy(new NextRequest("https://evil.example.net/today"));
    expect(res.status).toBe(500);
    expect(res.headers.get("location")).toBeNull();
  });
});

describe("SEC-3: Content-Security-Policy and HSTS", () => {
  it("is nonce-based and strict in production", () => {
    const nonce = newNonce();
    expect(newNonce()).not.toBe(nonce);
    const csp = contentSecurityPolicy(nonce, false);
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain(`script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`);
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("upgrade-insecure-requests");
    expect(csp).not.toContain("unsafe-eval");
    expect(csp).not.toMatch(/script-src[^;]*unsafe-inline/);
  });

  it("allows eval only on a development server, and refuses a malformed nonce", () => {
    expect(contentSecurityPolicy(newNonce(), true)).toContain("'unsafe-eval'");
    expect(() => contentSecurityPolicy("abc'; script-src *", false)).toThrow();
  });

  it("sends HSTS on every response", () => {
    expect(HSTS).toMatch(/^max-age=63072000; includeSubDomains$/);
    const config = read("next.config.ts");
    expect(config).toContain('{ key: "Strict-Transport-Security", value: HSTS }');
    expect(config).toContain('source: "/:path*", headers: securityHeaders');
  });
});
