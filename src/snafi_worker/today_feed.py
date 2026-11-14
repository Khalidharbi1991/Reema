"""The Today screen's Google part: the next event and up to five important unread emails.

Every few minutes (today_feed.minutes in worker.yaml, default 10) the worker reads Calendar and
Gmail, with no brain call, and writes one row to today_feed for Khalid. Only what the screen
shows leaves the PC: the next event's title, time and place, and each important email's sender
name, subject and time; never an email body. "Important" means unread, in the inbox, marked
Important by Gmail, from the last 24 hours (Khalid, Nov 14, 2026).

google_status tells the app what to show:
  ok             fresh data
  off            Gmail and Calendar are switched off in worker.yaml
  not_connected  Khalid has not run connect-google yet
  reconnect      Google no longer accepts the connection (7 days in Testing, revoked, password change)
  error          Google could not be reached this time
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from typing import Dict, Optional

from .google.http import GoogleAuthError, GoogleError, GoogleNotConnected

log = logging.getLogger("snafi_worker")
EMAILS = 5
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


def build_row(personal, owner_id: str, now: Optional[datetime] = None) -> Dict:
    now = now or datetime.now(timezone.utc)
    row = {"user_id": owner_id, "next_event": None, "emails": [], "google_status": "ok",
           "updated_at": now.isoformat()}
    mail, calendar = getattr(personal, "mail", None), getattr(personal, "calendar", None)
    if mail is None and calendar is None:
        row["google_status"] = "off"
        return row
    try:
        if calendar is not None:
            row["next_event"] = _next_event(calendar, now)
        if mail is not None:
            row["emails"] = [{"from": sender_name(m.sender), "subject": _cut(m.subject, 200) or "(no subject)",
                              "received_at": m.date} for m in mail.important_unread(HOURS, EMAILS)][:EMAILS]
    except GoogleNotConnected:
        row.update(next_event=None, emails=[], google_status="not_connected")
    except GoogleAuthError:
        row.update(next_event=None, emails=[], google_status="reconnect")
    except GoogleError as exc:
        log.warning("today feed: Google error (%s)", "retryable" if exc.retryable else "refused")
        row.update(next_event=None, emails=[], google_status="error")
    return row


class TodayFeed(threading.Thread):
    def __init__(self, store, personal, owner_id: str, minutes: float, stop: threading.Event):
        super().__init__(name="today-feed", daemon=True)
        self.store, self.personal, self.owner_id, self.stop = store, personal, owner_id, stop
        self.seconds = max(MIN_MINUTES, float(minutes)) * 60

    def refresh(self, now: Optional[datetime] = None) -> Dict:
        row = build_row(self.personal, self.owner_id, now)
        self.store.upsert("today_feed", row, "user_id")
        return row

    def run(self):
        while not self.stop.is_set():
            try:
                row = self.refresh()
                log.info("today feed: %s", row["google_status"])
            except Exception as exc:  # database unreachable: try again next time
                log.warning("today feed failed: %s", type(exc).__name__)
            self.stop.wait(self.seconds)
