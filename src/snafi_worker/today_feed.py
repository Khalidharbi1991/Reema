"""The Today screen's outside part: the next event, important unread emails and today's tasks.

Every few minutes (today_feed.minutes in worker.yaml, default 10) the worker reads Calendar,
Gmail, Yahoo and Todoist, with no brain call, and writes one row to today_feed for Khalid. Only
what the screen shows leaves the PC: the next event's title, time and place; each important
email's sender name, subject, time and account; and each task's title, due date, priority and
whether it is overdue (at most 10). Never an email body or a task description.
"Important" in Gmail means unread, in the inbox, marked Important by Gmail, from the last 24
hours; in Yahoo, which has no such mark, unread, in the Inbox, from the last 24 hours, and not a
newsletter, list or automatic email (Khalid, Nov 14, 2026). At most five from each account.

google_status, yahoo_status and todoist_status each tell the app what to show:
  ok             fresh data
  off            switched off in worker.yaml
  not_connected  not connected yet (connect-google for Google; set-secrets for Yahoo and Todoist)
  reconnect      the service no longer accepts the stored connection, app password or token
  error          the service could not be reached this time
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from typing import Dict, Optional

from zoneinfo import ZoneInfo

from .google.http import GoogleAuthError, GoogleError, GoogleNotConnected
from .personal.base import AuthRefused, NotConnected

log = logging.getLogger("snafi_worker")
EMAILS = 5          # per account
TASKS = 10
HOURS = 24
DAYS_AHEAD = 7
MIN_MINUTES = 2


def _cut(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text[:n]


def sender_name(sender: str) -> str:
    name, address = parseaddr(sender or "")
    return _cut(name or address or sender, 120)


def _next_event(calendar, now: datetime) -> Optional[Dict]:
    events = calendar.list_events(now.isoformat(), (now + timedelta(days=DAYS_AHEAD)).isoformat(), 10)
    timed = [e for e in events if not e.all_day]
    for event in timed + [e for e in events if e.all_day]:
        return {"title": _cut(event.title, 200) or "(no title)", "start": event.start, "end": event.end,
                "location": _cut(event.location, 200), "all_day": event.all_day}
    return None


def _status(exc: Exception) -> str:
    if isinstance(exc, (GoogleNotConnected, NotConnected)):
        return "not_connected"
    if isinstance(exc, (GoogleAuthError, AuthRefused)):
        return "reconnect"
    return "error"


def _emails(mail, account: str):
    return [{"from": sender_name(m.sender), "subject": _cut(m.subject, 200) or "(no subject)",
             "received_at": m.date, "account": account} for m in mail.important_unread(HOURS, EMAILS)][:EMAILS]


def _overdue(due: str, now: datetime, tz: ZoneInfo) -> bool:
    if not due:
        return False
    try:
        if len(due) == 10:
            return datetime.fromisoformat(due).date() < now.astimezone(tz).date()
        when = datetime.fromisoformat(due.replace("Z", "+00:00"))
        return (when.replace(tzinfo=tz) if when.tzinfo is None else when) < now
    except ValueError:
        return False


def _tasks(tasks, now: datetime, tz: ZoneInfo):
    """Today's and overdue Todoist tasks: overdue first, then the most urgent, then by time."""
    found = [(t, _overdue(t.due, now, tz)) for t in tasks.today(30)]
    found.sort(key=lambda pair: (not pair[1], pair[0].priority, pair[0].due or "9999"))
    return [{"content": _cut(t.content, 200) or "(no title)", "due": _with_offset(t.due, tz), "priority": int(t.priority),
             "overdue": overdue, "recurring": bool(t.recurring)} for t, overdue in found[:TASKS]]


def _with_offset(due: str, tz: ZoneInfo) -> str:
    """A day stays a day; a time gets its offset (Todoist gives local times without one)."""
    if not due or len(due) == 10:
        return _cut(due, 40)
    try:
        when = datetime.fromisoformat(due.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return (when.replace(tzinfo=tz) if when.tzinfo is None else when.astimezone(tz)).isoformat()[:40]


def build_row(personal, owner_id: str, now: Optional[datetime] = None, time_zone: str = "Asia/Riyadh") -> Dict:
    now = now or datetime.now(timezone.utc)
    tz = ZoneInfo(time_zone)
    row = {"user_id": owner_id, "next_event": None, "emails": [], "tasks": [], "google_status": "ok",
           "yahoo_status": "ok", "todoist_status": "ok", "updated_at": now.isoformat()}
    mail, calendar = getattr(personal, "mail", None), getattr(personal, "calendar", None)

    def google():
        next_event = _next_event(calendar, now) if calendar is not None else None
        gmail = _emails(mail, "gmail") if mail is not None else []
        row.update(next_event=next_event, emails=gmail)

    yahoo, tasks = getattr(personal, "yahoo", None), getattr(personal, "tasks", None)
    # Each source fails on its own, whatever the error (SEC-107): one bad email or task never stops
    # the others, and the row is still written.
    sources = (("google", "Google", None if mail is None and calendar is None else google),
               ("yahoo", "Yahoo", None if yahoo is None else (lambda: row.update(emails=row["emails"] + _emails(yahoo, "yahoo")))),
               ("todoist", "Todoist", None if tasks is None else (lambda: row.update(tasks=_tasks(tasks, now, tz)))))
    for key, name, refresh in sources:
        if refresh is None:
            row[f"{key}_status"] = "off"
            continue
        try:
            refresh()
        except Exception as exc:  # noqa: BLE001 (only the error's type is logged, never its text)
            status = _status(exc)
            if status == "error":
                kind = ("retryable" if exc.retryable else "refused") if isinstance(exc, GoogleError) else type(exc).__name__
                log.warning("today feed: %s error (%s)", name, kind)
            row[f"{key}_status"] = status
    return row


class TodayFeed(threading.Thread):
    def __init__(self, store, personal, owner_id: str, minutes: float, stop: threading.Event,
                 time_zone: str = "Asia/Riyadh"):
        super().__init__(name="today-feed", daemon=True)
        self.store, self.personal, self.owner_id, self.stop = store, personal, owner_id, stop
        self.seconds = max(MIN_MINUTES, float(minutes)) * 60
        self.time_zone = time_zone

    def refresh(self, now: Optional[datetime] = None) -> Dict:
        row = build_row(self.personal, self.owner_id, now, self.time_zone)
        self.store.upsert("today_feed", row, "user_id")
        return row

    def run(self):
        while not self.stop.is_set():
            try:
                row = self.refresh()
                log.info("today feed: google=%s yahoo=%s todoist=%s", row["google_status"], row["yahoo_status"],
                         row["todoist_status"])
            except Exception as exc:  # database unreachable: try again next time
                log.warning("today feed failed: %s", type(exc).__name__)
            self.stop.wait(self.seconds)
