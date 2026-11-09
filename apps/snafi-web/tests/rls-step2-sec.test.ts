// @vitest-environment node
/** SEC-12 and SEC-13 in the database: approve exactly what was shown, cards expire, run once. */
import type { PGlite } from "@electric-sql/pglite";
import { beforeAll, describe, expect, it } from "vitest";
import { ALICE, as, CONV, freshDb } from "./helpers/db";

let db: PGlite;
const HASH = "b".repeat(64);

async function card(extra = "") {
  const r = await as<{ id: string }>(db, "service_role", null,
    `insert into public.approvals (user_id, conversation_id, tool, summary, args, args_hash ${extra ? ", expires_at" : ""})
     values ($1, $2, 'send_test_message', 'Test send', '{"text":"hi"}', $3 ${extra ? `, ${extra}` : ""}) returning id`,
    [ALICE, CONV, HASH]);
  return r.rows[0].id;
}

beforeAll(async () => {
  db = await freshDb();
}, 60_000);

describe("approvals are bound to the arguments shown (SEC-13)", () => {
  it("approve only with the matching hash", async () => {
    const id = await card();
    await expect(as(db, "authenticated", ALICE, "select public.decide_approval($1, 'approved', $2)", [id, "c".repeat(64)]))
      .rejects.toThrow(/changed after it was shown/);
    await expect(as(db, "authenticated", ALICE, "select public.decide_approval($1, 'approved', null)", [id]))
      .rejects.toThrow(/changed after it was shown/);
    const ok = await as<{ status: string }>(db, "authenticated", ALICE,
      "select status from public.decide_approval($1, 'approved', $2)", [id, HASH]);
    expect(ok.rows[0].status).toBe("approved");
  });

  it("a card with no hash can never be approved, only rejected", async () => {
    const r = await as<{ id: string }>(db, "service_role", null,
      "insert into public.approvals (user_id, conversation_id, tool, summary) values ($1, $2, 'send_test_message', 'x') returning id", [ALICE, CONV]);
    await expect(as(db, "authenticated", ALICE, "select public.decide_approval($1, 'approved', '')", [r.rows[0].id]))
      .rejects.toThrow(/changed after it was shown/);
    const no = await as<{ status: string }>(db, "authenticated", ALICE,
      "select status from public.decide_approval($1, 'rejected', null)", [r.rows[0].id]);
    expect(no.rows[0].status).toBe("rejected");
  });

  it("expires 24 hours after it was made, and an expired card queues nothing", async () => {
    const fresh = await card();
    const exp = await db.query<{ hours: number }>(
      "select round(extract(epoch from (expires_at - created_at)) / 3600)::int hours from public.approvals where id = $1", [fresh]);
    expect(exp.rows[0].hours).toBe(24);
    const old = await card("now() - interval '1 minute'");
    const before = await db.query<{ n: number }>("select count(*)::int n from public.jobs");
    const r = await as<{ status: string }>(db, "authenticated", ALICE,
      "select status from public.decide_approval($1, 'approved', $2)", [old, HASH]);
    expect(r.rows[0].status).toBe("expired");
    const after = await db.query<{ n: number }>("select count(*)::int n from public.jobs");
    expect(after.rows[0].n).toBe(before.rows[0].n);
  });
});

describe("an approved card is claimed once (SEC-12)", () => {
  it("only one conditional update can move approved -> executing", async () => {
    const id = await card();
    await as(db, "authenticated", ALICE, "select public.decide_approval($1, 'approved', $2)", [id, HASH]);
    const claim = "update public.approvals set status = 'executing' where id = $1 and status = 'approved' returning id";
    const first = await as(db, "service_role", null, claim, [id]);
    const second = await as(db, "service_role", null, claim, [id]);
    expect(first.rows).toHaveLength(1);
    expect(second.rows).toHaveLength(0);
  });

  it("the app still cannot change a card directly", async () => {
    const id = await card();
    await expect(as(db, "authenticated", ALICE, "update public.approvals set status = 'executing' where id = $1", [id]))
      .rejects.toThrow(/permission denied/);
  });
});
