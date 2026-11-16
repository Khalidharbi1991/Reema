-- SEC-153 follow-up: "Turn off on all phones".
-- Settings' Off removes only the phone Khalid is holding (remove_push_subscription). This adds the
-- second button: every phone's push address is deleted and the account's push setting is switched
-- off, so nothing is pushed anywhere until he turns push on again (from any phone).
-- The app (role "authenticated") calls it after a confirm step; it touches only the caller's rows.
-- Run once in the Supabase SQL Editor after 0010_memory_family.sql.

begin;

create function public.remove_all_push_subscriptions()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  removed integer;
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  delete from public.push_subscriptions where user_id = uid;
  get diagnostics removed = row_count;
  insert into public.user_settings (user_id, push_enabled, updated_at)
  values (uid, false, now())
  on conflict (user_id) do update set push_enabled = false, updated_at = now();
  return removed;
end;
$$;

revoke all on function public.remove_all_push_subscriptions() from public, anon;
grant execute on function public.remove_all_push_subscriptions() to authenticated;

commit;
