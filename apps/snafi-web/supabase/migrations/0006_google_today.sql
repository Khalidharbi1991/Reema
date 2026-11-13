-- Snafi step 3: the Today screen's Google part (today_feed).
-- The PC worker reads Khalid's Google Calendar and Gmail every 10 minutes, with no brain
-- call, and writes ONE row per user: the next event (title, time, place) and up to five
-- important unread emails (sender name, subject, time). Never an email body, never a token.
-- The Google refresh token stays on the PC in Windows Credential Manager; nothing here
-- can reach Google.
-- The app (role "authenticated") may only read its own row; only the worker (service_role)
-- writes it. It is a cache rebuilt every few minutes, so it is not in the daily backup.
-- Run once in the Supabase SQL Editor after 0005_signin_throttle.sql.

begin;

create table public.today_feed (
  user_id       uuid primary key references auth.users (id) on delete cascade,
  next_event    jsonb check (next_event is null or (jsonb_typeof(next_event) = 'object'
                                                    and pg_column_size(next_event) <= 2048)),
  emails        jsonb not null default '[]'::jsonb
                check (jsonb_typeof(emails) = 'array' and jsonb_array_length(emails) <= 5
                       and pg_column_size(emails) <= 8192),
  google_status text not null default 'off'
                check (google_status in ('ok', 'off', 'not_connected', 'reconnect', 'error')),
  updated_at    timestamptz not null default now()
);

revoke all on public.today_feed from anon, authenticated;
grant select on public.today_feed to authenticated;
grant all on public.today_feed to service_role;

alter table public.today_feed enable row level security;
alter table public.today_feed force row level security;
create policy today_feed_select_own on public.today_feed
  for select to authenticated using ((select auth.uid()) = user_id);

commit;
