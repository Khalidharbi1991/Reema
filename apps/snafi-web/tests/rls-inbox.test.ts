// @vitest-environment node
/** AC-11 in the database: migration 0009 (cards.read_at and mark_card_read), run in PGlite. */
import type { PGlite } from "@electric-sql/pglite";
import { beforeAll, describe, expect, it } from "vitest";
import { ALICE, as, BOB, freshDb, migrationFiles } from "./helpers/db";

let db: PGlite;

async function card(user: string, kind = "reminder") {
  const r = await as<{ id: string }>(db, "service_role", null,
    "insert into public.cards (user_id, kind, title, body) values ($1, $2, 'Reminder', 'Call the bank') returning id", [user, kind]);
  return r.rows[0].id;
}
const readAt = async (id: string) =>
  (await as<{ read_at: string | null }>(db, "service_role", null, "select read_at::text from public.cards where id = $1", [id])).rows[0].read_at;

beforeAll(async () => {
  db = await freshDb();
}, 60_000);

describe("AC-11: mark_card_read (migration 0009)", () => {
  it("is the migration after 0008 and adds a read time that starts empty", async () => {
    expect(migrationFiles()).toContain("0009_inbox_read.sql");
    expect(migrationFiles().indexOf("0009_inbox_read.sql")).toBe(migrationFiles().indexOf("0008_proactive.sql") + 1);
    expect(await readAt(await card(ALICE))).toBeNull();
  });

  it("marks the user's own card once, and a second call keeps the first time", async () => {
    const id = await card(ALICE);
    await as(db, "authenticated", ALICE, "select public.mark_card_read($1)", [id]);
    const first = await readAt(id);
    expect(first).not.toBeNull();
    // Move the first time into the past, so a second call that overwrote it would show.
    await as(db, "service_role", null, "update public.cards set read_at = read_at - interval '1 hour' where id = $1", [id]);
    const moved = await readAt(id);
    await as(db, "authenticated", ALICE, "select public.mark_card_read($1)", [id]);
    expect(await readAt(id)).toBe(moved);
    // The owner reads it back through the app's own select.
    const mine = await as<{ read_at: string | null }>(db, "authenticated", ALICE, "select read_at from public.cards where id = $1", [id]);
    expect(mine.rows[0].read_at).not.toBeNull();
  });

  it("changes nothing on another user's card, or for an id that does not exist", async () => {
    const id = await card(ALICE);
    await as(db, "authenticated", BOB, "select public.mark_card_read($1)", [id]);
    expect(await readAt(id)).toBeNull();
    await as(db, "authenticated", BOB, "select public.mark_card_read('99999999-9999-4999-8999-999999999999')");
    expect((await as(db, "authenticated", BOB, "select * from public.cards")).rows).toEqual([]);
  });

  it("changes only the read time: no other column of the card moves", async () => {
    const id = await card(ALICE, "mail");
    const row = async () => (await as(db, "service_role", null,
      "select user_id, notification_id, kind, title, body, created_at::text, dismissed_at from public.cards where id = $1", [id])).rows[0];
    const before = await row();
    await as(db, "authenticated", ALICE, "select public.mark_card_read($1)", [id]);
    expect(await row()).toEqual(before);
  });

  it("refuses anonymous and signed-out callers", async () => {
    const id = await card(ALICE);
    await expect(as(db, "anon", null, "select public.mark_card_read($1)", [id])).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", null, "select public.mark_card_read($1)", [id])).rejects.toThrow(/not signed in/);
    expect(await readAt(id)).toBeNull();
  });

  it("still gives the app no direct update, insert or delete on cards", async () => {
    const id = await card(ALICE);
    await expect(as(db, "authenticated", ALICE, "update public.cards set read_at = now() where id = $1", [id])).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE, "update public.cards set title = 'changed' where id = $1", [id])).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE,
      `insert into public.cards (user_id, kind, title, body) values ('${ALICE}', 'reminder', 'x', 'y')`)).rejects.toThrow(/permission denied/);
    await expect(as(db, "authenticated", ALICE, "delete from public.cards where id = $1", [id])).rejects.toThrow(/permission denied/);
    await expect(as(db, "anon", null, "select * from public.cards")).rejects.toThrow(/permission denied/);
  });

  it("is hardened like dismiss_card: definer, empty search_path, execute for authenticated only", async () => {
    const f = await db.query<{ prosecdef: boolean; proconfig: string[] | null }>(
      "select prosecdef, proconfig from pg_proc where proname = 'mark_card_read'");
    expect(f.rows).toHaveLength(1);
    expect(f.rows[0].prosecdef).toBe(true);
    expect(f.rows[0].proconfig).toEqual(['search_path=""']);
    const can = async (role: string) => (await db.query<{ ok: boolean }>(
      "select has_function_privilege($1, 'public.mark_card_read(uuid)', 'execute') as ok", [role])).rows[0].ok;
    expect([await can("authenticated"), await can("anon")]).toEqual([true, false]);
    // dismiss_card stays in place (the app no longer calls it).
    expect((await db.query("select 1 from pg_proc where proname = 'dismiss_card'")).rows).toHaveLength(1);
  });
});
