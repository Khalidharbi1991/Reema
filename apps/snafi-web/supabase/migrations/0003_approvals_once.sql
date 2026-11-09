-- Snafi step 2 security fixes (SEC-12, SEC-13).
-- SEC-12: an approved action runs at most once. The worker moves a card from
--   approved to executing in one conditional update before running it, so a retry,
--   a timeout or a database error can never run it again.
-- SEC-13: the approval is bound to the exact arguments Khalid saw (args_hash, a
--   SHA-256 the worker computes when it creates the card), and a card expires
--   24 hours after it was made if nobody decided it.
-- Run once in the Supabase SQL Editor after 0002_step2_brain.sql.

begin;

alter table public.approvals drop constraint approvals_status_check;
alter table public.approvals add constraint approvals_status_check
  check (status in ('pending', 'approved', 'executing', 'rejected', 'executed', 'failed', 'expired'));

alter table public.approvals
  add column args_hash  text not null default '' check (args_hash = '' or args_hash ~ '^[0-9a-f]{64}$'),
  add column expires_at timestamptz not null default now() + interval '24 hours';

-- The app may now decide only with the hash of the arguments it showed.
drop function public.decide_approval(uuid, text);

create function public.decide_approval(p_id uuid, p_decision text, p_args_hash text)
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
  select * into rec from public.approvals
   where id = p_id and user_id = uid and status = 'pending'
   for update;
  if not found then
    raise exception 'no pending approval with that id' using errcode = 'P0002';
  end if;
  if rec.expires_at <= now() then
    update public.approvals set status = 'expired', decided_at = now() where id = rec.id returning * into rec;
    return rec;  -- nothing is queued; the app shows the card as expired
  end if;
  if p_decision = 'approved' and (rec.args_hash = '' or p_args_hash is distinct from rec.args_hash) then
    raise exception 'the action changed after it was shown; nothing was approved' using errcode = '22023';
  end if;
  update public.approvals set status = p_decision, decided_at = now() where id = rec.id returning * into rec;
  insert into public.jobs (user_id, kind, lane, payload, conversation_id)
  values (uid, 'approval.resume', 'chat', jsonb_build_object('approval_id', rec.id), rec.conversation_id);
  return rec;
end;
$$;

revoke all on function public.decide_approval(uuid, text, text) from public, anon;
grant execute on function public.decide_approval(uuid, text, text) to authenticated;

commit;
