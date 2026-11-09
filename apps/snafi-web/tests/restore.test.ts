// @vitest-environment node
/**
 * The backup is usable: the worker's real backup and restore code (Python) writes a backup
 * of every Snafi table, turns it into SQL, and that SQL loads into an empty Postgres
 * (PGlite) after both migrations, with every row back.
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { ALICE, freshDb } from "./helpers/db";

const REPO = resolve(process.cwd(), "..", "..");
const PYTHON = [join(REPO, ".venv", "Scripts", "python.exe"), join(REPO, ".venv", "bin", "python")].find(existsSync) ?? "python";
const work = mkdtempSync(join(tmpdir(), "snafi-restore-"));

const MAKE_BACKUP = `
import sys
from pathlib import Path
from src.snafi_worker import backup, restore
from src.snafi_worker.store.memory import MemoryStore
owner, folder = sys.argv[1], Path(sys.argv[2])
s = MemoryStore()
job = s.insert("jobs", {"user_id": owner, "kind": "chat.reply", "conversation_id": "33333333-3333-4333-8333-333333333333", "payload": {"message_id": "m"}})
card = s.insert("approvals", {"user_id": owner, "conversation_id": "33333333-3333-4333-8333-333333333333", "job_id": job["id"], "tool": "send_test_message", "args": {"text": "x"}, "summary": "Test send"})
s.insert("messages", {"user_id": owner, "conversation_id": "33333333-3333-4333-8333-333333333333", "role": "user", "body": "It's مرحبا", "lang": "ar", "job_id": job["id"]})
s.insert("messages", {"user_id": owner, "conversation_id": "33333333-3333-4333-8333-333333333333", "role": "assistant", "body": "card", "lang": "en", "approval_id": card["id"], "meta": {"kind": "approval_card"}})
s.insert("action_log", {"user_id": owner, "conversation_id": "33333333-3333-4333-8333-333333333333", "job_id": job["id"], "tool": "add_note", "level": 2, "summary": "Saved a note", "status": "done", "undoable": True, "undo": {"table": "notes", "id": "x"}})
s.insert("notes", {"user_id": owner, "body": "drawings"})
s.insert("reminders", {"user_id": owner, "body": "renew", "due_at": "2026-11-10T09:00:00+03:00"})
s.insert("facts", {"user_id": owner, "body": "prefers Arabic"})
s.upsert("worker_status", {"user_id": owner, "worker_id": "pc", "lanes": {"chat": {"alive": True}}}, "user_id")
out = backup.run_backup(s, folder, owner, "pc", "Asia/Riyadh", 30, signing_key="k" * 64)
assert out["ok"], out
(folder / "restore.sql").write_text(restore.to_sql(restore.load(folder / out["file"], "k" * 64)), encoding="utf-8")
`;

afterAll(() => rmSync(work, { recursive: true, force: true }));

describe("backup and restore", () => {
  it("loads a real backup into an empty database with every row back", async () => {
    execFileSync(PYTHON, ["-I", "-c", `import sys; sys.path.insert(0, ${JSON.stringify(REPO)});` + MAKE_BACKUP, ALICE, work], {
      cwd: REPO, stdio: "pipe",
    });
    const sql = readFileSync(join(work, "restore.sql"), "utf8");
    const db = await freshDb();
    await db.exec(sql);
    const counts = await db.query<{ t: string; n: number }>(`
      select 'jobs' t, count(*)::int n from public.jobs union all
      select 'approvals', count(*)::int from public.approvals union all
      select 'messages', count(*)::int from public.messages union all
      select 'action_log', count(*)::int from public.action_log union all
      select 'notes', count(*)::int from public.notes union all
      select 'reminders', count(*)::int from public.reminders union all
      select 'facts', count(*)::int from public.facts union all
      select 'worker_status', count(*)::int from public.worker_status`);
    expect(Object.fromEntries(counts.rows.map((r) => [r.t, r.n]))).toEqual({
      jobs: 1, approvals: 1, messages: 2, action_log: 1, notes: 1, reminders: 1, facts: 1, worker_status: 1,
    });
    const msg = await db.query<{ body: string }>("select body from public.messages where role = 'user'");
    expect(msg.rows[0].body).toBe("It's مرحبا");
    const card = await db.query<{ meta: { kind: string } }>("select meta from public.messages where approval_id is not null");
    expect(card.rows[0].meta.kind).toBe("approval_card");
  }, 60_000);
});
