// @vitest-environment node
/**
 * Snafi step 6 in the database: migration 0010 (memory and family) and 0011 ("Turn off on all phones"),
 * run in PGlite. Each user reads only their own memory, the app changes it only through the save_* and
 * forget_* functions, Forget really deletes (and blanks the action log's copy), and the no-secrets rule
 * holds for every writer, the worker's service role included.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { PGlite } from "@electric-sql/pglite";
import { beforeAll, describe, expect, it } from "vitest";
import { ALICE, as, BOB, freshDb, migrationFiles } from "./helpers/db";

const GUARD = JSON.parse(readFileSync(resolve(process.cwd(), "..", "..", "tests", "fixtures", "snafi_memory_guard.json"), "utf8")) as {
  allowed: string[]; refused: string[];
};
let db: PGlite;

const one = async <T>(role: "authenticated" | "service_role", sub: string | null, sql: string, params: unknown[] = []) =>
  (await as<T>(db, role, sub, sql, params)).rows[0];

beforeAll(async () => {
  db = await freshDb();
}, 60_000);

describe("migrations 0010 and 0011", () => {
  it("come in order after 0009", () => {
    const files = migrationFiles();
    expect(files.slice(files.indexOf("0009_inbox_read.sql"))).toEqual(
      ["0009_inbox_read.sql", "0010_memory_family.sql", "0011_push_off_all.sql"]);
  });

  it("the no-secrets rule matches the worker's and the app's (the shared fixture)", async () => {
    for (const text of GUARD.allowed) {
      expect((await db.query<{ ok: boolean }>("select public.snafi_memory_ok($1) as ok", [text])).rows[0].ok, text).toBe(true);
    }
    for (const text of GUARD.refused) {
      expect((await db.query<{ ok: boolean }>("select public.snafi_memory_ok($1) as ok", [text])).rows[0].ok, text).toBe(false);
    }
  });

  it("refuses a secret from every writer, the worker's service role included", async () => {
    await expect(as(db, "service_role", null, "insert into public.facts (user_id, body) values ($1, 'PIN is 1234')", [ALICE]))
      .rejects.toThrow(/facts_no_secrets/);
    await expect(as(db, "service_role", null,
      "insert into public.family_members (user_id, name, relation, note) values ($1, 'Sara', 'wife', 'iqama 2123456789')", [ALICE]))
      .rejects.toThrow(/check constraint/);
    await expect(as(db, "authenticated", ALICE, "select public.save_fact(null, 'me', 'My password is x')"))
      .rejects.toThrow(/never keeps passwords/);
  });
});

describe("facts: save, edit and forget", () => {
  it("saves and edits only the caller's own facts, in a known group", async () => {
    const f = await one<{ id: string; source: string }>("authenticated", ALICE,
      "select (public.save_fact(null, 'preferences', '  Likes tea  ')).*");
    expect(f.source).toBe("told");
    await as(db, "authenticated", ALICE, "select public.save_fact($1, 'routine', 'Tea after Asr')", [f.id]);
    expect(await one("service_role", null, "select body, section from public.facts where id = $1", [f.id]))
      .toEqual({ body: "Tea after Asr", section: "routine" });
    await expect(as(db, "authenticated", BOB, "select public.save_fact($1, 'me', 'taken over')", [f.id])).rejects.toThrow(/no fact/);
    await expect(as(db, "authenticated", ALICE, "select public.save_fact(null, 'work', 'x')")).rejects.toThrow(/invalid fact/);
    expect((await as(db, "authenticated", BOB, "select * from public.facts")).rows).toEqual([]);
  });

  it("forget deletes the row and blanks every action-log entry that saved it", async () => {
    const f = await one<{ id: string }>("service_role", null,
      "insert into public.facts (user_id, body) values ($1, 'Sara likes white roses') returning id", [ALICE]);
    await as(db, "service_role", null,
      `insert into public.action_log (user_id, tool, level, summary, args, result, status, undoable, undo)
       values ($1, 'add_fact', 2, 'Saved to memory: Sara likes white roses', '{"body":"Sara likes white roses"}', $2, 'done', true, $3)`,
      [ALICE, JSON.stringify({ id: f.id }), JSON.stringify({ table: "facts", id: f.id })]);
    await as(db, "authenticated", BOB, "select public.forget_fact($1)", [f.id]);  // another user: nothing happens
    expect((await as(db, "service_role", null, "select 1 from public.facts where id = $1", [f.id])).rows).toHaveLength(1);
    await as(db, "authenticated", ALICE, "select public.forget_fact($1)", [f.id]);
    expect((await as(db, "service_role", null, "select 1 from public.facts where id = $1", [f.id])).rows).toEqual([]);
    const log = await one<Record<string, unknown>>("service_role", null,
      "select summary, args, result, undo, undoable from public.action_log where tool = 'add_fact'");
    expect(log).toEqual({ summary: "Forgotten", args: {}, result: null, undo: null, undoable: false });
  });

  it("gives the app no direct write on memory tables", async () => {
    for (const sql of [
      `insert into public.facts (user_id, body) values ('${ALICE}', 'x')`,
      "update public.facts set body = 'x'",
      "delete from public.facts",
      `insert into public.family_members (user_id, name, relation) values ('${ALICE}', 'x', 'son')`,
      "delete from public.family_dates",
      `insert into public.interview_state (user_id) values ('${ALICE}')`,
    ]) {
      await expect(as(db, "authenticated", ALICE, sql), sql).rejects.toThrow(/permission denied/);
    }
    await expect(as(db, "anon", null, "select * from public.family_members")).rejects.toThrow(/permission denied/);
  });
});

describe("family", () => {
  it("one birthday per person, real dates only, both calendars; forgetting a person takes their dates", async () => {
    const m = await one<{ id: string }>("authenticated", ALICE, "select (public.save_family_member(null, 'Noura', 'daughter', '')).id");
    await expect(as(db, "authenticated", ALICE, "select public.save_family_member(null, ' noura ', 'daughter', '')"))
      .rejects.toThrow(/already saved/);
    const d = await one<{ id: string }>("authenticated", ALICE,
      "select (public.save_family_date(null, $1, 'birthday', '', 'hijri', 1440, 9, 30)).id", [m.id]);
    await expect(as(db, "authenticated", ALICE, "select public.save_family_date(null, $1, 'birthday', '', 'gregorian', null, 3, 1)", [m.id]))
      .rejects.toThrow(/already has a birthday/);
    await expect(as(db, "authenticated", ALICE, "select public.save_family_date(null, $1, 'other', '', 'gregorian', null, 4, 31)", [m.id]))
      .rejects.toThrow(/invalid date/);
    await expect(as(db, "authenticated", ALICE, "select public.save_family_date(null, $1, 'anniversary', '', 'gregorian', 2023, 2, 29)", [m.id]))
      .resolves.toBeDefined();  // the database allows 29 Feb; the worker and app check leap years
    await expect(as(db, "authenticated", BOB, "select public.save_family_date(null, $1, 'other', 'x', 'gregorian', null, 1, 1)", [m.id]))
      .rejects.toThrow(/no family member/);
    expect((await as(db, "authenticated", BOB, "select * from public.family_dates")).rows).toEqual([]);
    await as(db, "service_role", null,
      `insert into public.action_log (user_id, tool, level, summary, args, status, undoable, undo)
       values ($1, 'add_family_date', 2, 'Saved the date', '{"person":"Noura"}', 'done', true, $2)`,
      [ALICE, JSON.stringify({ table: "family_dates", id: d.id })]);
    await as(db, "authenticated", ALICE, "select public.forget_family_member($1)", [m.id]);
    expect((await as(db, "service_role", null, "select 1 from public.family_dates where member_id = $1", [m.id])).rows).toEqual([]);
    expect(await one("service_role", null, "select args from public.action_log where tool = 'add_family_date'")).toEqual({ args: {} });
  });

  it("interview state is readable by its owner only", async () => {
    await as(db, "service_role", null, "insert into public.interview_state (user_id, status) values ($1, 'active')", [ALICE]);
    expect(await one("authenticated", ALICE, "select status from public.interview_state")).toEqual({ status: "active" });
    expect((await as(db, "authenticated", BOB, "select * from public.interview_state")).rows).toEqual([]);
  });

  it("the new functions are hardened: definer, empty search_path, execute for authenticated only", async () => {
    for (const fn of ["save_fact(uuid,text,text)", "forget_fact(uuid)", "save_family_member(uuid,text,text,text)",
      "forget_family_member(uuid)", "save_family_date(uuid,uuid,text,text,text,integer,integer,integer)",
      "forget_family_date(uuid)", "remove_all_push_subscriptions()"]) {
      const can = async (role: string) => (await db.query<{ ok: boolean }>(
        "select has_function_privilege($1, $2, 'execute') as ok", [role, `public.${fn}`])).rows[0].ok;
      expect([await can("authenticated"), await can("anon")], fn).toEqual([true, false]);
      const f = (await db.query<{ prosecdef: boolean; proconfig: string[] }>(
        "select prosecdef, proconfig from pg_proc where oid = $1::regprocedure", [`public.${fn}`])).rows[0];
      expect([f.prosecdef, f.proconfig], fn).toEqual([true, ['search_path=""']]);
    }
    const scrub = async (role: string) => (await db.query<{ ok: boolean }>(
      "select has_function_privilege($1, 'public.snafi_scrub_log(uuid,text,uuid[])', 'execute') as ok", [role])).rows[0].ok;
    expect([await scrub("authenticated"), await scrub("anon")]).toEqual([false, false]);
  });
});

describe("0011: Turn off on all phones", () => {
  it("deletes every one of the caller's phones, switches push off, and leaves other users alone", async () => {
    const add = (user: string, n: number) => as(db, "service_role", null,
      "insert into public.push_subscriptions (user_id, endpoint, p256dh, auth) values ($1, $2, $3, $4)",
      [user, `https://web.push.apple.com/phone-${user.slice(0, 4)}-${n}`, "B".repeat(87), "C".repeat(22)]);
    await add(ALICE, 1);
    await add(ALICE, 2);
    await add(BOB, 1);
    await as(db, "service_role", null, "insert into public.user_settings (user_id, push_enabled) values ($1, true), ($2, true)", [ALICE, BOB]);
    expect(await one("authenticated", ALICE, "select public.remove_all_push_subscriptions() as n")).toEqual({ n: 2 });
    expect((await as(db, "service_role", null, "select 1 from public.push_subscriptions where user_id = $1", [ALICE])).rows).toEqual([]);
    expect((await as(db, "service_role", null, "select 1 from public.push_subscriptions where user_id = $1", [BOB])).rows).toHaveLength(1);
    expect(await one("service_role", null, "select push_enabled from public.user_settings where user_id = $1", [ALICE]))
      .toEqual({ push_enabled: false });
    expect(await one("service_role", null, "select push_enabled from public.user_settings where user_id = $1", [BOB]))
      .toEqual({ push_enabled: true });
    await expect(as(db, "authenticated", null, "select public.remove_all_push_subscriptions()")).rejects.toThrow(/not signed in/);
  });
});
