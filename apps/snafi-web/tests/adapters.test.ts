// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { FakeAuthAdapter } from "@/adapters/auth/fake";
import { cleanCredentials } from "@/adapters/auth/validate";
import { createMemoryStore, MemoryMailboxAdapter } from "@/adapters/mailbox/memory";
import { MailboxError } from "@/adapters/mailbox/types";
import { PlaceholderTodaySource } from "@/adapters/today/placeholder";
import { tapFeedback } from "@/core/haptics";

const SRC = fileURLToPath(new URL("../src", import.meta.url));

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

describe("swappable rule", () => {
  it("imports Supabase only inside src/adapters", () => {
    const offenders = files(SRC)
      .filter((f) => /\.(ts|tsx)$/.test(f))
      .filter((f) => /from\s+["']@supabase\//.test(readFileSync(f, "utf8")))
      .map((f) => relative(SRC, f).split(sep).join("/"))
      .filter((f) => !f.startsWith("adapters/"));
    expect(offenders).toEqual([]);
  });

  it("never mentions a secret key in app code outside the guard", () => {
    const offenders = files(SRC)
      .filter((f) => /SERVICE_ROLE|SUPABASE_SECRET/i.test(readFileSync(f, "utf8")))
      .map((f) => relative(SRC, f).split(sep).join("/"))
      .filter((f) => f !== "config/env.ts"); // the guard that refuses such keys
    expect(offenders).toEqual([]);
  });
});

describe("auth adapter", () => {
  const account = { id: "u1", email: "owner@example.test", password: "correct horse" };

  it("signs in with the right password only, and signs out", async () => {
    const auth = new FakeAuthAdapter(account);
    expect(await auth.signInWithPassword("owner@example.test", "wrong")).toEqual({ ok: false, error: "invalid" });
    expect(await auth.currentUser()).toBeNull();
    const ok = await auth.signInWithPassword(" OWNER@example.test ", "correct horse");
    expect(ok.ok).toBe(true);
    expect((await auth.currentUser())?.id).toBe("u1");
    await auth.signOut();
    expect(await auth.currentUser()).toBeNull();
  });

  it("rejects empty or malformed input before any call", async () => {
    expect(cleanCredentials("", "x")).toBeNull();
    expect(cleanCredentials("not-an-email", "x")).toBeNull();
    expect(cleanCredentials("a@b.co", "")).toBeNull();
    expect(cleanCredentials(undefined, "x")).toBeNull();
    expect(cleanCredentials("a@b.co", "x".repeat(2000))).toBeNull();
    expect(await new FakeAuthAdapter(account).signInWithPassword("", "")).toEqual({ ok: false, error: "missing" });
  });
});

describe("mailbox adapter (memory)", () => {
  it("keeps each user's messages and jobs apart", async () => {
    const store = createMemoryStore();
    const alice = new MemoryMailboxAdapter(store, "alice");
    const bob = new MemoryMailboxAdapter(store, "bob");
    await alice.postUserMessage({ conversationId: "c", body: " مرحبا ", lang: "ar" });
    await bob.postUserMessage({ conversationId: "c", body: "hi", lang: "en" });
    const mine = await alice.listMessages("c");
    expect(mine.map((m) => [m.userId, m.role, m.body])).toEqual([["alice", "user", "مرحبا"]]);
    const job = await alice.enqueueJob({ kind: "chat.reply", payload: {} });
    expect(job.status).toBe("queued");
    expect(await bob.listJobs()).toEqual([]);
  });

  it("refuses signed-out use, empty or long messages and bad job kinds", async () => {
    const store = createMemoryStore();
    await expect(new MemoryMailboxAdapter(store, null).listJobs()).rejects.toThrow(MailboxError);
    const a = new MemoryMailboxAdapter(store, "a");
    await expect(a.postUserMessage({ conversationId: "c", body: "   ", lang: "en" })).rejects.toThrow(/empty/);
    await expect(a.postUserMessage({ conversationId: "c", body: "x".repeat(8001), lang: "en" })).rejects.toThrow(/too long/);
    await expect(a.enqueueJob({ kind: "DROP TABLE", payload: {} })).rejects.toThrow(/kind/);
  });
});

describe("Today source (placeholder)", () => {
  it("is marked as sample data in both languages", async () => {
    const src = new PlaceholderTodaySource();
    const now = new Date("2026-11-07T12:00:00Z");
    const en = await src.getToday("en", now);
    const ar = await src.getToday("ar", now);
    expect(en.placeholder && ar.placeholder).toBe(true);
    expect(en.gregorianDate).toContain("2026");
    expect(ar.gregorianDate).toMatch(/[؀-ۿ]/);
    expect(en.tasks.every((t) => t.title.startsWith("Sample"))).toBe(true);
    expect(ar.tasks.every((t) => t.title.startsWith("نموذج"))).toBe(true);
    expect(en.nextPrayer.progress).toBeGreaterThanOrEqual(0);
  });
});

describe("haptics", () => {
  it("vibrates where supported and is quiet elsewhere", () => {
    const calls: unknown[] = [];
    expect(tapFeedback({ vibrate: ((p: unknown) => (calls.push(p), true)) as Navigator["vibrate"] })).toBe(true);
    expect(calls).toEqual([12]);
    expect(tapFeedback({} as Navigator)).toBe(false);
    expect(tapFeedback(undefined)).toBe(false);
  });
});
