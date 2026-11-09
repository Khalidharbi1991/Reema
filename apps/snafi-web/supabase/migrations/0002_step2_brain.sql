-- Snafi step 2: Ahmad's brain.
-- Lanes and retries on jobs, approval cards, the action log with Undo, notes,
-- reminders, facts, and the worker's heartbeat and backup status.
-- Every table carries user_id; row-level security lets a signed-in user read
-- only their own rows. The app (role "authenticated") changes nothing directly
-- except posting its own chat messages and chat jobs; it decides approvals and
-- asks for Undo only through two narrow functions. The PC worker uses the
-- secret key (role "service_role"), which bypasses row-level security.
-- Run once in the Supabase SQL Editor after 0001_mailbox.sql.

begin;

-- ---------- jobs: lanes, attempts, retry time ----------
alter table public.jobs
  add column lane            text not null default 'chat' check (lane in ('chat', 'background')),
  add column attempts        integer not null default 0 check (attempts >= 0),
  add column max_attempts    integer not null default 2 check (max_attempts between 1 and 5),
  add column run_after       timestamptz not null default now(),
  add column conversation_id uuid;

create index jobs_lane_queue_idx on public.jobs (lane, run_after) where status = 'queued';

-- The app may queue only chat replies, in the chat lane, for one conversation.
grant insert (conversation_id) on public.jobs to authenticated;
drop policy jobs_insert_own on public.jobs;
create policy jobs_insert_own on public.jobs
  for insert to authenticated
  with check ((select auth.uid()) = user_id and status = 'queued' and result is null and error is null
              and kind = 'chat.reply' and lane = 'chat' and attempts = 0);

-- ---------- approvals: Level 3 actions waiting for Khalid ----------
create table public.approvals (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users (id) on delete cascade,
  conversation_id uuid not null,
  job_id          uuid references public.jobs (id) on delete set null,
  tool            text not null check (tool ~ '^[a-z][a-z0-9_]{0,63}$'),
  args            jsonb not null default '{}'::jsonb check (jsonb_typeof(args) = 'object' and pg_column_size(args) <= 16384),
  summary         text not null check (char_length(summary) between 1 and 500),
  level           smallint not null default 3 check (level = 3),
  status          text not null default 'pending'
                  check (status in ('pending', 'approved', 'rejected', 'executed', 'failed', 'expired')),
  decided_at      timestamptz,
  executed_at     timestamptz,
  result          jsonb,
  created_at      timestamptz not null default now()
);
create index approvals_user_idx on public.approvals (user_id, status, created_at desc);

alter table public.messages
  add column approval_id uuid references public.approvals (id) on delete set null,
  add column meta        jsonb not null default '{}'::jsonb check (jsonb_typeof(meta) = 'object');

-- ---------- action_log: everything Ahmad did, with Undo where possible ----------
create table public.action_log (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references auth.users (id) on delete cascade,
  conversation_id   uuid,
  job_id            uuid references public.jobs (id) on delete set null,
  approval_id       uuid references public.approvals (id) on delete set null,
  tool              text not null check (tool ~ '^[a-z][a-z0-9_]{0,63}$'),
  level             smallint not null check (level between 1 and 3),
  summary           text not null check (char_length(summary) between 1 and 500),
  args              jsonb not null default '{}'::jsonb,
  result            jsonb,
  status            text not null check (status in ('done', 'failed', 'undone')),
  undoable          boolean not null default false,
  undo              jsonb,
  undo_requested_at timestamptz,
  undone_at         timestamptz,
  created_at        timestamptz not null default now()
);
create index action_log_user_idx on public.action_log (user_id, created_at desc);

-- ---------- notes, reminders, facts (Ahmad's local tools in step 2) ----------
create table public.notes (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  body       text not null check (char_length(body) between 1 and 4000),
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);
create table public.reminders (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  body       text not null check (char_length(body) between 1 and 1000),
  due_at     timestamptz,
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);
create table public.facts (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  body       text not null check (char_length(body) between 1 and 1000),
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);
create index notes_user_idx on public.notes (user_id, created_at desc);
create index reminders_user_idx on public.reminders (user_id, due_at);
create index facts_user_idx on public.facts (user_id, created_at desc);

-- ---------- worker_status: heartbeat and last backup ----------
create table public.worker_status (
  user_id           uuid primary key references auth.users (id) on delete cascade,
  worker_id         text not null check (char_length(worker_id) between 1 and 100),
  version           text not null default '',
  last_seen         timestamptz not null default now(),
  lanes             jsonb not null default '{}'::jsonb,
  last_backup_at    timestamptz,
  last_backup_ok    boolean,
  last_backup_error text check (char_length(last_backup_error) <= 500),
  last_backup_file  text check (char_length(last_backup_file) <= 200),
  updated_at        timestamptz not null default now()
);

-- ---------- privileges ----------
revoke all on public.approvals, public.action_log, public.notes, public.reminders,
              public.facts, public.worker_status from anon, authenticated;
grant select on public.approvals, public.action_log, public.notes, public.reminders,
                public.facts, public.worker_status to authenticated;
grant all on public.jobs, public.messages, public.approvals, public.action_log, public.notes,
             public.reminders, public.facts, public.worker_status to service_role;

-- ---------- row-level security: read own rows only ----------
do $$
declare t text;
begin
  foreach t in array array['approvals', 'action_log', 'notes', 'reminders', 'facts', 'worker_status'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format('create policy %I on public.%I for select to authenticated using ((select auth.uid()) = user_id)',
                   t || '_select_own', t);
  end loop;
end $$;

-- ---------- decide an approval (the app's only way to change one) ----------
-- Pending -> approved or rejected, once, by its owner; queues the follow-up job
-- so the worker runs the action (if approved) and carries on the chat.
create function public.decide_approval(p_id uuid, p_decision text)
returns public.approvals
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  rec public.approvals;
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  if p_decision not in ('approved', 'rejected') then
    raise exception 'decision must be approved or rejected' using errcode = '22023';
  end if;
  update public.approvals
     set status = p_decision, decided_at = now()
   where id = p_id and user_id = uid and status = 'pending'
  returning * into rec;
  if not found then
    raise exception 'no pending approval with that id' using errcode = 'P0002';
  end if;
  insert into public.jobs (user_id, kind, lane, payload, conversation_id)
  values (uid, 'approval.resume', 'chat', jsonb_build_object('approval_id', rec.id), rec.conversation_id);
  return rec;
end;
$$;

-- ---------- ask for Undo (the app's only way to touch the action log) ----------
create function public.request_undo(p_action_id uuid)
returns public.action_log
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  rec public.action_log;
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  update public.action_log
     set undo_requested_at = now()
   where id = p_action_id and user_id = uid and undoable and status = 'done'
     and undone_at is null and undo_requested_at is null
  returning * into rec;
  if not found then
    raise exception 'nothing to undo with that id' using errcode = 'P0002';
  end if;
  insert into public.jobs (user_id, kind, lane, payload, conversation_id)
  values (uid, 'action.undo', 'chat', jsonb_build_object('action_id', rec.id), rec.conversation_id);
  return rec;
end;
$$;

-- ---------- claim the next job in a lane (the worker only) ----------
create function public.claim_job(p_lane text, p_worker text)
returns setof public.jobs
language sql
security invoker
set search_path = ''
as $$
  update public.jobs j
     set status = 'claimed', claimed_by = p_worker, claimed_at = now(), attempts = j.attempts + 1
   where j.id = (
     select id from public.jobs
      where status = 'queued' and lane = p_lane and run_after <= now()
      order by created_at
      limit 1
      for update skip locked)
  returning j.*;
$$;

revoke all on function public.decide_approval(uuid, text) from public, anon;
revoke all on function public.request_undo(uuid) from public, anon;
revoke all on function public.claim_job(text, text) from public, anon, authenticated;
grant execute on function public.decide_approval(uuid, text) to authenticated;
grant execute on function public.request_undo(uuid) to authenticated;
grant execute on function public.claim_job(text, text) to service_role;

commit;
