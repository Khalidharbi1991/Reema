-- Snafi SEC-4: an app-side sign-in throttle, before Snafi goes online.
-- Every sign-in try through the app is counted BEFORE Supabase Auth is asked
-- (signin_begin), under a lock per key, so tries sent at the same moment cannot get
-- past the limit (SEC-72). A try that turns out not to be a wrong password (it
-- worked, or Auth was down) is taken back with signin_forget.
-- Limit: 5 counted tries in 15 minutes for the same email, or from the same client
-- IP address (on Vercel), then wait until the oldest of those 5 is 15 minutes old.
-- The app never sends the email or the IP: it sends an HMAC-SHA-256 of each, keyed
-- with SNAFI_THROTTLE_SECRET (a server-only setting), so a direct caller cannot
-- target Khalid's key. Note: anyone who knows his email can still use the sign-in
-- form to block NEW sign-ins for 15 minutes at a time (SEC-71); existing sessions
-- keep working.
-- SEC-70: a direct caller can add rows only for keys of its own choosing, at most 5
-- per key per 15 minutes, and the whole table refuses new tries (fails closed) once
-- it holds 10,000 tries from the last 15 minutes. Rows older than a day are deleted,
-- at most 500 per call, through an index.
-- The table is hidden from the app; only the two functions below touch it.
-- Run once in the Supabase SQL Editor after 0004_send_chat.sql.

begin;

create table public.signin_attempts (
  id         bigint generated always as identity primary key,
  attempt    uuid not null,
  key_hash   text not null check (key_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);

create index signin_attempts_key_idx on public.signin_attempts (key_hash, created_at desc);
create index signin_attempts_created_idx on public.signin_attempts (created_at);
create index signin_attempts_attempt_idx on public.signin_attempts (attempt);

revoke all on public.signin_attempts from anon, authenticated;
alter table public.signin_attempts enable row level security;
alter table public.signin_attempts force row level security;
-- No policies: nobody but the functions' owner can read or change a row.

-- Returns {"wait": seconds, "attempt": uuid or null}. wait > 0 means: do not try;
-- nothing was counted. wait = 0 means: the try is counted under "attempt".
create function public.signin_begin(p_keys text[]) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  k text;
  fifth timestamptz;
  wait integer := 0;
  new_attempt uuid := gen_random_uuid();
begin
  if p_keys is null or cardinality(p_keys) not between 1 and 2
     or exists (select 1 from unnest(p_keys) x where x is null or x !~ '^[0-9a-f]{64}$') then
    raise exception 'invalid throttle keys' using errcode = '22023';
  end if;
  -- One try at a time per key (sorted, so two keys never deadlock).
  foreach k in array (select array_agg(x order by x) from unnest(p_keys) x) loop
    perform pg_advisory_xact_lock(hashtextextended('snafi-signin:' || k, 0));
  end loop;

  delete from public.signin_attempts where id in (
    select id from public.signin_attempts where created_at < now() - interval '1 day' limit 500);

  if (select count(*) from public.signin_attempts where created_at > now() - interval '15 minutes') >= 10000 then
    return jsonb_build_object('wait', 60, 'attempt', null);
  end if;

  foreach k in array p_keys loop
    select created_at into fifth from public.signin_attempts
     where key_hash = k and created_at > now() - interval '15 minutes'
     order by created_at desc offset 4 limit 1;
    if found then
      wait := greatest(wait, ceil(extract(epoch from (fifth + interval '15 minutes' - now())))::integer);
    end if;
  end loop;
  if wait > 0 then
    return jsonb_build_object('wait', wait, 'attempt', null);
  end if;

  insert into public.signin_attempts (attempt, key_hash) select new_attempt, x from unnest(p_keys) x;
  return jsonb_build_object('wait', 0, 'attempt', new_attempt);
end;
$$;

-- Takes back a counted try that was not a wrong password. The attempt id is random
-- and known only to the server that began it.
create function public.signin_forget(p_attempt uuid) returns void
language sql
security definer
set search_path = ''
as $$
  delete from public.signin_attempts where attempt = p_attempt and created_at > now() - interval '15 minutes';
$$;

revoke all on function public.signin_begin(text[]) from public;
revoke all on function public.signin_forget(uuid) from public;
grant execute on function public.signin_begin(text[]) to anon, authenticated;
grant execute on function public.signin_forget(uuid) to anon, authenticated;

commit;
