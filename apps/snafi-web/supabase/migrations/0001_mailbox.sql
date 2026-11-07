-- Snafi step 1: the mailbox between the phone app and the PC worker.
-- Two tables, empty for now. Every row carries user_id (its owner) and
-- row-level security lets a signed-in user see and add only their own rows.
-- The app (publishable key, role "authenticated") can read and insert;
-- it can never update or delete. The PC worker (step 2) uses its own key.
-- Safe to run once in the Supabase SQL Editor.

begin;

-- ---------- jobs: work queued for the PC worker ----------
create table public.jobs (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  kind        text not null check (kind ~ '^[a-z][a-z0-9_.]{0,63}$'),
  status      text not null default 'queued'
              check (status in ('queued', 'claimed', 'running', 'done', 'failed', 'cancelled')),
  payload     jsonb not null default '{}'::jsonb
              check (jsonb_typeof(payload) = 'object' and pg_column_size(payload) <= 65536),
  result      jsonb,
  error       text,
  claimed_by  text,
  claimed_at  timestamptz,
  finished_at timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index jobs_queue_idx on public.jobs (created_at) where status = 'queued';
create index jobs_user_idx on public.jobs (user_id, created_at desc);

-- ---------- messages: chat between Khalid and Ahmad ----------
create table public.messages (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null default auth.uid() references auth.users (id) on delete cascade,
  conversation_id uuid not null,
  role            text not null check (role in ('user', 'assistant', 'system')),
  body            text not null check (char_length(body) between 1 and 8000),
  lang            text not null default 'en' check (lang in ('en', 'ar')),
  job_id          uuid references public.jobs (id) on delete set null,
  created_at      timestamptz not null default now()
);

create index messages_conversation_idx on public.messages (user_id, conversation_id, created_at);

-- ---------- updated_at on jobs ----------
create function public.snafi_touch_updated_at() returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger jobs_touch_updated_at
  before update on public.jobs
  for each row execute function public.snafi_touch_updated_at();

-- ---------- privileges: nothing for anonymous visitors ----------
revoke all on public.jobs, public.messages from anon, authenticated;

-- Signed-in users may read, and may insert only these columns. id, user_id,
-- status, result and timestamps are set by the database, never by the app.
grant select on public.jobs, public.messages to authenticated;
grant insert (kind, payload) on public.jobs to authenticated;
grant insert (conversation_id, role, body, lang) on public.messages to authenticated;

revoke execute on function public.snafi_touch_updated_at() from public, anon, authenticated;

-- ---------- row-level security ----------
alter table public.jobs enable row level security;
alter table public.jobs force row level security;
alter table public.messages enable row level security;
alter table public.messages force row level security;

create policy jobs_select_own on public.jobs
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy jobs_insert_own on public.jobs
  for insert to authenticated
  with check ((select auth.uid()) = user_id and status = 'queued' and result is null and error is null);

create policy messages_select_own on public.messages
  for select to authenticated
  using ((select auth.uid()) = user_id);

-- The app may only post the user's own words; Ahmad's replies come from the worker.
create policy messages_insert_own on public.messages
  for insert to authenticated
  with check ((select auth.uid()) = user_id and role = 'user' and job_id is null);

-- No update or delete policies: with RLS on, those are refused for the app.

commit;
