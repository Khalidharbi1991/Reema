// @vitest-environment node
/** Step 2 tables and functions: each user sees only their own rows; the app changes nothing directly. */
import type { PGlite } from "@electric-sql/pglite";
import { beforeAll, describe, expect, it } from "vitest";
import { ALICE, as, BOB, CONV, freshDb } from "./helpers/db";

let db: PGlite;
const HASH = "a".repeat(64);
const STEP2_TABLES = ["approvals", "action_log", "notes", "reminders", "facts", "worker_status"];

async function seedApproval(user = ALICE) {
  const r = await as<{ id: string }>(db, "service_role", null,
    "insert into public.approvals (user_id, conversation_id, tool, summary, args_hash) values ($1, $2, 'send_test_message', 'Test send', $3) returning id",
    [user, CONV, HASH]);
  return r.rows[0].id;
}

async function seedAction(user = ALICE, undoable = true) {
  const r = await as<{ id: string }>(db, "service_role", null,
    `insert into public.action_log (user_id, conversation_id, tool, level, summary, status, undoable)
     values ($1, $2, 'add_note', 2, 'Saved a note', 'done', $3) returning id`, [user, CONV, undoable]);
  return r.rows[0].id;
}

beforeAll(async () => {
  db = await freshDb();
}, 60_000);

describe("step 2 tables", () => {
  it("all have RLS forced", async () => {
    const r = await db.query<{ relname: string; relrowsecurity: boolean; relforcerowsecurity: boolean }>(
      "select relname, relrowsecurity, relforcerowsecurity from pg_class where relname = any($1) order by relname", [STEP2_TABLES]);
    expect(r.rows).toHaveLength(STEP2_TABLES.length);
    expect(r.rows.every((x) => x.relrowsecurity && x.relforcerowsecurity)).toBe(true);
  });

  it("give anonymous visitors nothing and signed-in users read-only access", async () => {
    for (const t of STEP2_TABLES) {
      await expect(as(db, "anon", null, `select * from public.${t}`)).rejects.toThrow(/permission denied/);
      await expect(as(db, "authenticated", ALICE, `insert into public.${t} (user_id) values ('${ALICE}')`)).rejects.toThrow(/permission denied/);
      await expect(as(db, "authenticated", ALICE, `delete from public.${t}`)).rejects.toThrow(/permission denied/);
    }
  });

  it("show each user only their own rows", async () => {
    await as(db, "service_role", null, "insert into public.notes (user_id, body) values ($1, 'alice note'), ($2, 'bob note')", [ALICE, BOB]);
    const mine = await as<{ body: string }>(db, "authenticated", ALICE, "select body from public.notes");
    expect(mine.rows.map((r) => r.body)).toEqual(["alice note"]);
  });
});

describe("jobs from the app", () => {
  it("may only be chat replies in the chat lane", async () => {
    const ok = await as<{ lane: string; kind: string }>(db, "authenticated", ALICE,
      "insert into public.jobs (kind, payload, conversation_id) values ('chat.reply', '{}', $1) returning lane, kind", [CONV]);
    expect(ok.rows[0]).toEqual({ lane: "chat", kind: "chat.reply" });
    await expect(as(db, "authenticated", ALICE, "insert into public.jobs (kind) values ('approval.resume')")).rejects.toThrow(/row-level security/);
    await expect(as(db, "authenticated", ALICE, "insert into public.jobs (kind, lane) values ('chat.reply', 'background')")).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE, "insert into public.jobs (kind, attempts) values ('chat.reply', 5)")).rejects.toThrow(/permission denied/);
  });
});

describe("decide_approval", () => {
  it("lets the owner approve once and queues the follow-up job", async () => {
    const id = await seedApproval();
    const r = await as<{ status: string }>(db, "authenticated", ALICE, "select status from public.decide_approval($1, 'approved', $2)", [id, HASH]);
    expect(r.rows[0].status).toBe("approved");
    const jobs = await as<{ kind: string; payload: { approval_id: string } }>(db, "authenticated", ALICE,
      "select kind, payload from public.jobs where kind = 'approval.resume'");
    expect(jobs.rows.map((j) => j.payload.approval_id)).toContain(id);
    await expect(as(db, "authenticated", ALICE, "select public.decide_approval($1, 'rejected', $2)", [id, HASH])).rejects.toThrow(/no pending approval/);
  });

  it("refuses someone else's approval, anonymous callers and odd decisions", async () => {
    const id = await seedApproval();
    await expect(as(db, "authenticated", BOB, "select public.decide_approval($1, 'approved', $2)", [id, HASH])).rejects.toThrow(/no pending approval/);
    await expect(as(db, "anon", null, "select public.decide_approval($1, 'approved', $2)", [id, HASH])).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE, "select public.decide_approval($1, 'executed', $2)", [id, HASH])).rejects.toThrow(/approved or rejected/);
  });

  it("cannot be bypassed by updating the table directly", async () => {
    const id = await seedApproval();
    await expect(as(db, "authenticated", ALICE, "update public.approvals set status = 'approved' where id = $1", [id])).rejects.toThrow(/permission denied/);
  });
});

describe("request_undo", () => {
  it("queues one undo for the owner's undoable action", async () => {
    const id = await seedAction();
    await as(db, "authenticated", ALICE, "select public.request_undo($1)", [id]);
    const jobs = await as<{ payload: { action_id: string } }>(db, "authenticated", ALICE,
      "select payload from public.jobs where kind = 'action.undo'");
    expect(jobs.rows.map((j) => j.payload.action_id)).toContain(id);
    await expect(as(db, "authenticated", ALICE, "select public.request_undo($1)", [id])).rejects.toThrow(/nothing to undo/);
  });

  it("refuses other users and actions that cannot be undone", async () => {
    await expect(as(db, "authenticated", BOB, "select public.request_undo($1)", [await seedAction()])).rejects.toThrow(/nothing to undo/);
    await expect(as(db, "authenticated", ALICE, "select public.request_undo($1)", [await seedAction(ALICE, false)])).rejects.toThrow(/nothing to undo/);
  });
});

describe("claim_job", () => {
  it("is for the worker only, and takes one queued job per lane in order", async () => {
    await expect(as(db, "authenticated", ALICE, "select * from public.claim_job('chat', 'w')")).rejects.toThrow(/permission denied/);
    await as(db, "service_role", null, "update public.jobs set status = 'done' where status = 'queued'");
    await as(db, "service_role", null,
      "insert into public.jobs (user_id, kind, lane) values ($1, 'chat.reply', 'chat'), ($1, 'backup.run', 'background')", [ALICE]);
    const chat = await as<{ kind: string; status: string; attempts: number; claimed_by: string }>(db, "service_role", null,
      "select kind, status, attempts, claimed_by from public.claim_job('chat', 'pc-1')");
    expect(chat.rows).toEqual([{ kind: "chat.reply", status: "claimed", attempts: 1, claimed_by: "pc-1" }]);
    const again = await as(db, "service_role", null, "select * from public.claim_job('chat', 'pc-1')");
    expect(again.rows).toEqual([]);
    const bg = await as<{ kind: string }>(db, "service_role", null, "select kind from public.claim_job('background', 'pc-1')");
    expect(bg.rows[0].kind).toBe("backup.run");
  });

  it("waits until run_after for a retry", async () => {
    await as(db, "service_role", null,
      "insert into public.jobs (user_id, kind, lane, run_after) values ($1, 'chat.reply', 'chat', now() + interval '1 hour')", [ALICE]);
    const r = await as(db, "service_role", null, "select * from public.claim_job('chat', 'pc-1')");
    expect(r.rows).toEqual([]);
  });
});

describe("messages from the app", () => {
  it("still cannot carry an approval or worker metadata", async () => {
    await expect(as(db, "authenticated", ALICE,
      "insert into public.messages (conversation_id, role, body, meta) values ($1, 'user', 'x', '{\"a\":1}')", [CONV])).rejects.toThrow(/permission denied/);
  });
});
