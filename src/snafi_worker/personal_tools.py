"""Ahmad's personal tools, each with its level fixed in code: Gmail and Yahoo Mail, Google Calendar,
Google Drive (step 3) and Todoist (step 4).

  Level 1  search_mail, read_mail, list_events, search_files, read_file, list_tasks, search_tasks
  Level 2  create_draft (Undo deletes that draft), create_event with only Khalid (Undo deletes
           that event, and only if Snafi created it), add_task (Undo deletes it, only if unchanged),
           complete_task (Undo reopens it, or puts a repeating task's date back), reschedule_task
           (Undo puts the old date back)
  Level 3  send_email, invite_to_event, delete_event, delete_draft, delete_task: an approval card
           showing the exact content; nothing runs until Khalid taps Approve
  Level 4  more than MAX_RECIPIENTS people in one send or invite (a mass message): refused

Two mail accounts (step 4): every mail tool works on "gmail" or "yahoo" (the `account` argument).
search_mail without an account reads both. An id says which account it is in (Yahoo ids start
with "y"), a reply always goes from the account the email came from, and every outcome line,
log entry and approval card names the account, written by code.

Everything a Level 1 tool reads (mail, event text, file text, task text) is outside content: it
goes to the brain only as untrusted data, and only ids and counts go into the action log. A send
can only come from an approved card, so an email that says "send X to Y" can at most cause a card.
"""

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from zoneinfo import ZoneInfo

from .google.http import GoogleError
from .personal.base import NotConnected, PartlySent, ServiceError
from .tool_types import NeverError, Tool, ToolArgError, ToolResult

MAX_RECIPIENTS = 5          # To + Cc + Bcc of one email, or the guests of one invite (Khalid, Nov 14, 2026)
BODY_MAX = 5000
SUBJECT_MAX = 200
UNTRUSTED_MAX = 12_000      # characters of outside content given to the brain from one tool
EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                   r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+\Z")   # \Z, not $ (SEC-112)
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}\Z")
CONTROL = re.compile("[\x00-\x08\x0a-\x1f\x7f\u2028\u2029]")  # any line break, bare \n included (SEC-82)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}\Z")
OFF = {"mail": ("Gmail", "Gmail"), "calendar": ("Google Calendar", "تقويم Google"), "files": ("Google Drive", "Google Drive"),
       "yahoo": ("Yahoo Mail", "Yahoo Mail"), "tasks": ("Todoist", "Todoist")}
# The mail accounts: account name -> (the Personal field, the name shown to Khalid).
ACCOUNTS = {"gmail": ("mail", "Gmail"), "yahoo": ("yahoo", "Yahoo")}
MAIL_WRITES = {"create_draft", "send_email", "delete_draft"}


def _short(text: str, n: int = 80) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _service(ctx: Dict, kind: str):
    personal = (ctx or {}).get("services")
    service = getattr(personal, kind, None) if personal else None
    if service is None:
        raise NotConnected(f"{OFF[kind][0]} is switched off in worker.yaml")
    return service


def label(account: str) -> str:
    return ACCOUNTS.get(account, ("", account))[1]


def _mail(ctx: Dict, account: str):
    return _service(ctx, ACCOUNTS[account][0])


def account_of_id(value: str) -> str:
    """Yahoo ids start with "y" (y<validity>_<uid>, yd... for drafts); Gmail ids never do."""
    return "yahoo" if (value or "").startswith("y") else "gmail"


def _check_account(args: Dict, *id_names: str, default: str = "gmail") -> Dict:
    """Sets args["account"] to the account the action runs in. An id decides it (a reply goes from the
    account the email came from); an account that disagrees with the id is refused."""
    given = str(args.get("account") or "").strip().lower()
    if given and given not in ACCOUNTS:
        raise ToolArgError("account must be gmail or yahoo")
    found = None
    for name in id_names:
        if args.get(name):
            here = account_of_id(args[name])
            if found and here != found:
                raise ToolArgError("those ids are in different accounts")
            found = here
    if given and found and given != found:
        raise ToolArgError(f"that email is in {label(found)}; a reply or draft for it goes from {label(found)}")
    if default or given or found:
        args["account"] = given or found or default
    return args


def _tz(ctx: Dict) -> ZoneInfo:
    return ZoneInfo((ctx or {}).get("time_zone") or "Asia/Riyadh")


def _limited(text: str) -> str:
    return text if len(text) <= UNTRUSTED_MAX else text[:UNTRUSTED_MAX] + "\n[cut here]"


# ---------- argument checks (run by the gate before any card or action) ----------
def _addresses(args: Dict, *names: str) -> int:
    seen = set()
    for name in names:
        clean = []
        for address in args.get(name) or []:
            if not EMAIL.match(address):
                raise ToolArgError(f"{name} has an address that is not valid: {_short(address, 60)}")
            if address.lower() not in seen:
                seen.add(address.lower())
                clean.append(address)
        if name in args:
            args[name] = clean
    if len(seen) > MAX_RECIPIENTS:
        raise NeverError(f"that is {len(seen)} people; I never send to more than {MAX_RECIPIENTS} at once")
    return len(seen)


def _subject(args: Dict, name: str = "subject") -> None:
    if name in args and CONTROL.search(args[name].replace("\t", " ")):
        raise ToolArgError(f"{name} must be one line")


def _id_arg(args: Dict, name: str) -> None:
    if name in args and not SAFE_ID.match(args[name]):
        raise ToolArgError(f"{name} is not a valid id")


def _when(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ToolArgError(f"{name} must be a date and time like 2026-11-20T09:00+03:00") from None
    if parsed.tzinfo is None:
        raise ToolArgError(f"{name} needs a time zone, like +03:00")
    return parsed


def _times(args: Dict) -> None:
    start, end = _when(args["start"], "start"), _when(args["end"], "end")
    if end <= start:
        raise ToolArgError("end must be after start")
    if end - start > timedelta(days=14):
        raise ToolArgError("an event can last at most 14 days")
    now = datetime.now(timezone.utc)
    if start < now - timedelta(days=1) or start > now + timedelta(days=730):
        raise ToolArgError("start must be between yesterday and two years from now")
    args["start"], args["end"] = start.isoformat(), end.isoformat()


def _check_mail(args: Dict, need_to: bool = True) -> Dict:
    count = _addresses(args, "to", "cc", "bcc")
    if need_to and not args.get("to"):
        raise ToolArgError("to is required")
    if count == 0:
        raise ToolArgError("at least one address is needed")
    _subject(args)
    _id_arg(args, "in_reply_to")
    return _check_account(args, "in_reply_to")


def _check_mail_id(args: Dict) -> Dict:
    _id_arg(args, "id")
    return _check_account(args, "id")


def _check_search_mail(args: Dict) -> Dict:
    return _check_account(args, default="")


def _check_due(args: Dict, required: bool = False) -> Dict:
    """A due date: a day ("2026-11-20") or a date and time with its offset."""
    value = args.get("due")
    if not value:
        if required:
            raise ToolArgError("due is required")
        return args
    if DATE.match(value):
        try:
            day = datetime.fromisoformat(value).date()
        except ValueError:
            raise ToolArgError("due must be a real date like 2026-11-20") from None
        today = datetime.now(timezone.utc).date()
        if not today - timedelta(days=1) <= day <= today + timedelta(days=730):
            raise ToolArgError("due must be between yesterday and two years from now")
        return args
    when = _when(value, "due")
    now = datetime.now(timezone.utc)
    if not now - timedelta(days=1) <= when <= now + timedelta(days=730):
        raise ToolArgError("due must be between yesterday and two years from now")
    args["due"] = when.isoformat()
    return args


def _check_task(args: Dict) -> Dict:
    _subject(args, "content")
    return _check_due(args)


def _check_reschedule(args: Dict) -> Dict:
    _id_arg(args, "id")
    return _check_due(args, required=True)


def _check_event(args: Dict, invite: bool = False) -> Dict:
    _subject(args, "title")
    _subject(args, "location")
    _times(args)
    if invite:
        if _addresses(args, "attendees") == 0:
            raise ToolArgError("attendees is required")
    return args


def _check_list_events(args: Dict) -> Dict:
    if args.get("date") and not DATE.match(args["date"]):
        raise ToolArgError("date must look like 2026-11-20")
    return args


def _check_ids(*names):
    def check(args):
        for name in names:
            _id_arg(args, name)
        return args
    return check


# ---------- Level 1: reads (outside content, untrusted) ----------
def _mail_line(m, account: str) -> str:
    flags = "".join([" [unread]" if m.unread else "", " [important]" if m.important else ""])
    return (f"[{label(account)}] id={m.id} | {m.date[:16]} | from: {m.sender} | subject: {m.subject}{flags}\n"
            f"  {m.snippet}")


def _connected_accounts(ctx: Dict) -> List[str]:
    personal = (ctx or {}).get("services")
    return [a for a, (field, _) in ACCOUNTS.items() if personal is not None and getattr(personal, field, None)]


def _search_mail(store, user_id, args, ctx):
    """One account, or both together when no account is given. Every line says which account it is in."""
    accounts = [args["account"]] if args.get("account") else _connected_accounts(ctx)
    if not accounts:
        raise NotConnected("Gmail and Yahoo Mail are both switched off in worker.yaml")
    found, problems = [], []
    for account in accounts:
        try:
            found += [(account, m) for m in _mail(ctx, account).search(args.get("query", ""), args.get("limit", 10))]
        except (ServiceError, ToolArgError) as exc:  # one account failing still shows the other
            if len(accounts) == 1:
                raise
            problems.append(f"{label(account)}: {str(exc)[:160]}")
    note = "".join(f"\n({p})" for p in problems)
    where = " and ".join(label(a) for a in accounts)
    if not found:
        return ToolResult(True, {"en": f"No emails matched in {where}.{note}", "ar": f"لا توجد رسائل مطابقة في {where}.{note}"},
                          {"count": 0, "accounts": accounts})
    shown = "\n".join(f"• [{label(a)}] {_short(m.sender, 40)}: {_short(m.subject, 70)}" for a, m in found)
    return ToolResult(True, {"en": f"Found {len(found)} emails in {where}:\n{shown}{note}",
                             "ar": f"وجدت {len(found)} رسائل في {where}:\n{shown}{note}"},
                      {"count": len(found), "ids": [m.id for _, m in found], "accounts": accounts},
                      untrusted=_limited("\n".join(_mail_line(m, a) for a, m in found)))


def _read_mail(store, user_id, args, ctx):
    account = args["account"]
    m = _mail(ctx, account).read(args["id"])
    text = (f"account: {label(account)}\nid={m.id}\nfrom: {m.sender}\nto: {m.to}\ncc: {m.cc}\ndate: {m.date}\n"
            f"subject: {m.subject}\n\n{m.body}")
    who, subject, where = _short(m.sender, 50), _short(m.subject, 70), label(account)
    return ToolResult(True, {"en": f"Read the {where} email from {who}: {subject}",
                             "ar": f"قرأت رسالة {who} في {where}: {subject}"},
                      {"id": m.id, "account": account}, untrusted=_limited(text))


def _list_events(store, user_id, args, ctx):
    tz = _tz(ctx)
    day = (datetime.fromisoformat(args["date"]).replace(tzinfo=tz) if args.get("date")
           else datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0))
    start, end = day, day + timedelta(days=args.get("days", 1))
    events = _service(ctx, "calendar").list_events(start.isoformat(), end.isoformat(), 25)
    if not events:
        return ToolResult(True, {"en": "No events in that time.", "ar": "لا توجد مواعيد في هذه الفترة."}, {"count": 0})

    def when(e):
        if e.all_day:
            return e.start
        return datetime.fromisoformat(e.start.replace("Z", "+00:00")).astimezone(tz).strftime("%a %d %b %H:%M")
    shown = "\n".join(f"• {when(e)}: {_short(e.title, 70)}" for e in events)
    detail = "\n".join(f"id={e.id} | {e.start} to {e.end} | {e.title} | place: {e.location} | "
                       f"guests: {len(e.attendees)}\n  {_short(e.description, 300)}" for e in events)
    return ToolResult(True, {"en": f"Your events:\n{shown}", "ar": f"مواعيدك:\n{shown}"},
                      {"count": len(events)}, untrusted=_limited(detail))


def _search_files(store, user_id, args, ctx):
    found = _service(ctx, "files").search(args["query"], args.get("limit", 10))
    if not found:
        return ToolResult(True, {"en": "No files matched.", "ar": "لا توجد ملفات مطابقة."}, {"count": 0})
    shown = "\n".join(f"• {_short(f.name, 80)}" for f in found)
    detail = "\n".join(f"id={f.id} | {f.name} | {f.mime_type} | modified {f.modified}" for f in found)
    return ToolResult(True, {"en": f"Found {len(found)} files:\n{shown}", "ar": f"وجدت {len(found)} ملفات:\n{shown}"},
                      {"count": len(found)}, untrusted=_limited(detail))


def _read_file(store, user_id, args, ctx):
    text = _service(ctx, "files").read(args["id"])
    return ToolResult(True, {"en": "Read the file.", "ar": "قرأت الملف."}, {"id": args["id"]},
                      untrusted=_limited(f"file id={args['id']}\n\n{text}"))


# ---------- Level 2: with Undo ----------
def _create_draft(store, user_id, args, ctx):
    account = args["account"]
    draft = _mail(ctx, account).create_draft(args["to"], args.get("cc", []), args["subject"], args["body"],
                                             args.get("in_reply_to"))
    to, subject, where = ", ".join(args["to"]), _short(args["subject"], 70), label(account)
    return ToolResult(True, {"en": f"Draft saved in {where} (not sent) to {to}: {subject}",
                             "ar": f"حُفظت مسودة في {where} (لم تُرسل) إلى {to}: {subject}"},
                      {"draft_id": draft.id, "account": account},
                      {"kind": "draft", "account": account, "id": draft.id})


def _create_event(store, user_id, args, ctx):
    event = _service(ctx, "calendar").create_event(args["title"], args["start"], args["end"],
                                                   args.get("location", ""), args.get("description", ""), None)
    title = _short(args["title"], 70)
    return ToolResult(True, {"en": f"Added to your calendar (only you): {title}, {args['start'][:16]}",
                             "ar": f"أُضيف إلى تقويمك (أنت فقط): {title}، {args['start'][:16]}"},
                      {"event_id": event.id}, {"kind": "event", "id": event.id})


def _undo_google(store, undo: Dict, ctx: Dict):
    """Undo for drafts (either account), events and tasks."""
    if undo.get("kind") == "draft":
        account = undo.get("account") or "gmail"  # drafts from step 3 have no account: Gmail
        if account not in ACCOUNTS or account_of_id(undo["id"]) != account:
            raise ServiceError("nothing to undo")
        _mail(ctx, account).delete_draft(undo["id"])
    elif str(undo.get("kind", "")).startswith("task_"):
        _undo_task(undo, ctx)
    elif undo.get("kind") == "event":
        calendar = _service(ctx, "calendar")
        if not calendar.get_event(undo["id"]).created_by_snafi:
            raise ServiceError("that event was not made by Snafi, so Undo will not delete it")
        calendar.delete_event(undo["id"])
    else:
        raise ServiceError("nothing to undo")


# ---------- Level 3: approval card first ----------
def _from_line(account: str, address: str) -> str:
    return f"{label(account)} ({address})" if address else label(account)


def _prepare_send(args: Dict, ctx: Dict) -> Dict:
    """The card shows which account the email goes from (and its address, when the account knows it)."""
    account = args.get("account") or "gmail"
    address = getattr(_mail(ctx, account), "address", None) or ""
    return {**args, "account": account, "from_address": _short(address, 254)}


def _send_email(store, user_id, args, ctx):
    account = args.get("account") or "gmail"
    mail = _mail(ctx, account)
    if (getattr(mail, "address", None) or "") != args.get("from_address", ""):
        raise ServiceError(f"the {label(account)} account changed after you approved; nothing was sent")
    everyone = args["to"] + args.get("cc", []) + args.get("bcc", [])
    people, subject, sender = ", ".join(everyone), _short(args["subject"], 70), _from_line(account, args.get("from_address", ""))
    try:
        mail.send(args["to"], args.get("cc", []), args.get("bcc", []), args["subject"], args["body"],
                  args.get("in_reply_to"))
    except PartlySent as exc:  # it went out, but not to everyone: say exactly that
        refused = ", ".join(exc.refused) or "some recipients"
        return ToolResult(True, {"en": f"Email sent from {sender} to {people}: {subject}. But {label(account)} "
                                       f"refused: {refused}",
                                 "ar": f"أُرسل البريد من {sender} إلى {people}: {subject}. لكن {label(account)} "
                                       f"رفض: {refused}"},
                          {"sent": True, "account": account, "recipients": len(everyone), "refused": len(exc.refused)})
    return ToolResult(True, {"en": f"Email sent from {sender} to {people}: {subject}",
                             "ar": f"أُرسل البريد من {sender} إلى {people}: {subject}"},
                      {"sent": True, "account": account, "recipients": len(everyone)})


def _invite(store, user_id, args, ctx):
    event = _service(ctx, "calendar").create_event(args["title"], args["start"], args["end"], args.get("location", ""),
                                                   args.get("description", ""), args["attendees"])
    who = ", ".join(args["attendees"])
    return ToolResult(True, {"en": f"Invitation sent to {who}: {_short(args['title'], 70)}",
                             "ar": f"أُرسلت الدعوة إلى {who}: {_short(args['title'], 70)}"},
                      {"event_id": event.id, "invited": len(args["attendees"])})


def _prepare_delete_event(args: Dict, ctx: Dict) -> Dict:
    event = _service(ctx, "calendar").get_event(args["id"])
    return {**args, "event_title": _short(event.title, 200), "event_start": event.start,
            "guests_notified": "no"}


def _delete_event(store, user_id, args, ctx):
    calendar = _service(ctx, "calendar")
    event = calendar.get_event(args["id"])
    if (_short(event.title, 200), event.start) != (args.get("event_title"), args.get("event_start")):
        raise ServiceError("the event changed after you approved; nothing was deleted")
    calendar.delete_event(args["id"])
    return ToolResult(True, {"en": f"Deleted from your calendar: {args['event_title']}",
                             "ar": f"حُذف من تقويمك: {args['event_title']}"}, {"deleted": args["id"]})


def _prepare_delete_draft(args: Dict, ctx: Dict) -> Dict:
    account = args.get("account") or "gmail"
    draft = _mail(ctx, account).get_draft(args["id"])
    return {**args, "account": account, "draft_to": _short(draft.to, 200), "draft_subject": _short(draft.subject, 200)}


def _delete_draft(store, user_id, args, ctx):
    account = args.get("account") or "gmail"
    if account_of_id(args["id"]) != account:
        raise ServiceError("that draft is not in this account; nothing was deleted")
    mail = _mail(ctx, account)
    draft = mail.get_draft(args["id"])
    if (_short(draft.to, 200), _short(draft.subject, 200)) != (args.get("draft_to"), args.get("draft_subject")):
        raise ServiceError("the draft changed after you approved; nothing was deleted")
    mail.delete_draft(args["id"])
    where = label(account)
    return ToolResult(True, {"en": f"{where} draft deleted: {args['draft_subject']}",
                             "ar": f"حُذفت مسودة {where}: {args['draft_subject']}"},
                      {"deleted": args["id"], "account": account})


# ---------- Todoist (step 4) ----------
def _due_text(task) -> str:
    if not task.due:
        return "no date"
    return task.due[:16].replace("T", " ") + (f" (repeats: {_short(task.due_string, 40)})" if task.recurring else "")


def _task_line(t) -> str:
    return (f"id={t.id} | due {_due_text(t)} | p{t.priority} | {t.content}"
            + (f"\n  {_short(t.description, 300)}" if t.description else ""))


def _task_list(found, en_title: str, ar_title: str, none_en: str, none_ar: str) -> ToolResult:
    if not found:
        return ToolResult(True, {"en": none_en, "ar": none_ar}, {"count": 0})
    shown = "\n".join(f"• {_short(t.content, 80)} ({_due_text(t)})" for t in found)
    return ToolResult(True, {"en": f"{en_title}:\n{shown}", "ar": f"{ar_title}:\n{shown}"},
                      {"count": len(found), "ids": [t.id for t in found]},
                      untrusted=_limited("\n".join(_task_line(t) for t in found)))


SHOW_TASKS = 30            # tasks shown in one list; the rest are counted ("and N more")
ALL_TASKS_MAX = 1000       # open tasks read for "all", at most
GROUPS = {"overdue": ("Overdue", "متأخرة"), "today": ("Today", "اليوم"), "tomorrow": ("Tomorrow", "غداً"),
          "none": ("No date", "بلا موعد")}


def _check_list_tasks(args: Dict) -> Dict:
    when = str(args.get("when") or "today").strip().lower()
    if when not in ("today", "all"):
        raise ToolArgError('when must be "today" (today and overdue) or "all" (every open task)')
    args["when"] = when
    return args


def _task_group(task, today, now: datetime, tz: ZoneInfo) -> str:
    """overdue, today, tomorrow, a date (YYYY-MM-DD), or none; in Khalid's time zone."""
    if not task.due:
        return "none"
    try:
        if len(task.due) == 10:
            day = datetime.fromisoformat(task.due).date()
            late = day < today
        else:
            when = datetime.fromisoformat(task.due.replace("Z", "+00:00"))
            when = when.replace(tzinfo=tz) if when.tzinfo is None else when.astimezone(tz)
            day, late = when.date(), when < now
    except ValueError:
        return "none"
    if late:
        return "overdue"
    if day == today:
        return "today"
    if day == today + timedelta(days=1):
        return "tomorrow"
    return day.isoformat()


def _local_time(due: str, tz: ZoneInfo) -> str:
    try:
        when = datetime.fromisoformat(due.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return (when if when.tzinfo is None else when.astimezone(tz)).strftime("%H:%M")


def _grouped(found, ctx: Dict, show: int):
    """Tasks by due date (overdue, today, tomorrow, later dates, no date), at most `show` of them."""
    tz = _tz(ctx)
    now = datetime.now(tz)
    keyed = [(_task_group(t, now.date(), now, tz), t) for t in found]

    def order(pair):
        group, task = pair
        rank = {"overdue": "0", "today": "1", "tomorrow": "2", "none": "9"}.get(group, "3" + group)
        return (rank, task.priority, task.due or "")
    keyed.sort(key=order)
    shown = keyed[:show]
    lines = {"en": [], "ar": []}
    last = None
    for group, task in shown:
        if group != last:
            en, ar = GROUPS.get(group) or (datetime.fromisoformat(group).strftime("%a %d %b"), group)
            lines["en"].append(f"{en}:")
            lines["ar"].append(f"{ar}:")
            last = group
        at = f" {_local_time(task.due, tz)}" if len(task.due) > 10 else ""
        repeat = f" (repeats: {_short(task.due_string, 30)})" if task.recurring else ""
        for lang in ("en", "ar"):
            lines[lang].append(f"• {_short(task.content, 80)}{at}{repeat}")
    return [t for _, t in shown], lines


def _list_tasks(store, user_id, args, ctx):
    tasks = _service(ctx, "tasks")
    show = min(args.get("limit", SHOW_TASKS if args.get("when") == "all" else 20), SHOW_TASKS)
    if args.get("when") == "all":
        found = tasks.all_open(ALL_TASKS_MAX)
        if not found:
            return ToolResult(True, {"en": "You have no open Todoist tasks.", "ar": "لا توجد مهام مفتوحة في Todoist."},
                              {"count": 0})
        shown, lines = _grouped(found, ctx, show)
        more = len(found) - len(shown)
        tail = {"en": f"\n…and {more} more" if more else "", "ar": f"\n…و{more} أخرى" if more else ""}
        en_title = f"All your open Todoist tasks ({len(found)}), by due date"
        ar_title = f"كل مهامك المفتوحة في Todoist ({len(found)})، حسب الموعد"
        return ToolResult(True, {"en": f"{en_title}:\n" + "\n".join(lines["en"]) + tail["en"],
                                 "ar": f"{ar_title}:\n" + "\n".join(lines["ar"]) + tail["ar"]},
                          {"count": len(found), "shown": len(shown), "ids": [t.id for t in shown]},
                          untrusted=_limited("\n".join(_task_line(t) for t in shown)
                                             + (f"\n(and {more} more not listed)" if more else "")))
    found = tasks.today(show)
    return _task_list(found, "Your Todoist tasks for today and overdue", "مهامك في Todoist لليوم والمتأخرة",
                      "No Todoist tasks for today, and nothing overdue.", "لا مهام في Todoist لليوم ولا متأخرة.")


def _search_tasks(store, user_id, args, ctx):
    found = _service(ctx, "tasks").search(args["query"], args.get("limit", 10))
    return _task_list(found, f"Found {len(found)} Todoist tasks", f"وجدت {len(found)} مهام في Todoist",
                      "No Todoist tasks matched.", "لا توجد مهام مطابقة في Todoist.")


def _content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _add_task(store, user_id, args, ctx):
    task = _service(ctx, "tasks").add(args["content"], args.get("description", ""), args.get("due", ""),
                                      args.get("priority", 4))
    text, when = _short(args["content"], 80), (f", {args['due'][:16]}" if args.get("due") else "")
    return ToolResult(True, {"en": f"Added to Todoist: {text}{when}", "ar": f"أُضيفت إلى Todoist: {text}{when}"},
                      {"task_id": task.id},
                      {"kind": "task_add", "id": task.id, "content_sha256": _content_hash(task.content)})


def _complete_task(store, user_id, args, ctx):
    tasks = _service(ctx, "tasks")
    task = tasks.get(args["id"])
    if task.done:
        raise ServiceError("that task is already completed; nothing was changed")
    tasks.complete(task.id)
    text = _short(task.content, 80)
    undo = {"kind": "task_complete", "id": task.id, "recurring": task.recurring, "due": task.due,
            "due_string": task.due_string}
    if task.recurring:
        return ToolResult(True, {"en": f"Completed in Todoist: {text}. It repeats, so it moved to its next date",
                                 "ar": f"أُنجزت في Todoist: {text}. إنها متكررة فانتقلت إلى موعدها التالي"},
                          {"task_id": task.id, "recurring": True}, undo)
    return ToolResult(True, {"en": f"Completed in Todoist: {text}", "ar": f"أُنجزت في Todoist: {text}"},
                      {"task_id": task.id}, undo)


def _reschedule_task(store, user_id, args, ctx):
    tasks = _service(ctx, "tasks")
    task = tasks.get(args["id"])
    if task.done:
        raise ServiceError("that task is completed; nothing was changed")
    tasks.set_due(task.id, args["due"], task.due_string, task.recurring)
    text = _short(task.content, 80)
    return ToolResult(True, {"en": f"Moved in Todoist: {text}, now {args['due'][:16]} (was {_due_text(task)})",
                             "ar": f"نُقلت في Todoist: {text}، الآن {args['due'][:16]} (كانت {_due_text(task)})"},
                      {"task_id": task.id},
                      {"kind": "task_due", "id": task.id, "due": task.due, "due_string": task.due_string,
                       "recurring": task.recurring})


def _undo_task(undo: Dict, ctx: Dict) -> None:
    tasks = _service(ctx, "tasks")
    kind, task_id = undo.get("kind"), undo.get("id", "")
    if not SAFE_ID.match(task_id or ""):
        raise ServiceError("nothing to undo")
    if kind == "task_add":
        task = tasks.get(task_id)
        if _content_hash(task.content) != undo.get("content_sha256"):
            raise ServiceError("that task changed after Snafi added it, so Undo will not delete it")
        tasks.delete(task_id)
    elif kind == "task_complete":
        if undo.get("recurring"):
            tasks.set_due(task_id, undo.get("due", ""), undo.get("due_string", ""), True)
        else:
            tasks.reopen(task_id)
    elif kind == "task_due":
        tasks.set_due(task_id, undo.get("due", ""), undo.get("due_string", ""), bool(undo.get("recurring")))
    else:
        raise ServiceError("nothing to undo")


def _prepare_delete_task(args: Dict, ctx: Dict) -> Dict:
    task = _service(ctx, "tasks").get(args["id"])
    return {**args, "task_content": _short(task.content, 200), "task_due": _due_text(task)}


def _delete_task(store, user_id, args, ctx):
    tasks = _service(ctx, "tasks")
    task = tasks.get(args["id"])
    if (_short(task.content, 200), _due_text(task)) != (args.get("task_content"), args.get("task_due")):
        raise ServiceError("the task changed after you approved; nothing was deleted")
    tasks.delete(args["id"])
    return ToolResult(True, {"en": f"Deleted from Todoist: {args['task_content']}",
                             "ar": f"حُذفت من Todoist: {args['task_content']}"}, {"deleted": args["id"]})


# ---------- descriptions (what the log and the approval card say) ----------
def _d(en: str, ar: str):
    return lambda a: {"en": en.format(**_fmt(a)), "ar": ar.format(**_fmt(a))}


def _fmt(a: Dict) -> Dict:
    people = a.get("to", []) + a.get("cc", []) + a.get("bcc", [])
    return {"subject": _short(a.get("subject", ""), 80), "to": ", ".join(people or a.get("attendees", [])),
            "title": _short(a.get("title", "") or a.get("event_title", ""), 80), "start": str(a.get("start", ""))[:16],
            "query": _short(a.get("query", ""), 60), "id": a.get("id", ""),
            "draft": _short(a.get("draft_subject", "") or a.get("id", ""), 80),
            "account": label(a["account"]) if a.get("account") else "Gmail and Yahoo",
            "from": _from_line(a.get("account") or "gmail", a.get("from_address", "")),
            "task": _short(a.get("task_content", "") or a.get("content", "") or a.get("id", ""), 80),
            "due": str(a.get("due", "") or a.get("task_due", ""))[:16] or "no date"}


EMAILS = (list, MAX_RECIPIENTS, False)
ACCOUNT = (str, 10, False)
PERSONAL_TOOLS: List[Tool] = [
    Tool("search_mail", 1, {"query": (str, 200, False), "limit": (int, 20, False), "account": ACCOUNT}, _search_mail,
         describe=_d("Search mail ({account}): {query}", "بحث في البريد ({account}): {query}"),
         validate=_check_search_mail, reads_outside=True),
    Tool("read_mail", 1, {"id": (str, 128, True), "account": ACCOUNT}, _read_mail,
         describe=_d("Read a {account} email", "قراءة رسالة في {account}"), validate=_check_mail_id, reads_outside=True),
    Tool("list_events", 1, {"date": (str, 10, False), "days": (int, 31, False)}, _list_events,
         describe=_d("Look at your calendar", "الاطلاع على تقويمك"), validate=_check_list_events, reads_outside=True),
    Tool("search_files", 1, {"query": (str, 200, True), "limit": (int, 20, False)}, _search_files,
         describe=_d("Search Drive: {query}", "بحث في Drive: {query}"), reads_outside=True),
    Tool("read_file", 1, {"id": (str, 200, True)}, _read_file,
         describe=_d("Read a Drive file", "قراءة ملف من Drive"), validate=_check_ids("id"), reads_outside=True),
    Tool("create_draft", 2, {"to": EMAILS, "cc": EMAILS, "subject": (str, SUBJECT_MAX, True),
                             "body": (str, BODY_MAX, True), "in_reply_to": (str, 128, False), "account": ACCOUNT},
         _create_draft, _undo_google, _d("{account} draft (not sent) to {to}: {subject}",
                                         "مسودة في {account} (لا تُرسل) إلى {to}: {subject}"),
         lambda a: _check_mail(a)),
    Tool("create_event", 2, {"title": (str, 200, True), "start": (str, 40, True), "end": (str, 40, True),
                             "location": (str, 200, False), "description": (str, 2000, False)},
         _create_event, _undo_google, _d("Calendar event (only you): {title}, {start}", "موعد في التقويم (أنت فقط): {title}، {start}"),
         lambda a: _check_event(a)),
    Tool("send_email", 3, {"to": EMAILS, "cc": EMAILS, "bcc": EMAILS, "subject": (str, SUBJECT_MAX, True),
                           "body": (str, BODY_MAX, True), "in_reply_to": (str, 128, False), "account": ACCOUNT},
         _send_email, None, _d("Send from {from} to {to}: {subject}", "إرسال من {from} إلى {to}: {subject}"),
         lambda a: _check_mail(a), prepare=_prepare_send, sends=True),
    Tool("invite_to_event", 3, {"title": (str, 200, True), "start": (str, 40, True), "end": (str, 40, True),
                                "attendees": EMAILS, "location": (str, 200, False), "description": (str, 2000, False)},
         _invite, None, _d("Invite {to} to: {title}, {start}", "دعوة {to} إلى: {title}، {start}"),
         lambda a: _check_event(a, invite=True), sends=True),
    Tool("delete_event", 3, {"id": (str, 200, True)}, _delete_event, None,
         _d("Delete from your calendar (guests not notified): {title}", "حذف من تقويمك (دون إشعار الضيوف): {title}"),
         _check_ids("id"), prepare=_prepare_delete_event),
    Tool("delete_draft", 3, {"id": (str, 128, True), "account": ACCOUNT}, _delete_draft, None,
         _d("Delete the {account} draft: {draft}", "حذف مسودة {account}: {draft}"), _check_mail_id,
         prepare=_prepare_delete_draft),
    # Step 4: Todoist
    Tool("list_tasks", 1, {"when": (str, 10, False), "limit": (int, SHOW_TASKS, False)}, _list_tasks,
         describe=_d("Look at your Todoist tasks", "الاطلاع على مهامك في Todoist"), validate=_check_list_tasks,
         reads_outside=True),
    Tool("search_tasks", 1, {"query": (str, 200, True), "limit": (int, 20, False)}, _search_tasks,
         describe=_d("Search Todoist: {query}", "بحث في Todoist: {query}"), reads_outside=True),
    Tool("add_task", 2, {"content": (str, 500, True), "description": (str, 2000, False), "due": (str, 40, False),
                         "priority": (int, 4, False)},
         _add_task, _undo_google, _d("Add to Todoist: {task} ({due})", "إضافة إلى Todoist: {task} ({due})"), _check_task),
    Tool("complete_task", 2, {"id": (str, 64, True)}, _complete_task, _undo_google,
         _d("Complete in Todoist: {task}", "إنجاز في Todoist: {task}"), _check_ids("id")),
    Tool("reschedule_task", 2, {"id": (str, 64, True), "due": (str, 40, True)}, _reschedule_task, _undo_google,
         _d("Move in Todoist to {due}: {task}", "نقل في Todoist إلى {due}: {task}"), _check_reschedule),
    Tool("delete_task", 3, {"id": (str, 64, True)}, _delete_task, None,
         _d("Delete from Todoist: {task} (due {due})", "حذف من Todoist: {task} (موعدها {due})"), _check_ids("id"),
         prepare=_prepare_delete_task),
]

# Errors a personal tool may raise; their messages are safe to show (no content, no tokens).
SAFE_ERRORS = (GoogleError, ToolArgError)
