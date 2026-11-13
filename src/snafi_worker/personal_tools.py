"""Ahmad's step 3 tools: Gmail, Google Calendar and Google Drive, each with its level fixed in code.

  Level 1  search_mail, read_mail, list_events, search_files, read_file
  Level 2  create_draft (Undo deletes that draft), create_event with only Khalid (Undo deletes
           that event, and only if Snafi created it)
  Level 3  send_email, invite_to_event, delete_event, delete_draft: an approval card showing the
           exact content; nothing runs until Khalid taps Approve
  Level 4  more than MAX_RECIPIENTS people in one send or invite (a mass message): refused

Everything a Level 1 tool reads (mail, event text, file text) is outside content: it goes to
the brain only as untrusted data, and only ids and counts go into the action log. A send can
only come from an approved card, so an email that says "send X to Y" can at most cause a card.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from zoneinfo import ZoneInfo

from .google.http import GoogleError
from .personal.base import NotConnected, ServiceError
from .tool_types import NeverError, Tool, ToolArgError, ToolResult

MAX_RECIPIENTS = 5          # To + Cc + Bcc of one email, or the guests of one invite (Khalid, Nov 14, 2026)
BODY_MAX = 5000
SUBJECT_MAX = 200
UNTRUSTED_MAX = 12_000      # characters of outside content given to the brain from one tool
EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                   r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OFF = {"mail": ("Gmail", "Gmail"), "calendar": ("Google Calendar", "تقويم Google"), "files": ("Google Drive", "Google Drive")}


def _short(text: str, n: int = 80) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _service(ctx: Dict, kind: str):
    personal = (ctx or {}).get("services")
    service = getattr(personal, kind, None) if personal else None
    if service is None:
        raise NotConnected(f"{OFF[kind][0]} is switched off in worker.yaml")
    return service


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
    return args


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
def _mail_line(m) -> str:
    flags = "".join([" [unread]" if m.unread else "", " [important]" if m.important else ""])
    return f"id={m.id} | {m.date[:16]} | from: {m.sender} | subject: {m.subject}{flags}\n  {m.snippet}"


def _search_mail(store, user_id, args, ctx):
    found = _service(ctx, "mail").search(args.get("query", ""), args.get("limit", 10))
    if not found:
        return ToolResult(True, {"en": "No emails matched.", "ar": "لا توجد رسائل مطابقة."}, {"count": 0})
    shown = "\n".join(f"• {_short(m.sender, 40)}: {_short(m.subject, 70)}" for m in found)
    return ToolResult(True, {"en": f"Found {len(found)} emails:\n{shown}", "ar": f"وجدت {len(found)} رسائل:\n{shown}"},
                      {"count": len(found), "ids": [m.id for m in found]},
                      untrusted=_limited("\n".join(_mail_line(m) for m in found)))


def _read_mail(store, user_id, args, ctx):
    m = _service(ctx, "mail").read(args["id"])
    text = (f"id={m.id}\nfrom: {m.sender}\nto: {m.to}\ncc: {m.cc}\ndate: {m.date}\nsubject: {m.subject}\n\n{m.body}")
    who, subject = _short(m.sender, 50), _short(m.subject, 70)
    return ToolResult(True, {"en": f"Read the email from {who}: {subject}", "ar": f"قرأت رسالة {who}: {subject}"},
                      {"id": m.id}, untrusted=_limited(text))


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
    draft = _service(ctx, "mail").create_draft(args["to"], args.get("cc", []), args["subject"], args["body"],
                                               args.get("in_reply_to"))
    to, subject = ", ".join(args["to"]), _short(args["subject"], 70)
    return ToolResult(True, {"en": f"Draft saved in Gmail (not sent) to {to}: {subject}",
                             "ar": f"حُفظت مسودة في Gmail (لم تُرسل) إلى {to}: {subject}"},
                      {"draft_id": draft.id}, {"kind": "draft", "id": draft.id})


def _create_event(store, user_id, args, ctx):
    event = _service(ctx, "calendar").create_event(args["title"], args["start"], args["end"],
                                                   args.get("location", ""), args.get("description", ""), None)
    title = _short(args["title"], 70)
    return ToolResult(True, {"en": f"Added to your calendar (only you): {title}, {args['start'][:16]}",
                             "ar": f"أُضيف إلى تقويمك (أنت فقط): {title}، {args['start'][:16]}"},
                      {"event_id": event.id}, {"kind": "event", "id": event.id})


def _undo_google(store, undo: Dict, ctx: Dict):
    if undo.get("kind") == "draft":
        _service(ctx, "mail").delete_draft(undo["id"])
    elif undo.get("kind") == "event":
        calendar = _service(ctx, "calendar")
        if not calendar.get_event(undo["id"]).created_by_snafi:
            raise ServiceError("that event was not made by Snafi, so Undo will not delete it")
        calendar.delete_event(undo["id"])
    else:
        raise ServiceError("nothing to undo")


# ---------- Level 3: approval card first ----------
def _send_email(store, user_id, args, ctx):
    _service(ctx, "mail").send(args["to"], args.get("cc", []), args.get("bcc", []), args["subject"], args["body"],
                               args.get("in_reply_to"))
    people = ", ".join(args["to"] + args.get("cc", []) + args.get("bcc", []))
    subject = _short(args["subject"], 70)
    return ToolResult(True, {"en": f"Email sent to {people}: {subject}", "ar": f"أُرسل البريد إلى {people}: {subject}"},
                      {"sent": True, "recipients": len(args["to"] + args.get("cc", []) + args.get("bcc", []))})


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
    draft = _service(ctx, "mail").get_draft(args["id"])
    return {**args, "draft_to": _short(draft.to, 200), "draft_subject": _short(draft.subject, 200)}


def _delete_draft(store, user_id, args, ctx):
    mail = _service(ctx, "mail")
    draft = mail.get_draft(args["id"])
    if (_short(draft.to, 200), _short(draft.subject, 200)) != (args.get("draft_to"), args.get("draft_subject")):
        raise ServiceError("the draft changed after you approved; nothing was deleted")
    mail.delete_draft(args["id"])
    return ToolResult(True, {"en": f"Draft deleted: {args['draft_subject']}", "ar": f"حُذفت المسودة: {args['draft_subject']}"},
                      {"deleted": args["id"]})


# ---------- descriptions (what the log and the approval card say) ----------
def _d(en: str, ar: str):
    return lambda a: {"en": en.format(**_fmt(a)), "ar": ar.format(**_fmt(a))}


def _fmt(a: Dict) -> Dict:
    people = a.get("to", []) + a.get("cc", []) + a.get("bcc", [])
    return {"subject": _short(a.get("subject", ""), 80), "to": ", ".join(people or a.get("attendees", [])),
            "title": _short(a.get("title", "") or a.get("event_title", ""), 80), "start": str(a.get("start", ""))[:16],
            "query": _short(a.get("query", ""), 60), "id": a.get("id", ""),
            "draft": _short(a.get("draft_subject", "") or a.get("id", ""), 80)}


EMAILS = (list, MAX_RECIPIENTS, False)
PERSONAL_TOOLS: List[Tool] = [
    Tool("search_mail", 1, {"query": (str, 200, False), "limit": (int, 20, False)}, _search_mail,
         describe=_d("Search mail: {query}", "بحث في البريد: {query}"), reads_outside=True),
    Tool("read_mail", 1, {"id": (str, 128, True)}, _read_mail,
         describe=_d("Read an email", "قراءة رسالة"), validate=_check_ids("id"), reads_outside=True),
    Tool("list_events", 1, {"date": (str, 10, False), "days": (int, 31, False)}, _list_events,
         describe=_d("Look at your calendar", "الاطلاع على تقويمك"), validate=_check_list_events, reads_outside=True),
    Tool("search_files", 1, {"query": (str, 200, True), "limit": (int, 20, False)}, _search_files,
         describe=_d("Search Drive: {query}", "بحث في Drive: {query}"), reads_outside=True),
    Tool("read_file", 1, {"id": (str, 200, True)}, _read_file,
         describe=_d("Read a Drive file", "قراءة ملف من Drive"), validate=_check_ids("id"), reads_outside=True),
    Tool("create_draft", 2, {"to": EMAILS, "cc": EMAILS, "subject": (str, SUBJECT_MAX, True),
                             "body": (str, BODY_MAX, True), "in_reply_to": (str, 128, False)},
         _create_draft, _undo_google, _d("Draft (not sent) to {to}: {subject}", "مسودة (لا تُرسل) إلى {to}: {subject}"),
         lambda a: _check_mail(a)),
    Tool("create_event", 2, {"title": (str, 200, True), "start": (str, 40, True), "end": (str, 40, True),
                             "location": (str, 200, False), "description": (str, 2000, False)},
         _create_event, _undo_google, _d("Calendar event (only you): {title}, {start}", "موعد في التقويم (أنت فقط): {title}، {start}"),
         lambda a: _check_event(a)),
    Tool("send_email", 3, {"to": EMAILS, "cc": EMAILS, "bcc": EMAILS, "subject": (str, SUBJECT_MAX, True),
                           "body": (str, BODY_MAX, True), "in_reply_to": (str, 128, False)},
         _send_email, None, _d("Send an email to {to}: {subject}", "إرسال بريد إلى {to}: {subject}"),
         lambda a: _check_mail(a), sends=True),
    Tool("invite_to_event", 3, {"title": (str, 200, True), "start": (str, 40, True), "end": (str, 40, True),
                                "attendees": EMAILS, "location": (str, 200, False), "description": (str, 2000, False)},
         _invite, None, _d("Invite {to} to: {title}, {start}", "دعوة {to} إلى: {title}، {start}"),
         lambda a: _check_event(a, invite=True), sends=True),
    Tool("delete_event", 3, {"id": (str, 200, True)}, _delete_event, None,
         _d("Delete from your calendar (guests not notified): {title}", "حذف من تقويمك (دون إشعار الضيوف): {title}"),
         _check_ids("id"), prepare=_prepare_delete_event),
    Tool("delete_draft", 3, {"id": (str, 128, True)}, _delete_draft, None,
         _d("Delete the Gmail draft: {draft}", "حذف مسودة Gmail: {draft}"), _check_ids("id"), prepare=_prepare_delete_draft),
]

# Errors a personal tool may raise; their messages are safe to show (no content, no tokens).
SAFE_ERRORS = (GoogleError, ToolArgError)
