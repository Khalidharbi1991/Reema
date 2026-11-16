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

const A = "11111111-1111-4111-8111-111111111111";
const B = "22222222-2222-4222-8222-222222222222";

describe("mailbox adapter (memory)", () => {
  it("keeps each user's messages apart and queues a reply for each message", async () => {
    const store = createMemoryStore();
    const alice = new MemoryMailboxAdapter(store, A);
    const bob = new MemoryMailboxAdapter(store, B);
    await alice.sendChat({ conversationId: A, body: " مرحبا ", lang: "ar" });
    await bob.sendChat({ conversationId: B, body: "hi", lang: "en" });
    const mine = await alice.listMessages(A);
    expect(mine.map((m) => [m.userId, m.role, m.body])).toEqual([[A, "user", "مرحبا"]]);
    expect(await bob.listMessages(A)).toEqual([]);
    expect(store.jobs.map((j) => [j.userId, j.kind, j.payload.message_id])).toEqual([
      [A, "chat.reply", mine[0].id], [B, "chat.reply", expect.any(String)]]);
  });

  it("decides a pending card once, only for its owner, and queues the follow-up", async () => {
    const store = createMemoryStore();
    store.approvals.push({ id: B, userId: A, conversationId: A, tool: "send_test_message", args: { text: "hi" },
      argsHash: "a".repeat(64), summary: "Test send", status: "pending", createdAt: "", expiresAt: "2999-01-01T00:00:00Z" });
    const bob = new MemoryMailboxAdapter(store, B);
    await expect(bob.decideApproval(B, "approved", "a".repeat(64))).rejects.toThrow(/no pending/);
    const alice = new MemoryMailboxAdapter(store, A);
    expect((await alice.pendingApprovals()).map((c) => c.id)).toEqual([B]);
    await expect(alice.decideApproval(B, "approved", "b".repeat(64))).rejects.toThrow(/changed after it was shown/);
    expect((await alice.decideApproval(B, "approved", "a".repeat(64))).status).toBe("approved");
    await expect(alice.decideApproval(B, "rejected", "a".repeat(64))).rejects.toThrow(/no pending/);
    expect(store.jobs.at(-1)).toMatchObject({ kind: "approval.resume", payload: { approval_id: B } });
  });

  it("asks for Undo once, only on undoable actions", async () => {
    const store = createMemoryStore();
    store.actions.push({ id: A, userId: A, summary: "Saved a note", level: 2, status: "done", undoable: true, undoRequested: false });
    store.actions.push({ id: B, userId: A, summary: "Listed notes", level: 1, status: "done", undoable: false, undoRequested: false });
    const alice = new MemoryMailboxAdapter(store, A);
    await alice.requestUndo(A);
    await expect(alice.requestUndo(A)).rejects.toThrow(/nothing to undo/);
    await expect(alice.requestUndo(B)).rejects.toThrow(/nothing to undo/);
    expect(store.jobs.map((j) => j.kind)).toEqual(["action.undo"]);
  });

  it("refuses signed-out use, empty or long messages and bad ids", async () => {
    const store = createMemoryStore();
    await expect(new MemoryMailboxAdapter(store, null).listMessages(A)).rejects.toThrow(MailboxError);
    const a = new MemoryMailboxAdapter(store, A);
    await expect(a.sendChat({ conversationId: A, body: "   ", lang: "en" })).rejects.toThrow(/empty/);
    await expect(a.sendChat({ conversationId: A, body: "x".repeat(8001), lang: "en" })).rejects.toThrow(/too long/);
    await expect(a.sendChat({ conversationId: "not-an-id", body: "x", lang: "en" })).rejects.toThrow(/invalid id/);
    await expect(a.decideApproval("1; drop", "approved", "a".repeat(64))).rejects.toThrow(/invalid id/);
  });
});

describe("Today source (placeholder)", () => {
  it("is marked as sample data in both languages", async () => {
    const src = new PlaceholderTodaySource();
    const now = new Date("2026-11-07T12:00:00Z");
    const en = await src.getToday("en", now);
    const ar = await src.getToday("ar", now);
    expect([en.sample, ar.sample]).toEqual([true, true]);
    expect(en.gregorianDate).toContain("2026");
    expect(ar.gregorianDate).toMatch(/[؀-ۿ]/);
    expect(en.tasks.every((t) => t.title.startsWith("Sample"))).toBe(true);
    expect(ar.tasks.every((t) => t.title.startsWith("نموذج"))).toBe(true);
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
