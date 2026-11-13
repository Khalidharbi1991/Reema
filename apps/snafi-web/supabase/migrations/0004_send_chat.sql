-- Snafi phase 2 fix: a chat message and its reply job are saved together.
-- Before this, the app saved the message and then queued the chat.reply job in a
-- second request. When the second request failed, Khalid saw "Couldn't send" while
-- his message stayed in the chat with Ahmad "thinking" forever and nothing queued.
-- send_chat does both in one transaction: either both rows exist or neither does.
-- It runs as the caller (security invoker), so the same column grants and
-- row-level security policies as a direct insert apply; it adds no privilege.
-- Run once in the Supabase SQL Editor after 0003_approvals_once.sql.

begin;

create function public.send_chat(p_conversation_id uuid, p_body text, p_lang text)
returns public.messages
language plpgsql
security invoker
set search_path = ''
as $$
declare
  msg public.messages;
begin
  if auth.uid() is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  insert into public.messages (conversation_id, role, body, lang)
  values (p_conversation_id, 'user', p_body, p_lang)
  returning * into msg;
  insert into public.jobs (kind, payload, conversation_id)
  values ('chat.reply', jsonb_build_object('message_id', msg.id), p_conversation_id);
  return msg;
end;
$$;

revoke all on function public.send_chat(uuid, text, text) from public, anon;
grant execute on function public.send_chat(uuid, text, text) to authenticated;

commit;
