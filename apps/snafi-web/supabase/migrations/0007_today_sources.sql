-- Snafi step 4: Yahoo mail and Todoist on the Today screen (today_feed).
-- The PC worker now also reads Khalid's Yahoo Inbox and his Todoist every 10 minutes, with no
-- brain call, and writes into the same ONE row per user:
--   emails  up to five important unread emails from each account (sender name, subject, time,
--           and which account: "gmail" or "yahoo"), so at most ten. Never an email body.
--   tasks   up to ten Todoist tasks due today or overdue (title, due date, priority, overdue,
--           repeating). Never a task description or comment.
--   yahoo_status, todoist_status  what the app says about each source (like google_status).
-- The Yahoo app password and the Todoist API token stay on the PC in Windows Credential
-- Manager; nothing here can reach Yahoo or Todoist.
-- The app (role "authenticated") may still only read its own row; only the worker (service_role)
-- writes it. It is a cache rebuilt every few minutes, so it is not in the daily backup.
-- Run once in the Supabase SQL Editor after 0006_google_today.sql.

begin;

alter table public.today_feed drop constraint if exists today_feed_emails_check;
alter table public.today_feed add constraint today_feed_emails_check
  check (jsonb_typeof(emails) = 'array' and jsonb_array_length(emails) <= 10
         and pg_column_size(emails) <= 16384);

alter table public.today_feed
  add column tasks jsonb not null default '[]'::jsonb
    constraint today_feed_tasks_check
    check (jsonb_typeof(tasks) = 'array' and jsonb_array_length(tasks) <= 10
           and pg_column_size(tasks) <= 8192),
  add column yahoo_status text not null default 'off'
    constraint today_feed_yahoo_status_check
    check (yahoo_status in ('ok', 'off', 'not_connected', 'reconnect', 'error')),
  add column todoist_status text not null default 'off'
    constraint today_feed_todoist_status_check
    check (todoist_status in ('ok', 'off', 'not_connected', 'reconnect', 'error'));

-- The grants and the row policy from 0006 cover the new columns (select own row; the worker writes).
revoke all on public.today_feed from anon, authenticated;
grant select on public.today_feed to authenticated;
grant all on public.today_feed to service_role;

commit;
