-- Snafi SEC-4: an app-side sign-in throttle, before Snafi goes online.
-- After 5 wrong passwords in 15 minutes for the same email, or from the same client
-- IP address, sign-in is refused until the oldest of those 5 is 15 minutes old.
-- The app never sends the email or the IP: it sends an HMAC-SHA-256 of each, keyed
-- with SNAFI_THROTTLE_SECRET (a server-only setting). Without that secret, nobody
-- calling these functions directly can work out the key for Khalid's email, so they
-- cannot lock him out on purpose; they can only add rows for random keys, which are
-- capped per key and deleted after a day.
-- The table is hidden from the app; only the two functions below touch it.
-- Run once in the Supabase SQL Editor after 0004_send_chat.sql.

begin;

create table public.signin_failures (
  id         bigint generated always as identity primary key,
  key_hash   text not null check (key_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);

create index signin_failures_key_idx on public.signin_failures (key_hash, created_at desc);

revoke all on public.signin_failures from anon, authenticated;
alter table public.signin_failures enable row level security;
alter table public.signin_failures force row level security;
-- No policies: nobody but the functions' owner can read or change a row.

-- Seconds to wait before another try (0 = go ahead).
create function public.signin_wait_seconds(p_keys text[]) returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  k text;
  fifth timestamptz;
  wait integer := 0;
begin
  if p_keys is null or cardinality(p_keys) not between 1 and 2
     or exists (select 1 from unnest(p_keys) x where x is null or x !~ '^[0-9a-f]{64}$') then
    raise exception 'invalid throttle keys' using errcode = '22023';
  end if;
  foreach k in array p_keys loop
    select created_at into fifth from public.signin_failures
     where key_hash = k and created_at > now() - interval '15 minutes'
     order by created_at desc offset 4 limit 1;
    if found then
      wait := greatest(wait, ceil(extract(epoch from (fifth + interval '15 minutes' - now())))::integer);
    end if;
  end loop;
  return greatest(wait, 0);
end;
$$;

-- Records one wrong password for each key. At most 20 rows per key are kept in the
-- window, and rows older than a day are deleted.
create function public.signin_record_failure(p_keys text[]) returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  k text;
begin
  if p_keys is null or cardinality(p_keys) not between 1 and 2
     or exists (select 1 from unnest(p_keys) x where x is null or x !~ '^[0-9a-f]{64}$') then
    raise exception 'invalid throttle keys' using errcode = '22023';
  end if;
  delete from public.signin_failures where created_at < now() - interval '1 day';
  foreach k in array p_keys loop
    if (select count(*) from public.signin_failures
         where key_hash = k and created_at > now() - interval '15 minutes') < 20 then
      insert into public.signin_failures (key_hash) values (k);
    end if;
  end loop;
end;
$$;

revoke all on function public.signin_wait_seconds(text[]) from public;
revoke all on function public.signin_record_failure(text[]) from public;
grant execute on function public.signin_wait_seconds(text[]) to anon, authenticated;
grant execute on function public.signin_record_failure(text[]) to anon, authenticated;

commit;
