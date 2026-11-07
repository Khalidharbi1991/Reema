// @vitest-environment node
/**
 * Runs the real migration in PGlite (Postgres in-process, offline) with a
 * small stand-in for Supabase's auth schema and roles, then checks that each
 * user sees and writes only their own rows.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { PGlite } from "@electric-sql/pglite";
import { beforeAll, describe, expect, it } from "vitest";

const MIGRATION = readFileSync(
  fileURLToPath(new URL("../supabase/migrations/0001_mailbox.sql", import.meta.url)),
  "utf8",
);

const ALICE = "11111111-1111-4111-8111-111111111111";
const BOB = "22222222-2222-4222-8222-222222222222";
const CONV = "33333333-3333-4333-8333-333333333333";

const SUPABASE_STUB = `
  create role anon nologin;
  create role authenticated nologin;
  create role service_role nologin bypassrls;
  create schema auth;
  grant usage on schema auth to anon, authenticated, service_role;
  create table auth.users (id uuid primary key);
  create function auth.uid() returns uuid language sql stable as
    $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
  grant usage on schema public to anon, authenticated, service_role;
  insert into auth.users values ('${ALICE}'), ('${BOB}');
`;

let db: PGlite;

async function as(role: "anon" | "authenticated" | "service_role", sub: string | null, sql: string, params: unknown[] = []) {
  await db.exec("reset role");
  await db.query("select set_config('request.jwt.claim.sub', $1, false)", [sub ?? ""]);
  await db.exec(`set role ${role}`);
  try {
    return await db.query<Record<string, unknown>>(sql, params);
  } finally {
    await db.exec("reset role");
  }
}

beforeAll(async () => {
  db = new PGlite();
  await db.exec(SUPABASE_STUB);
  await db.exec(MIGRATION);
  await db.exec(`grant all on public.jobs, public.messages to service_role`);
}, 60_000);

describe("mailbox row-level security", () => {
  it("creates both tables empty, with RLS forced", async () => {
    const r = await db.query<{ relname: string; relrowsecurity: boolean; relforcerowsecurity: boolean }>(
      "select relname, relrowsecurity, relforcerowsecurity from pg_class where relname in ('jobs','messages') order by relname",
    );
    expect(r.rows).toEqual([
      { relname: "jobs", relrowsecurity: true, relforcerowsecurity: true },
      { relname: "messages", relrowsecurity: true, relforcerowsecurity: true },
    ]);
    const counts = await db.query<{ n: number }>("select (select count(*) from public.jobs)::int + (select count(*) from public.messages)::int as n");
    expect(counts.rows[0].n).toBe(0);
  });

  it("gives anonymous visitors nothing", async () => {
    await expect(as("anon", null, "select * from public.messages")).rejects.toThrow(/permission denied/);
    await expect(as("anon", null, "insert into public.jobs (kind) values ('x')")).rejects.toThrow(/permission denied/);
  });

  it("stamps user_id from the session and keeps users apart", async () => {
    await as("authenticated", ALICE, "insert into public.messages (conversation_id, role, body, lang) values ($1, 'user', 'مرحبا', 'ar')", [CONV]);
    await as("authenticated", BOB, "insert into public.messages (conversation_id, role, body) values ($1, 'user', 'hi')", [CONV]);

    const alice = await as("authenticated", ALICE, "select user_id, body from public.messages");
    expect(alice.rows).toEqual([{ user_id: ALICE, body: "مرحبا" }]);
    const bob = await as("authenticated", BOB, "select user_id, body from public.messages");
    expect(bob.rows).toEqual([{ user_id: BOB, body: "hi" }]);
  });

  it("refuses setting user_id to someone else", async () => {
    await expect(
      as("authenticated", ALICE, "insert into public.messages (user_id, conversation_id, role, body) values ($1, $2, 'user', 'x')", [BOB, CONV]),
    ).rejects.toThrow(/permission denied/);
  });

  it("lets the app post only user messages", async () => {
    await expect(
      as("authenticated", ALICE, "insert into public.messages (conversation_id, role, body) values ($1, 'assistant', 'fake reply')", [CONV]),
    ).rejects.toThrow(/row-level security/);
  });

  it("queues jobs but never lets the app change or delete them", async () => {
    const queued = await as("authenticated", ALICE, "insert into public.jobs (kind, payload) values ('chat.reply', '{\"n\":1}') returning status, user_id");
    expect(queued.rows).toEqual([{ status: "queued", user_id: ALICE }]);

    await expect(as("authenticated", ALICE, "insert into public.jobs (kind, status) values ('x', 'done')")).rejects.toThrow(/permission denied/);
    await expect(as("authenticated", ALICE, "update public.jobs set status = 'done'")).rejects.toThrow(/permission denied/);
    await expect(as("authenticated", ALICE, "delete from public.jobs")).rejects.toThrow(/permission denied/);
    await expect(as("authenticated", ALICE, "delete from public.messages")).rejects.toThrow(/permission denied/);

    const bobJobs = await as("authenticated", BOB, "select * from public.jobs");
    expect(bobJobs.rows).toEqual([]);
  });

  it("rejects bad job kinds and oversize messages", async () => {
    await expect(as("authenticated", ALICE, "insert into public.jobs (kind) values ('Drop Table')")).rejects.toThrow(/check constraint/);
    await expect(
      as("authenticated", ALICE, "insert into public.messages (conversation_id, role, body) values ($1, 'user', repeat('a', 8001))", [CONV]),
    ).rejects.toThrow(/check constraint/);
  });

  it("lets the worker role (step 2) update a job, and touches updated_at", async () => {
    const before = await as("service_role", null, "select id, updated_at from public.jobs limit 1");
    const { id, updated_at } = before.rows[0] as { id: string; updated_at: Date };
    await new Promise((r) => setTimeout(r, 5));
    await as("service_role", null, "update public.jobs set status = 'done', result = '{}' where id = $1", [id]);
    const after = await as("authenticated", ALICE, "select status, updated_at from public.jobs where id = $1", [id]);
    expect(after.rows[0].status).toBe("done");
    expect(new Date(after.rows[0].updated_at as Date).getTime()).toBeGreaterThan(new Date(updated_at).getTime());
  });
});
