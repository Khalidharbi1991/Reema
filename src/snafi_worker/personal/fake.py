"""Fake mail, calendar and files for offline tests: no network, no Google account.

They keep everything in memory and record every send, so a test can prove what did (or did
not) leave the PC.
"""

import itertools
from typing import Dict, List, Optional

from ..registry import register
from .base import Draft, Event, FileInfo, MailMessage, MailSummary, PartlySent, ServiceError, TaskItem

_ids = itertools.count(1)


def _next(prefix: str) -> str:
    return f"{prefix}{next(_ids)}"


@register("mail", "fake")
class FakeMail:
    """prefix "y" makes it act as the Yahoo account (its ids start with "y", like the real one's)."""

    def __init__(self, options: Optional[dict] = None, auth=None, prefix: str = "", address: Optional[str] = None):
        self.messages: Dict[str, MailMessage] = {}
        self.flags: Dict[str, Dict[str, bool]] = {}
        self.drafts: Dict[str, Dict] = {}
        self.sent: List[Dict] = []
        self.prefix = prefix
        self.address = address
        self.refuse: List[str] = []   # recipients the fake server refuses (a partly sent email)

    def add(self, sender: str, subject: str, body: str, date: str = "2026-11-14T08:00:00+03:00",
            unread: bool = True, important: bool = False, to: str = "khalid@example.com") -> str:
        mid = _next(self.prefix + "m")
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

    def watch_unread(self, hours, limit):
        """The mail watch's "truly important": important unread mail, minus any marked watch=False."""
        found = [m for m in self.messages.values() if self.flags[m.id]["unread"] and self.flags[m.id]["important"]
                 and self.flags[m.id].get("watch", True)]
        return [self._summary(m) for m in sorted(found, key=lambda m: m.date, reverse=True)[:limit]]

    def create_draft(self, to, cc, subject, body, in_reply_to=None):
        did = _next(self.prefix + "d")
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
                          "in_reply_to": in_reply_to, "from": self.address})
        refused = [a for a in list(to) + list(cc) + list(bcc) if a in self.refuse]
        if refused:
            raise PartlySent(f"the server refused {len(refused)} of the recipients", refused)
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


@register("tasks", "fake")
class FakeTasks:
    """Tasks in memory. A repeating task, when completed, moves to its next date and stays open."""

    def __init__(self, options: Optional[dict] = None, auth=None):
        self.tasks: Dict[str, TaskItem] = {}
        self.deleted: List[str] = []
        self.today_ids: List[str] = []
        self.next_dates: Dict[str, str] = {}

    def put(self, content, due="", priority=4, recurring=False, due_string="", today=True, next_date="") -> str:
        tid = _next("k")
        self.tasks[tid] = TaskItem(tid, content, "", due, due_string, recurring, priority)
        if today:
            self.today_ids.append(tid)
        if next_date:
            self.next_dates[tid] = next_date
        return tid

    def _get(self, task_id) -> TaskItem:
        if task_id not in self.tasks:
            raise ServiceError("not found in your Todoist")
        return self.tasks[task_id]

    def today(self, limit):
        return [self.tasks[t] for t in self.today_ids if t in self.tasks and not self.tasks[t].done][:limit]

    def all_open(self, most):
        return [t for t in self.tasks.values() if not t.done][:most]

    def search(self, query, limit):
        q = (query or "").lower()
        return [t for t in self.tasks.values() if not t.done and q in t.content.lower()][:limit]

    def get(self, task_id):
        return self._get(task_id)

    def add(self, content, description="", due="", priority=4):
        tid = _next("k")
        self.tasks[tid] = TaskItem(tid, content, description, due, "", False, priority)
        return self.tasks[tid]

    def _replace(self, task_id, **changes):
        from dataclasses import replace
        self.tasks[task_id] = replace(self._get(task_id), **changes)

    def complete(self, task_id):
        task = self._get(task_id)
        if task.recurring:
            self._replace(task_id, due=self.next_dates.get(task_id, task.due))
        else:
            self._replace(task_id, done=True)

    def reopen(self, task_id):
        self._replace(task_id, done=False)

    def set_due(self, task_id, due, due_string="", recurring=False):
        task = self._get(task_id)
        self._replace(task_id, due=due, due_string=due_string if recurring else task.due_string)

    def delete(self, task_id):
        self._get(task_id)
        del self.tasks[task_id]
        self.deleted.append(task_id)
