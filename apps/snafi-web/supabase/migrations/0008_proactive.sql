-- Snafi step 5: Proactive Ahmad.
-- The PC worker's scheduler (no brain call) fires reminders, writes the morning brief and watches
-- mail, and tells Khalid through a card on Today plus a Web Push notification to his phone.
--   user_settings       push on/off, brief time, daily push cap, the language of lock-screen text
--   push_subscriptions  each installed phone's Web Push address (only Apple, Google, Mozilla and
--                       Microsoft push hosts are accepted); only the worker reads them
--   notifications       the worker's ledger: one row per thing it tells Khalid, UNIQUE per
--                       (user_id, dedupe_key), so nothing is ever sent twice
--   cards               what Today shows from Ahmad; Khalid can dismiss one
--   reminders.fired_at  when a reminder went off
-- The app (role "authenticated") changes these only through save_settings, save_push_subscription,
-- remove_push_subscription, dismiss_card and request_test_push. The worker uses service_role.
-- Run once in the Supabase SQL Editor after 0007_today_sources.sql.

begin;

-- ---------- settings ----------
create table public.user_settings (
  user_id      uuid primary key references auth.users (id) on delete cascade,
  push_enabled boolean not null default false,
  brief_time   text not null default '07:00' check (brief_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'),
  daily_cap    integer not null default 10 check (daily_cap between 1 and 50),
  lang         text not null default 'en' check (lang in ('en', 'ar')),
  updated_at   timestamptz not null default now()
);

-- ---------- Web Push addresses (the worker posts to them; never the app) ----------
create table public.push_subscriptions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  endpoint   text not null unique check (char_length(endpoint) between 20 and 1000),
  p256dh     text not null check (p256dh ~ '^[A-Za-z0-9_-]{87}$'),
  auth       text not null check (auth ~ '^[A-Za-z0-9_-]{22}$'),
  failures   integer not null default 0 check (failures >= 0),
  last_ok_at timestamptz,
  created_at timestamptz not null default now()
);
create index push_subscriptions_user_idx on public.push_subscriptions (user_id, created_at desc);

-- ---------- the never-twice ledger ----------
create table public.notifications (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users (id) on delete cascade,
  kind          text not null check (kind in ('reminder', 'brief', 'mail', 'test', 'learned')),
  dedupe_key    text not null check (char_length(dedupe_key) between 3 and 300),
  content_hash  text not null default '' check (content_hash ~ '^([0-9a-f]{64})?$'),
  status        text not null default 'new'
                check (status in ('new', 'held', 'delivering', 'sent', 'silent', 'skipped', 'cancelled')),
  counts_to_cap boolean not null default true,
  card          jsonb check (card is null or (jsonb_typeof(card) = 'object' and pg_column_size(card) <= 8192)),
  hold_until    timestamptz,
  pushed        boolean not null default false,
  reason        text check (char_length(reason) <= 100),
  created_at    timestamptz not null default now(),
  delivered_at  timestamptz,
  unique (user_id, dedupe_key)
);
create index notifications_user_idx on public.notifications (user_id, status, created_at desc);

-- ---------- Ahmad's cards on Today ----------
create table public.cards (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users (id) on delete cascade,
  notification_id uuid unique references public.notifications (id) on delete set null,
  kind            text not null check (kind in ('reminder', 'brief', 'mail', 'test')),
  title           text not null check (char_length(title) between 1 and 200),
  body            text not null check (char_length(body) between 1 and 3000),
  created_at      timestamptz not null default now(),
  dismissed_at    timestamptz
);
create index cards_user_idx on public.cards (user_id, created_at desc) where dismissed_at is null;

-- ---------- reminders go off once ----------
alter table public.reminders add column fired_at timestamptz;
create index reminders_due_idx on public.reminders (user_id, due_at) where fired_at is null and deleted_at is null;

-- ---------- a test push from Settings is a background job for the worker ----------
-- (jobs inserted by request_test_push; the app's own insert policy still allows only chat.reply)

-- ---------- privileges ----------
revoke all on public.user_settings, public.push_subscriptions, public.notifications, public.cards
  from anon, authenticated;
grant select on public.user_settings, public.cards to authenticated;
grant all on public.user_settings, public.push_subscriptions, public.notifications, public.cards to service_role;

do $$
declare t text;
begin
  foreach t in array array['user_settings', 'push_subscriptions', 'notifications', 'cards'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
  end loop;
end $$;
create policy user_settings_select_own on public.user_settings
  for select to authenticated using ((select auth.uid()) = user_id);
create policy cards_select_own on public.cards
  for select to authenticated using ((select auth.uid()) = user_id);
-- push_subscriptions and notifications: no policy for the app at all (only the worker reads them).

-- ---------- save settings (the app's only way to change them) ----------
create function public.save_settings(p_push_enabled boolean, p_brief_time text, p_daily_cap integer, p_lang text)
returns public.user_settings
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  rec public.user_settings;
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  if p_push_enabled is null or p_brief_time is null or p_daily_cap is null
     or p_brief_time !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$' or p_daily_cap not between 1 and 50
     or p_lang not in ('en', 'ar') then
    raise exception 'invalid settings' using errcode = '22023';
  end if;
  insert into public.user_settings (user_id, push_enabled, brief_time, daily_cap, lang, updated_at)
  values (uid, p_push_enabled, p_brief_time, p_daily_cap, p_lang, now())
  on conflict (user_id) do update
    set push_enabled = excluded.push_enabled, brief_time = excluded.brief_time,
        daily_cap = excluded.daily_cap, lang = excluded.lang, updated_at = now()
  returning * into rec;
  return rec;
end;
$$;

-- ---------- save or remove this phone's push address ----------
-- Only the four browser push services are accepted, so the worker can never be made to post
-- anywhere else (SSRF). The same check runs again in the worker before every send.
create function public.push_endpoint_ok(p_endpoint text)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select p_endpoint is not null and char_length(p_endpoint) between 20 and 1000
     and p_endpoint ~ '^https://(fcm\.googleapis\.com|web\.push\.apple\.com|[a-z0-9-]+\.push\.apple\.com|updates\.push\.services\.mozilla\.com|[a-z0-9-]+\.notify\.windows\.com)/[A-Za-z0-9._~:/?#\[\]@!$&''()*+,;=%-]+$'
$$;

create function public.save_push_subscription(p_endpoint text, p_p256dh text, p_auth text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  if not public.push_endpoint_ok(p_endpoint) then
    raise exception 'not a known push service address' using errcode = '22023';
  end if;
  if p_p256dh !~ '^[A-Za-z0-9_-]{87}$' or p_auth !~ '^[A-Za-z0-9_-]{22}$' then
    raise exception 'invalid push keys' using errcode = '22023';
  end if;
  -- An address belongs to one user: another user's row with the same address is not taken over.
  if exists (select 1 from public.push_subscriptions where endpoint = p_endpoint and user_id <> uid) then
    raise exception 'that push address is already in use' using errcode = '42501';
  end if;
  insert into public.push_subscriptions (user_id, endpoint, p256dh, auth)
  values (uid, p_endpoint, p_p256dh, p_auth)
  on conflict (endpoint) do update set p256dh = excluded.p256dh, auth = excluded.auth, failures = 0;
  -- At most five phones or browsers per user: the oldest go first.
  delete from public.push_subscriptions
   where user_id = uid and id not in (
     select id from public.push_subscriptions where user_id = uid order by created_at desc, id limit 5);
end;
$$;

create function public.remove_push_subscription(p_endpoint text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  delete from public.push_subscriptions where user_id = uid and endpoint = p_endpoint;
end;
$$;

-- ---------- dismiss a card ----------
create function public.dismiss_card(p_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  update public.cards set dismissed_at = now() where id = p_id and user_id = uid and dismissed_at is null;
  if not found then
    raise exception 'no card with that id' using errcode = 'P0002';
  end if;
end;
$$;

-- ---------- ask the worker for a test push (at most one waiting at a time) ----------
create function public.request_test_push()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  if exists (select 1 from public.jobs where user_id = uid and kind = 'push.test'
             and status in ('queued', 'claimed', 'running')) then
    return;
  end if;
  insert into public.jobs (user_id, kind, lane, payload)
  values (uid, 'push.test', 'background', '{}'::jsonb);
end;
$$;

revoke all on function public.save_settings(boolean, text, integer, text),
  public.save_push_subscription(text, text, text), public.remove_push_subscription(text),
  public.dismiss_card(uuid), public.request_test_push() from public, anon;
grant execute on function public.save_settings(boolean, text, integer, text),
  public.save_push_subscription(text, text, text), public.remove_push_subscription(text),
  public.dismiss_card(uuid), public.request_test_push() to authenticated;
-- push_endpoint_ok is a pure check of a text against the allow-list (it reads no table), so it keeps
-- the default execute for everyone: the definer functions above call it as their owner.

commit;
