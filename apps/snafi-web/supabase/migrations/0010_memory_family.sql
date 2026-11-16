-- Snafi step 6: Memory and family.
--   facts.section, .source, .updated_at   what Ahmad knows about Khalid, grouped for the About me page
--                                         (me, family, preferences, routine) and where it came from
--                                         (told in chat, the interview, or learned)
--   family_members                        wife, daughters, son and others: name, relation, a short note
--   family_dates                          birthdays, anniversaries and other key dates, each in the
--                                         Gregorian or the Hijri (Umm al-Qura) calendar
--   interview_state                       where Ahmad's onboarding interview stands (one row per user)
--   snafi_memory_ok(text)                 the no-secrets rule, enforced on every memory row by a CHECK:
--                                         no group of 9 or more digits (ID, card, IBAN, phone numbers)
--                                         and no password, PIN, OTP, CVV, card or ID number wording,
--                                         in English or Arabic. The worker and the app apply the same
--                                         rule first (tests/fixtures/snafi_memory_guard.json).
-- Forget really deletes: forget_fact, forget_family_member and forget_family_date delete the row and
-- blank the text of every action-log entry that saved it. Rows already removed with Undo before this
-- step (facts.deleted_at set) are deleted here for the same reason.
-- The app (role "authenticated") reads its own rows and changes them only through the save_* and
-- forget_* functions below. The worker uses service_role. Family members (later) are other users:
-- row-level security keeps every row to its owner.
-- Run once in the Supabase SQL Editor after 0009_inbox_read.sql.

begin;

-- ---------- the no-secrets rule ----------
create function public.snafi_norm(p text)
returns text
language sql
immutable
set search_path = ''
as $$
  select lower(regexp_replace(
           translate(coalesce(p, ''), 'أإآٱةى٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', 'ااااهي01234567890123456789'),
           '[ً-ٰٟـ]', '', 'g'))
$$;

create function public.snafi_memory_ok(p text)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select p is null or (
        public.snafi_norm(p) !~ '[0-9]([ .-]?[0-9]){8,}'
    and public.snafi_norm(p) !~* '\m(password|passwords|passcode|passwd|pin|pins|otp|cvv|cvc|iban|iqama|token|secret|api key|card number|card no|credit card|debit card|id number|national id|passport number|passport no|security code|verification code|login code)\M'
    and public.snafi_norm(p) !~ '(كلمه المرور|كلمه السر|كلمات المرور|الرقم السري|الرمز السري|رمز التحقق|رمز الدخول|رقم الهويه|الهويه الوطنيه|رقم الاقامه|رقم الجواز|رقم البطاقه|البطاقه الائتمانيه|رقم الحساب|الايبان|ايبان)'
  )
$$;

-- ---------- facts: grouped, with a source; forgotten rows really go ----------
delete from public.facts where deleted_at is not null;
alter table public.facts
  add column section    text not null default 'me' check (section in ('me', 'family', 'preferences', 'routine')),
  add column source     text not null default 'told' check (source in ('told', 'interview', 'learned')),
  add column updated_at timestamptz not null default now(),
  add constraint facts_no_secrets check (public.snafi_memory_ok(body)) not valid;

-- ---------- family ----------
create table public.family_members (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  name       text not null check (char_length(btrim(name)) between 1 and 80 and public.snafi_memory_ok(name)),
  relation   text not null check (relation in ('wife', 'husband', 'daughter', 'son', 'mother', 'father',
                                                'sister', 'brother', 'other')),
  note       text not null default '' check (char_length(note) <= 300 and public.snafi_memory_ok(note)),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index family_members_name_idx on public.family_members (user_id, lower(btrim(name)));

create table public.family_dates (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  member_id  uuid not null references public.family_members (id) on delete cascade,
  label      text not null check (label in ('birthday', 'anniversary', 'other')),
  title      text not null default '' check (char_length(title) <= 80 and public.snafi_memory_ok(title)),
  calendar   text not null default 'gregorian' check (calendar in ('gregorian', 'hijri')),
  year       integer check (year is null or (calendar = 'gregorian' and year between 1900 and 2100)
                                         or (calendar = 'hijri' and year between 1300 and 1500)),
  month      integer not null check (month between 1 and 12),
  day        integer not null check (day between 1 and 31),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (calendar = 'hijri' and day <= 30
         or calendar = 'gregorian' and day <= (case when month = 2 then 29
                                                    when month in (4, 6, 9, 11) then 30 else 31 end)),
  check (label <> 'other' or char_length(btrim(title)) >= 1)
);
create index family_dates_user_idx on public.family_dates (user_id, month, day);
create index family_dates_member_idx on public.family_dates (member_id);
-- At most one birthday per person.
create unique index family_dates_one_birthday on public.family_dates (member_id) where label = 'birthday';

-- ---------- the onboarding interview ----------
create table public.interview_state (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  status      text not null default 'invited' check (status in ('invited', 'active', 'paused', 'done')),
  step        integer not null default 0 check (step between 0 and 100),
  lang        text not null default 'en' check (lang in ('en', 'ar')),
  started_at  timestamptz,
  finished_at timestamptz,
  updated_at  timestamptz not null default now()
);

-- ---------- privileges and row-level security ----------
revoke all on public.family_members, public.family_dates, public.interview_state from anon, authenticated;
grant select on public.family_members, public.family_dates, public.interview_state to authenticated;
grant all on public.family_members, public.family_dates, public.interview_state to service_role;

do $$
declare t text;
begin
  foreach t in array array['family_members', 'family_dates', 'interview_state'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format('create policy %I on public.%I for select to authenticated using ((select auth.uid()) = user_id)',
                   t || '_select_own', t);
  end loop;
end $$;

-- ---------- blank the action log's copy of a forgotten row ----------
create function public.snafi_scrub_log(p_user uuid, p_table text, p_ids uuid[])
returns void
language sql
security definer
set search_path = ''
as $$
  update public.action_log
     set args = '{}'::jsonb, result = null, undo = null, undoable = false, summary = 'Forgotten'
   where user_id = p_user and undo is not null and undo->>'table' = p_table
     and undo->>'id' = any (select unnest(p_ids)::text);
$$;
revoke all on function public.snafi_scrub_log(uuid, text, uuid[]) from public, anon, authenticated;

-- ---------- facts: save (add or edit) and forget ----------
create function public.save_fact(p_id uuid, p_section text, p_body text)
returns public.facts
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  v_body text := btrim(coalesce(p_body, ''));
  rec public.facts;
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  if p_section not in ('me', 'family', 'preferences', 'routine') or char_length(v_body) not between 1 and 500 then
    raise exception 'invalid fact' using errcode = '22023';
  end if;
  if not public.snafi_memory_ok(v_body) then
    raise exception 'memory never keeps passwords, ID or card numbers' using errcode = '22023';
  end if;
  if p_id is null then
    insert into public.facts (user_id, body, section, source) values (uid, v_body, p_section, 'told') returning * into rec;
  else
    update public.facts set body = v_body, section = p_section, updated_at = now()
     where id = p_id and user_id = uid and deleted_at is null
    returning * into rec;
    if rec.id is null then
      raise exception 'no fact with that id' using errcode = 'P0002';
    end if;
  end if;
  return rec;
end;
$$;

create function public.forget_fact(p_id uuid)
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
  delete from public.facts where id = p_id and user_id = uid;
  if found then
    perform public.snafi_scrub_log(uid, 'facts', array[p_id]);
  end if;
end;
$$;

-- ---------- family members: save and forget (a member's dates go with them) ----------
create function public.save_family_member(p_id uuid, p_name text, p_relation text, p_note text)
returns public.family_members
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  rec public.family_members;
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  if char_length(btrim(coalesce(p_name, ''))) not between 1 and 80 or char_length(coalesce(p_note, '')) > 300
     or p_relation not in ('wife', 'husband', 'daughter', 'son', 'mother', 'father', 'sister', 'brother', 'other') then
    raise exception 'invalid family member' using errcode = '22023';
  end if;
  if not public.snafi_memory_ok(p_name) or not public.snafi_memory_ok(p_note) then
    raise exception 'memory never keeps passwords, ID or card numbers' using errcode = '22023';
  end if;
  if p_id is null then
    insert into public.family_members (user_id, name, relation, note)
    values (uid, btrim(p_name), p_relation, btrim(coalesce(p_note, ''))) returning * into rec;
  else
    update public.family_members set name = btrim(p_name), relation = p_relation, note = btrim(coalesce(p_note, '')),
                                     updated_at = now()
     where id = p_id and user_id = uid
    returning * into rec;
    if rec.id is null then
      raise exception 'no family member with that id' using errcode = 'P0002';
    end if;
  end if;
  return rec;
exception
  when unique_violation then
    raise exception 'a family member with that name is already saved' using errcode = '23505';
end;
$$;

create function public.forget_family_member(p_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  dates uuid[];
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  select coalesce(array_agg(id), '{}') into dates from public.family_dates where member_id = p_id and user_id = uid;
  delete from public.family_members where id = p_id and user_id = uid;
  if found then
    perform public.snafi_scrub_log(uid, 'family_members', array[p_id]);
    perform public.snafi_scrub_log(uid, 'family_dates', dates);
  end if;
end;
$$;

-- ---------- family dates: save and forget ----------
create function public.save_family_date(p_id uuid, p_member_id uuid, p_label text, p_title text, p_calendar text,
                                        p_year integer, p_month integer, p_day integer)
returns public.family_dates
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  rec public.family_dates;
begin
  if uid is null then
    raise exception 'not signed in' using errcode = '42501';
  end if;
  if not exists (select 1 from public.family_members where id = p_member_id and user_id = uid) then
    raise exception 'no family member with that id' using errcode = 'P0002';
  end if;
  if not public.snafi_memory_ok(p_title) then
    raise exception 'memory never keeps passwords, ID or card numbers' using errcode = '22023';
  end if;
  begin
    if p_id is null then
      insert into public.family_dates (user_id, member_id, label, title, calendar, year, month, day)
      values (uid, p_member_id, p_label, btrim(coalesce(p_title, '')), p_calendar, p_year, p_month, p_day)
      returning * into rec;
    else
      update public.family_dates
         set member_id = p_member_id, label = p_label, title = btrim(coalesce(p_title, '')), calendar = p_calendar,
             year = p_year, month = p_month, day = p_day, updated_at = now()
       where id = p_id and user_id = uid
      returning * into rec;
      if rec.id is null then
        raise exception 'no date with that id' using errcode = 'P0002';
      end if;
    end if;
  exception
    when check_violation or not_null_violation then
      raise exception 'invalid date' using errcode = '22023';
    when unique_violation then
      raise exception 'that person already has a birthday saved' using errcode = '23505';
  end;
  return rec;
end;
$$;

create function public.forget_family_date(p_id uuid)
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
  delete from public.family_dates where id = p_id and user_id = uid;
  if found then
    perform public.snafi_scrub_log(uid, 'family_dates', array[p_id]);
  end if;
end;
$$;

revoke all on function public.save_fact(uuid, text, text), public.forget_fact(uuid),
  public.save_family_member(uuid, text, text, text), public.forget_family_member(uuid),
  public.save_family_date(uuid, uuid, text, text, text, integer, integer, integer), public.forget_family_date(uuid)
  from public, anon;
grant execute on function public.save_fact(uuid, text, text), public.forget_fact(uuid),
  public.save_family_member(uuid, text, text, text), public.forget_family_member(uuid),
  public.save_family_date(uuid, uuid, text, text, text, integer, integer, integer), public.forget_family_date(uuid)
  to authenticated;
-- snafi_norm and snafi_memory_ok are pure checks of a text (they read no table) and keep the default
-- execute: the CHECK constraints and the definer functions above call them.

commit;
