/**
 * Offline Postgres (PGlite) with a small stand-in for Supabase's auth schema and
 * roles, and every migration in supabase/migrations applied in order.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { PGlite } from "@electric-sql/pglite";

export const ALICE = "11111111-1111-4111-8111-111111111111";
export const BOB = "22222222-2222-4222-8222-222222222222";
export const CONV = "33333333-3333-4333-8333-333333333333";

const MIGRATIONS = resolve(process.cwd(), "supabase", "migrations");

export function migrationFiles(): string[] {
  return readdirSync(MIGRATIONS).filter((f) => f.endsWith(".sql")).sort();
}

const SUPABASE_STUB = `
  create role anon nologin;
  create role authenticated nologin;
  create role service_role nologin bypassrls;
  -- Stand-in for Supabase's "postgres" role: not a superuser, but bypasses RLS.
  create role supabase_owner nologin bypassrls;
  create schema auth;
  grant usage on schema auth to anon, authenticated, service_role, supabase_owner;
  create table auth.users (id uuid primary key);
  create function auth.uid() returns uuid language sql stable as
    $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
  grant usage on schema public to anon, authenticated, service_role, supabase_owner;
  insert into auth.users values ('${ALICE}'), ('${BOB}');
`;

export async function freshDb(options: { migrations?: string[] } = {}): Promise<PGlite> {
  const db = new PGlite();
  await db.exec(SUPABASE_STUB);
  for (const file of options.migrations ?? migrationFiles()) {
    await db.exec(readFileSync(join(MIGRATIONS, file), "utf8"));
  }
  // Mirror Supabase: definer functions are owned by a non-superuser that bypasses RLS.
  await db.exec(`
    grant all on all tables in schema public to supabase_owner;
    do $$ declare f text; begin
      for f in select p.oid::regprocedure::text from pg_proc p join pg_namespace n on n.oid = p.pronamespace
               where n.nspname = 'public' and p.prosecdef loop
        execute format('alter function %s owner to supabase_owner', f);
      end loop;
    end $$;
    grant all on all tables in schema public to service_role;
  `);
  return db;
}

export async function as<T = Record<string, unknown>>(
  db: PGlite,
  role: "anon" | "authenticated" | "service_role",
  sub: string | null,
  sql: string,
  params: unknown[] = [],
) {
  await db.exec("reset role");
  await db.query("select set_config('request.jwt.claim.sub', $1, false)", [sub ?? ""]);
  await db.exec(`set role ${role}`);
  try {
    return await db.query<T>(sql, params);
  } finally {
    await db.exec("reset role");
  }
}
