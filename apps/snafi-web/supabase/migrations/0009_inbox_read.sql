-- Snafi UI job: the Inbox.
-- Ahmad's cards now sit in the Inbox behind the bell, and a card is "read" once Khalid opens it.
--   cards.read_at   when Khalid first opened the card (null = unread); the app hides a card
--                   7 days after it was read. Rows are not deleted here.
--   mark_card_read  the app's only way to set it, for its own cards, once.
-- dismiss_card (0008) stays in place but the app no longer calls it and no longer may: its
-- execute right is taken back below; cards dismissed before this job (dismissed_at set) stay hidden.
-- The app (role "authenticated") still cannot insert, delete or update cards directly.
-- Run once in the Supabase SQL Editor after 0008_proactive.sql.

begin;

alter table public.cards add column read_at timestamptz;

-- ---------- mark a card read ----------
-- Sets read_at the first time only: a second call keeps the first time. Another user's card,
-- or an id that does not exist, changes nothing and says nothing.
create function public.mark_card_read(p_id uuid)
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
  update public.cards set read_at = now() where id = p_id and user_id = uid and read_at is null;
end;
$$;

revoke all on function public.mark_card_read(uuid) from public, anon;
grant execute on function public.mark_card_read(uuid) to authenticated;

-- ---------- take back the dismiss_card right ----------
-- Nothing in the app calls dismiss_card any more (it marks a card read instead), and a dismissed
-- card cannot be brought back from any screen, so the app keeps no right to hide a card for good.
-- The function itself stays, so rows dismissed before this job keep their meaning and Khalid can
-- still run it by hand through the service role.
revoke execute on function public.dismiss_card(uuid) from public, anon, authenticated;

commit;
