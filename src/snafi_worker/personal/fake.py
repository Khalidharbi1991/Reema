"""Fake mail, calendar and files for offline tests: no network, no Google account.

They keep everything in memory and record every send, so a test can prove what did (or did
not) leave the PC.
"""

import itertools
from typing import Dict, List, Optional

from ..registry import register
from .base import Draft, Event, FileInfo, MailMessage, MailSummary, ServiceError

_ids = itertools.count(1)


def _next(prefix: str) -> str:
    return f"{prefix}{next(_ids)}"


@register("mail", "fake")
class FakeMail:
    def __init__(self, options: Optional[dict] = None, auth=None):
        self.messages: Dict[str, MailMessage] = {}
        self.flags: Dict[str, Dict[str, bool]] = {}
        self.drafts: Dict[str, Dict] = {}
        self.sent: List[Dict] = []

    def add(self, sender: str, subject: str, body: str, date: str = "2026-11-14T08:00:00+03:00",
            unread: bool = True, important: bool = False, to: str = "khalid@example.com") -> str:
        mid = _next("m")
        self.messages[mid] = MailMessage(mid, "t" + mid, sender, to, "", subject, date, body, f"<{mid}@example.com>")
        self.flags[mid] = {"unread": unread, "important": important}
        return mid

    def _summary(self, m: MailMessage) -> MailSummary:
        f = self.flags[m.id]
        return MailSummary(m.id, m.thread_id, m.sender, m.subject, m.date, m.body[:120], f["unread"], f["important"])

    def search(self, query, limit):
        words = (query or "").lower().split()
        found = [m for m in self.messages.values()
                 if all(w in (m.subject + " " + m.body + " " + m.sender).lower() for w in words)]
        return [self._summary(m) for m in sorted(found, key=lambda m: m.date, reverse=True)[:limit]]

    def read(self, message_id):
        if message_id not in self.messages:
            raise ServiceError("not found in your Google account")
        return self.messages[message_id]

    def important_unread(self, hours, limit):
        found = [m for m in self.messages.values() if self.flags[m.id]["unread"] and self.flags[m.id]["important"]]
        return [self._summary(m) for m in sorted(found, key=lambda m: m.date, reverse=True)[:limit]]

    def create_draft(self, to, cc, subject, body, in_reply_to=None):
        did = _next("d")
        self.drafts[did] = {"to": list(to), "cc": list(cc), "subject": subject, "body": body,
                            "in_reply_to": in_reply_to}
        return Draft(did, ", ".join(to), subject)

    def get_draft(self, draft_id):
        if draft_id not in self.drafts:
            raise ServiceError("not found in your Google account")
        d = self.drafts[draft_id]
        return Draft(draft_id, ", ".join(d["to"]), d["subject"])

    def delete_draft(self, draft_id):
        if self.drafts.pop(draft_id, None) is None:
            raise ServiceError("not found in your Google account")

    def send(self, to, cc, bcc, subject, body, in_reply_to=None):
        self.sent.append({"to": list(to), "cc": list(cc), "bcc": list(bcc), "subject": subject, "body": body,
                          "in_reply_to": in_reply_to})
        return _next("s")


@register("calendar", "fake")
class FakeCalendar:
    def __init__(self, options: Optional[dict] = None, auth=None):
        self.events: Dict[str, Event] = {}
        self.invites_sent: List[Dict] = []

    def add(self, title, start, end, location="", description="", attendees=None, created_by_snafi=False) -> str:
        eid = _next("e")
        self.events[eid] = Event(eid, title, start, end, location, description, list(attendees or []),
                                 False, created_by_snafi)
        return eid

    def list_events(self, start, end, limit):
        found = [e for e in self.events.values() if start <= e.start < end or (e.start < start < e.end)]
        return sorted(found, key=lambda e: e.start)[:limit]

    def get_event(self, event_id):
        if event_id not in self.events:
            raise ServiceError("not found in your Google account")
        return self.events[event_id]

    def create_event(self, title, start, end, location="", description="", attendees=None):
        eid = self.add(title, start, end, location, description, attendees, created_by_snafi=True)
        if attendees:
            self.invites_sent.append({"event": eid, "attendees": list(attendees)})
        return self.events[eid]

    def delete_event(self, event_id):
        if self.events.pop(event_id, None) is None:
            raise ServiceError("not found in your Google account")


@register("files", "fake")
class FakeFiles:
    def __init__(self, options: Optional[dict] = None, auth=None):
        self.files: Dict[str, Dict] = {}

    def add(self, name: str, text: str, mime: str = "application/vnd.google-apps.document") -> str:
        fid = _next("f")
        self.files[fid] = {"info": FileInfo(fid, name, mime, "2026-11-14T08:00:00Z", f"https://drive.example/{fid}"),
                           "text": text}
        return fid

    def search(self, query, limit):
        q = (query or "").lower()
        return [f["info"] for f in self.files.values() if q in (f["info"].name + " " + f["text"]).lower()][:limit]

    def read(self, file_id):
        if file_id not in self.files:
            raise ServiceError("not found in your Google account")
        return self.files[file_id]["text"]
