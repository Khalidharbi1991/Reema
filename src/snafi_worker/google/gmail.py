"""Gmail adapter (provider "gmail"). Scopes: gmail.readonly to read, gmail.compose to make
drafts and to send. Sending runs only from an approved Level 3 card; this file just does
what the engine asks after the gate has decided.
"""

import base64
import html
import re
import urllib.parse
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

from ..personal.base import MAX_BODY, Draft, MailMessage, MailSummary, ServiceError
from ..personal.text import html_to_text
from ..registry import register
from .http import GoogleApi

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
ID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")  # \Z: no trailing newline (SEC-112)


def _id(value: str) -> str:
    if not isinstance(value, str) or not ID.match(value):
        raise ServiceError("that is not a Gmail id")
    return urllib.parse.quote(value, safe="")


def _headers(payload: Dict) -> Dict[str, str]:
    found = {}
    for h in (payload or {}).get("headers") or []:
        if isinstance(h, dict) and isinstance(h.get("name"), str) and isinstance(h.get("value"), str):
            found.setdefault(h["name"].lower(), h["value"][:1000])
    return found


def _date(headers: Dict[str, str], internal: Optional[str]) -> str:
    if internal and str(internal).isdigit():
        return datetime.fromtimestamp(int(internal) / 1000, timezone.utc).isoformat()
    try:
        return parsedate_to_datetime(headers.get("date", "")).isoformat()
    except (TypeError, ValueError):
        return ""


def _decode(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def _strip_html(text: str) -> str:
    return html_to_text(text)  # linear time (SEC-106: the regex version was quadratic on crafted HTML)


def body_text(payload: Dict) -> str:
    """The message's plain text (or its HTML made plain), at most MAX_BODY characters."""
    plain, rich = [], []

    def walk(part, depth=0):
        if not isinstance(part, dict) or depth > 8:
            return
        mime = str(part.get("mimeType") or "")
        data = (part.get("body") or {}).get("data")
        if isinstance(data, str) and not part.get("filename"):
            if mime == "text/plain":
                plain.append(_decode(data))
            elif mime == "text/html":
                rich.append(_strip_html(_decode(data)))
        for child in part.get("parts") or []:
            walk(child, depth + 1)

    walk(payload)
    text = "\n".join(plain) if plain else "\n".join(rich)
    return text.strip()[:MAX_BODY]


def build_raw(to: List[str], cc: List[str], bcc: List[str], subject: str, body: str,
              reply: Optional[Dict[str, str]] = None) -> str:
    msg = EmailMessage()
    if to:
        msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = subject
    if reply and reply.get("message_id"):
        msg["In-Reply-To"] = reply["message_id"]
        msg["References"] = reply["message_id"]
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")


@register("mail", "gmail")
class GmailMail:
    def __init__(self, options: dict, auth):
        self.api = GoogleApi(auth)

    def __repr__(self) -> str:
        return "GmailMail(tokens=hidden)"

    def _summary(self, message_id: str) -> MailSummary:
        data = self.api.call("GET", f"{BASE}/messages/{_id(message_id)}",
                             {"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]})
        h = _headers(data.get("payload"))
        labels = data.get("labelIds") or []
        return MailSummary(str(data.get("id") or message_id), str(data.get("threadId") or ""), h.get("from", ""),
                           h.get("subject", ""), _date(h, data.get("internalDate")),
                           html.unescape(str(data.get("snippet") or ""))[:300], "UNREAD" in labels, "IMPORTANT" in labels)

    def _list(self, query: str, limit: int) -> List[MailSummary]:
        data = self.api.call("GET", f"{BASE}/messages", {"q": query, "maxResults": max(1, min(limit, 20))})
        ids = [m.get("id") for m in data.get("messages") or [] if isinstance(m, dict)]
        return [self._summary(i) for i in ids if isinstance(i, str) and ID.match(i)]

    def search(self, query, limit):
        return self._list(query or "in:inbox", limit)

    def important_unread(self, hours, limit):
        days = max(1, -(-int(hours) // 24))
        found = self._list(f"is:unread in:inbox is:important newer_than:{days}d", limit)
        since = datetime.now(timezone.utc).timestamp() - hours * 3600
        return [m for m in found if not m.date or datetime.fromisoformat(m.date).timestamp() >= since]

    def watch_unread(self, hours, limit):
        """Mail watch (step 5): "truly important" in Gmail is unread, in the Inbox, marked Important by
        Gmail and in the Primary category (Khalid, Nov 14, 2026)."""
        days = max(1, -(-int(hours) // 24))
        found = self._list(f"is:unread in:inbox is:important category:primary newer_than:{days}d", limit)
        since = datetime.now(timezone.utc).timestamp() - hours * 3600
        return [m for m in found if not m.date or datetime.fromisoformat(m.date).timestamp() >= since]

    def read(self, message_id):
        data = self.api.call("GET", f"{BASE}/messages/{_id(message_id)}", {"format": "full"})
        payload = data.get("payload") or {}
        h = _headers(payload)
        return MailMessage(str(data.get("id") or message_id), str(data.get("threadId") or ""), h.get("from", ""),
                           h.get("to", ""), h.get("cc", ""), h.get("subject", ""), _date(h, data.get("internalDate")),
                           body_text(payload), h.get("message-id", ""))

    def _reply(self, in_reply_to: Optional[str]) -> Optional[Dict[str, str]]:
        if not in_reply_to:
            return None
        data = self.api.call("GET", f"{BASE}/messages/{_id(in_reply_to)}",
                             {"format": "metadata", "metadataHeaders": ["Message-ID"]})
        return {"message_id": _headers(data.get("payload")).get("message-id", ""),
                "thread_id": str(data.get("threadId") or "")}

    def create_draft(self, to, cc, subject, body, in_reply_to=None):
        reply = self._reply(in_reply_to)
        message = {"raw": build_raw(to, cc, [], subject, body, reply)}
        if reply and reply["thread_id"]:
            message["threadId"] = reply["thread_id"]
        data = self.api.call("POST", f"{BASE}/drafts", body={"message": message})
        draft_id = data.get("id")
        if not isinstance(draft_id, str) or not ID.match(draft_id):
            raise ServiceError("Gmail did not return the draft")
        return Draft(draft_id, ", ".join(to), subject)

    def get_draft(self, draft_id):
        data = self.api.call("GET", f"{BASE}/drafts/{_id(draft_id)}", {"format": "metadata"})
        h = _headers((data.get("message") or {}).get("payload"))
        return Draft(str(data.get("id") or draft_id), h.get("to", ""), h.get("subject", ""))

    def delete_draft(self, draft_id):
        self.api.call("DELETE", f"{BASE}/drafts/{_id(draft_id)}")

    def send(self, to, cc, bcc, subject, body, in_reply_to=None):
        reply = self._reply(in_reply_to)
        message = {"raw": build_raw(to, cc, bcc, subject, body, reply)}
        if reply and reply["thread_id"]:
            message["threadId"] = reply["thread_id"]
        data = self.api.call("POST", f"{BASE}/messages/send", body=message)
        sent = data.get("id")
        if not isinstance(sent, str):
            raise ServiceError("Gmail did not confirm the send")
        return sent
