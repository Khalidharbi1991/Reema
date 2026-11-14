"""Yahoo Mail adapter (provider "yahoo_imap"), standard library only.

  read and search   IMAP over TLS to imap.mail.yahoo.com:993, Inbox opened read-only and messages
                    fetched with BODY.PEEK, so reading never marks anything read
  drafts            IMAP APPEND into Yahoo's Drafts folder; Undo deletes only that draft (UID EXPUNGE)
  send              SMTP over TLS to smtp.mail.yahoo.com:465, run only from an approved Level 3 card

The hosts are fixed here, never taken from worker.yaml, and the certificate is always checked.
The login is Khalid's Yahoo address and an app password (YAHOO_EMAIL, YAHOO_APP_PASSWORD), stored
only in his Credential Manager. Neither is ever put in a log line, repr or error.

Ids: a Yahoo email is "y<UIDVALIDITY>_<UID>" and a draft "yd<UIDVALIDITY>_<UID>", so an id always
says which account it belongs to (Gmail ids never start with "y") and goes out of date if Yahoo
renumbers the folder.
"""

import imaplib
import re
import smtplib
import ssl
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from email.message import EmailMessage
from email.policy import default as default_policy
from email.utils import formatdate, getaddresses, make_msgid, parseaddr, parsedate_to_datetime
from typing import Callable, Dict, List, Optional, Tuple

from ..personal.base import (MAX_BODY, AuthRefused, Draft, MailMessage, MailSummary, PartlySent,
                             ServiceError)
from ..personal.credentials import usable
from ..personal.text import html_to_text
from ..registry import register

IMAP_HOST, IMAP_PORT = "imap.mail.yahoo.com", 993
SMTP_HOST, SMTP_PORT = "smtp.mail.yahoo.com", 465
SECRET_NAMES = ("YAHOO_EMAIL", "YAHOO_APP_PASSWORD")
INBOX = "INBOX"
DRAFTS_FALLBACK = "Draft"          # Yahoo's Drafts folder when the server does not mark it \Drafts
SENT_FALLBACK = "Sent"             # Yahoo's Sent folder when the server does not mark it \Sent
KNOWN_DAYS = 90                    # mail watch: people Khalid emailed from Yahoo in this many days
KNOWN_SCAN = 500                   # newest sent emails looked at for them
KNOWN_HOURS = 6                    # how long that list is kept before Sent is read again
MESSAGE_ID = re.compile(r"^y(\d{1,10})_(\d{1,10})\Z")   # \Z: a trailing newline does not pass (SEC-112)
DRAFT_ID = re.compile(r"^yd(\d{1,10})_(\d{1,10})\Z")
MAX_MESSAGE = 2_000_000            # bytes of one email fetched
SCAN = 50                          # newest emails looked at for the Today screen
HEADERS = "FROM TO CC SUBJECT DATE MESSAGE-ID LIST-UNSUBSCRIBE LIST-ID PRECEDENCE AUTO-SUBMITTED"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class YahooError(ServiceError):
    pass


def _imap_connect(timeout: float):
    return imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ssl.create_default_context(), timeout=timeout)


def _smtp_connect(timeout: float):
    return smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context(), timeout=timeout)


def _quote(text: str) -> str:
    """An IMAP quoted string. Control characters are refused (they could end the command)."""
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise YahooError("the search has a character Yahoo cannot take")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _imap_date(when: datetime) -> str:
    return f"{when.day:02d}-{MONTHS[when.month - 1]}-{when.year}"


def _strip_html(text: str) -> str:
    return html_to_text(text)  # linear time (SEC-106)


def _header(msg, name: str) -> str:
    try:
        value = msg.get(name)
    except Exception:  # a malformed header from the sender: shown as empty
        return ""
    return " ".join(str(value or "").split())[:1000]


def _date(msg, internal: str = "") -> str:
    """Always with an offset: a "-0000" Date gives a naive time, read as UTC (SEC-107)."""
    try:
        when = parsedate_to_datetime(_header(msg, "date"))
        return (when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.strptime(internal, "%d-%b-%Y %H:%M:%S %z").isoformat()
    except ValueError:
        return ""


def _bulk(msg) -> bool:
    """A newsletter, mailing list or automatic message: never "important" on the Today screen."""
    if _header(msg, "list-unsubscribe") or _header(msg, "list-id"):
        return True
    if _header(msg, "precedence").lower() in ("bulk", "list", "junk"):
        return True
    auto = _header(msg, "auto-submitted").lower()
    return bool(auto) and auto != "no"


def _fetch_items(data) -> List[Tuple[str, bytes]]:
    """imaplib FETCH data -> [(the response text, the literal bytes)] per message."""
    items: List[Tuple[str, bytes]] = []
    for part in data or []:
        if isinstance(part, tuple) and len(part) >= 2:
            items.append((part[0].decode("ascii", "replace"), part[1] or b""))
        elif isinstance(part, bytes) and items and part.strip() not in (b"", b")"):
            meta, literal = items[-1]
            items[-1] = (meta + " " + part.decode("ascii", "replace"), literal)  # FLAGS after the literal
    return items


def _uid(meta: str) -> str:
    found = re.search(r"\bUID (\d+)", meta)
    return found.group(1) if found else ""


def _uids_in(data) -> List[str]:
    """Every UID in FETCH data, with or without a literal part."""
    found = []
    for part in data or []:
        head = part[0] if isinstance(part, tuple) and part else part
        if isinstance(head, bytes):
            uid = _uid(head.decode("ascii", "replace"))
            if uid:
                found.append(uid)
    return found


def _flags(meta: str) -> str:
    found = re.search(r"\bFLAGS \(([^)]*)\)", meta)
    return found.group(1) if found else ""


def _internal(meta: str) -> str:
    found = re.search(r'\bINTERNALDATE "([^"]+)"', meta)
    return found.group(1) if found else ""


def _ok(typ, what: str):
    if typ != "OK":
        raise YahooError(f"Yahoo refused {what}")


def body_text(raw: bytes) -> Tuple[object, str]:
    msg = message_from_bytes(raw, policy=default_policy)
    text = ""
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is not None:
            content = part.get_content()
            text = _strip_html(content) if part.get_content_subtype() == "html" else content
    except (KeyError, LookupError, ValueError, AssertionError):
        text = ""
    return msg, str(text).strip()[:MAX_BODY]


class Query:
    """Gmail-style words made into IMAP SEARCH criteria: is:unread, is:starred, from:, to:, subject:,
    newer_than:Nd; every other word is searched in the whole message. One word outside plain English
    (Arabic, for example) is sent as UTF-8; further ones are matched against the sender and subject."""

    def __init__(self, text: str, now: datetime):
        self.criteria: List[str] = []
        self.literal: Optional[bytes] = None
        self.literal_key = "TEXT"
        self.local: List[str] = []
        for word in (text or "").split()[:12]:
            key, _, value = word.partition(":")
            key = key.lower()
            if word.lower() in ("is:unread",):
                self.criteria.append("UNSEEN")
            elif word.lower() == "is:read":
                self.criteria.append("SEEN")
            elif word.lower() in ("is:starred", "is:flagged"):
                self.criteria.append("FLAGGED")
            elif word.lower() in ("in:inbox", "is:important"):
                continue
            elif key == "newer_than" and re.fullmatch(r"\d{1,3}d", value.lower()):
                self.criteria += ["SINCE", _imap_date(now - timedelta(days=int(value[:-1])))]
            elif key in ("from", "to", "subject") and value:
                self._add(key.upper(), value)
            else:
                self._add("TEXT", word)
        if not self.criteria and self.literal is None:
            self.criteria.append("ALL")

    def _add(self, key: str, value: str) -> None:
        if value.isascii():
            self.criteria += [key, _quote(value)]
        elif self.literal is None:
            self.literal = value.encode("utf-8")
            self.literal_key = key
        else:
            self.local.append(value.lower())


@register("mail", "yahoo_imap")
class YahooMail:
    def __init__(self, options: dict, login, imap_connect: Optional[Callable] = None,
                 smtp_connect: Optional[Callable] = None, clock: Callable[[], datetime] = None):
        self.login = login
        self.timeout = float((options or {}).get("timeout_seconds", 30))
        self._imap_connect = imap_connect or _imap_connect
        self._smtp_connect = smtp_connect or _smtp_connect
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._known = None  # (when read, addresses) for the mail watch

    def __repr__(self) -> str:
        return "YahooMail(login=hidden)"

    @property
    def address(self) -> Optional[str]:
        try:
            return self.login.values()[0].strip()
        except ServiceError:
            return None

    def _credentials(self) -> Tuple[str, str]:
        address, password = self.login.values()
        return usable(address.strip(), "Yahoo address"), usable(password.replace(" ", ""), "Yahoo app password")

    # ---------- IMAP ----------
    @contextmanager
    def _imap(self):
        conn = None
        for attempt in (1, 2):
            address, password = self._credentials()
            try:
                conn = self._imap_connect(self.timeout)
            except (OSError, imaplib.IMAP4.error):
                raise YahooError("Yahoo unreachable", retryable=True) from None
            try:
                conn.login(address, password)
                break
            except (imaplib.IMAP4.abort, OSError, EOFError):  # a network or TLS drop is not a refusal (SEC-111)
                self._close(conn)
                raise YahooError("Yahoo dropped the connection", retryable=True) from None
            except imaplib.IMAP4.error:
                self._close(conn)
                if attempt == 1 and self.login.refused():
                    continue  # Khalid stored a new app password: try it once
                raise AuthRefused("Yahoo refused the app password; make a new one and store it with "
                                  "snafi.cmd set-secrets") from None
        try:
            yield conn
        except imaplib.IMAP4.abort:
            raise YahooError("Yahoo dropped the connection", retryable=True) from None
        except imaplib.IMAP4.error:
            raise YahooError("Yahoo refused the request") from None
        except (OSError, EOFError):
            raise YahooError("Yahoo unreachable", retryable=True) from None
        finally:
            self._close(conn)

    @staticmethod
    def _close(conn) -> None:
        try:
            conn.logout()
        except Exception:
            pass

    @staticmethod
    def _select(conn, folder: str, readonly: bool) -> str:
        typ, _ = conn.select(_quote(folder), readonly=readonly)
        _ok(typ, f"to open {folder}")
        _, data = conn.response("UIDVALIDITY")
        value = (data or [b""])[0]
        value = value.decode("ascii", "replace") if isinstance(value, bytes) else str(value or "")
        if not value.isdigit():
            raise YahooError("Yahoo did not say how the folder is numbered")
        return value

    @staticmethod
    def _drafts_folder(conn) -> str:
        typ, data = conn.list()
        if typ == "OK":
            for line in data or []:
                text = line.decode("utf-8", "replace") if isinstance(line, bytes) else str(line or "")
                found = re.match(r'^\(([^)]*)\)\s+(?:"[^"]*"|NIL)\s+(.+)$', text)
                if found and "\\drafts" in found.group(1).lower():
                    name = found.group(2).strip()
                    return name[1:-1].replace('\\"', '"').replace("\\\\", "\\") if name.startswith('"') else name
        return DRAFTS_FALLBACK

    @staticmethod
    def _parse(value: str, pattern) -> Tuple[str, str]:
        found = pattern.match(value or "")
        if not found:
            raise YahooError("that is not a Yahoo id")
        return found.group(1), found.group(2)

    def _search(self, conn, query: Query) -> List[str]:
        if query.literal is not None:
            conn.literal = query.literal
            typ, data = conn.uid("SEARCH", "CHARSET", "UTF-8", *query.criteria, query.literal_key)
        else:
            typ, data = conn.uid("SEARCH", *query.criteria)
        _ok(typ, "the search")
        uids = [u for u in b" ".join(d for d in data or [] if isinstance(d, bytes)).decode("ascii", "replace").split()
                if u.isdigit()]
        return sorted(uids, key=int, reverse=True)

    def _summaries(self, conn, validity: str, uids: List[str]) -> List[Tuple[MailSummary, object]]:
        if not uids:
            return []
        typ, data = conn.uid("FETCH", ",".join(uids),
                             f"(UID FLAGS INTERNALDATE BODY.PEEK[HEADER.FIELDS ({HEADERS})])")
        _ok(typ, "to list the emails")
        found = []
        for meta, raw in _fetch_items(data):
            uid = _uid(meta)
            if not uid:
                continue
            msg = message_from_bytes(raw, policy=default_policy)
            flags = _flags(meta).lower()
            found.append((MailSummary(f"y{validity}_{uid}", f"y{validity}_{uid}", _header(msg, "from"),
                                      _header(msg, "subject"), _date(msg, _internal(meta)), "",
                                      "\\seen" not in flags, "\\flagged" in flags), msg))
        order = {u: i for i, u in enumerate(uids)}
        return sorted(found, key=lambda pair: order.get(pair[0].id.split("_")[1], 0))

    def search(self, query, limit):
        limit = max(1, min(int(limit or 10), 20))
        q = Query(query, self._now())
        with self._imap() as conn:
            validity = self._select(conn, INBOX, readonly=True)
            uids = self._search(conn, q)[: limit if not q.local else SCAN]
            pairs = self._summaries(conn, validity, uids)
        found = [s for s, _ in pairs if all(w in (s.sender + " " + s.subject).lower() for w in q.local)]
        return found[:limit]

    def important_unread(self, hours, limit):
        """Unread, in the Inbox, from the last `hours` hours, and not a newsletter, list or automatic email
        (Khalid, Nov 14, 2026). Yahoo has no Important flag like Gmail's."""
        since = self._now() - timedelta(hours=int(hours))
        query = Query("is:unread", since)
        query.criteria += ["SINCE", _imap_date(since - timedelta(days=1))]  # IMAP SINCE is a whole day
        with self._imap() as conn:
            validity = self._select(conn, INBOX, readonly=True)
            pairs = self._summaries(conn, validity, self._search(conn, query)[:SCAN])
        out = []
        for summary, msg in pairs:
            if _bulk(msg):
                continue
            if summary.date:
                try:
                    when = datetime.fromisoformat(summary.date)
                    if (when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when) < since:
                        continue
                except (ValueError, TypeError):
                    continue
            out.append(summary)
        return out[: max(1, int(limit))]

    # ---------- mail watch (step 5) ----------
    @staticmethod
    def _sent_folder(conn) -> str:
        typ, data = conn.list()
        if typ == "OK":
            for line in data or []:
                text = line.decode("utf-8", "replace") if isinstance(line, bytes) else str(line or "")
                found = re.match(r'^\(([^)]*)\)\s+(?:"[^"]*"|NIL)\s+(.+)$', text)
                if found and "\\sent" in found.group(1).lower():
                    name = found.group(2).strip()
                    return name[1:-1].replace('\\"', '"').replace("\\\\", "\\") if name.startswith('"') else name
        return SENT_FALLBACK

    def known_correspondents(self, days: int = KNOWN_DAYS) -> set:
        """Every address Khalid sent to from Yahoo in the last `days` days (To, Cc and Bcc of the newest
        KNOWN_SCAN emails in Sent), lower case. Read-only; kept for KNOWN_HOURS hours."""
        now = self._now()
        if self._known is not None and now - self._known[0] < timedelta(hours=KNOWN_HOURS):
            return self._known[1]
        query = Query("", now)
        query.criteria = ["SINCE", _imap_date(now - timedelta(days=int(days)))]
        found = set()
        with self._imap() as conn:
            self._select(conn, self._sent_folder(conn), readonly=True)
            uids = self._search(conn, query)[:KNOWN_SCAN]
            if uids:
                typ, data = conn.uid("FETCH", ",".join(uids), "(UID BODY.PEEK[HEADER.FIELDS (TO CC BCC)])")
                _ok(typ, "to read Sent")
                for _, raw in _fetch_items(data):
                    msg = message_from_bytes(raw, policy=default_policy)
                    for name in ("to", "cc", "bcc"):
                        for _, address in getaddresses([_header(msg, name)]):
                            if "@" in address:
                                found.add(address.strip().lower())
        self._known = (now, found)
        return found

    def watch_unread(self, hours, limit):
        """Mail watch: "truly important" in Yahoo is the Today rule (unread, Inbox, last `hours` hours,
        not a newsletter, list or automatic email) and from someone Khalid emailed from Yahoo in the last
        90 days (Khalid, Nov 14, 2026)."""
        candidates = self.important_unread(hours, SCAN)
        if not candidates:
            return []
        known = self.known_correspondents()
        out = [s for s in candidates if parseaddr(s.sender)[1].strip().lower() in known]
        return out[: max(1, int(limit))]

    def _fetch_message(self, conn, uid: str):
        typ, data = conn.uid("FETCH", uid, f"(UID BODY.PEEK[]<0.{MAX_MESSAGE}>)")
        _ok(typ, "to open the email")
        items = [item for item in _fetch_items(data) if _uid(item[0]) == uid]
        if not items:
            raise YahooError("not found in your Yahoo account")
        return items[0][1]

    def read(self, message_id):
        validity, uid = self._parse(message_id, MESSAGE_ID)
        with self._imap() as conn:
            if self._select(conn, INBOX, readonly=True) != validity:
                raise YahooError("that Yahoo email id is out of date; search again")
            raw = self._fetch_message(conn, uid)
        msg, text = body_text(raw)
        return MailMessage(message_id, message_id, _header(msg, "from"), _header(msg, "to"), _header(msg, "cc"),
                           _header(msg, "subject"), _date(msg), text, _header(msg, "message-id"))

    def _reply_headers(self, conn, in_reply_to: Optional[str]) -> Dict[str, str]:
        if not in_reply_to:
            return {}
        validity, uid = self._parse(in_reply_to, MESSAGE_ID)
        if self._select(conn, INBOX, readonly=True) != validity:
            raise YahooError("that Yahoo email id is out of date; search again")
        typ, data = conn.uid("FETCH", uid, "(UID BODY.PEEK[HEADER.FIELDS (MESSAGE-ID REFERENCES)])")
        _ok(typ, "to open the email")
        items = [item for item in _fetch_items(data) if _uid(item[0]) == uid]
        if not items:
            raise YahooError("not found in your Yahoo account")
        msg = message_from_bytes(items[0][1], policy=default_policy)
        mid = _header(msg, "message-id")
        if not re.fullmatch(r"<[^<>\s]{1,250}>", mid):
            return {}
        refs = " ".join(r for r in _header(msg, "references").split() if re.fullmatch(r"<[^<>\s]{1,250}>", r))
        return {"In-Reply-To": mid, "References": (refs + " " + mid).strip()[-900:]}

    def _message(self, address: str, to, cc, subject: str, body: str, reply: Dict[str, str]) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = address
        if to:
            msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=False)
        msg["Message-ID"] = make_msgid(idstring="snafi", domain=address.rpartition("@")[2] or "yahoo.com")
        for name, value in reply.items():
            msg[name] = value
        msg.set_content(body)
        return msg

    def create_draft(self, to, cc, subject, body, in_reply_to=None):
        address, _ = self._credentials()
        with self._imap() as conn:
            msg = self._message(address, to, cc, subject, body, self._reply_headers(conn, in_reply_to))
            folder = self._drafts_folder(conn)
            typ, data = conn.append(_quote(folder), "(\\Draft \\Seen)", imaplib.Time2Internaldate(time.time()),
                                    msg.as_bytes())
            _ok(typ, "to save the draft")
            text = b" ".join(d for d in data or [] if isinstance(d, bytes)).decode("ascii", "replace")
            found = re.search(r"APPENDUID (\d+) (\d+)", text)
            if found:
                validity, uid = found.group(1), found.group(2)
            else:  # no UIDPLUS answer: find the draft by the Message-ID Snafi gave it
                validity = self._select(conn, folder, readonly=True)
                typ, data = conn.uid("SEARCH", "HEADER", "Message-ID", _quote(msg["Message-ID"]))
                _ok(typ, "to find the draft")
                uids = b" ".join(d for d in data or [] if isinstance(d, bytes)).split()
                if len(uids) != 1:
                    raise YahooError("Yahoo saved the draft but did not say where; look in Drafts")
                uid = uids[0].decode("ascii")
        return Draft(f"yd{validity}_{uid}", ", ".join(to), subject)

    def get_draft(self, draft_id):
        validity, uid = self._parse(draft_id, DRAFT_ID)
        with self._imap() as conn:
            if self._select(conn, self._drafts_folder(conn), readonly=True) != validity:
                raise YahooError("that Yahoo draft id is out of date")
            typ, data = conn.uid("FETCH", uid, "(UID BODY.PEEK[HEADER.FIELDS (TO SUBJECT)])")
            _ok(typ, "to open the draft")
        items = [item for item in _fetch_items(data) if _uid(item[0]) == uid]
        if not items:
            raise YahooError("not found in your Yahoo account")
        msg = message_from_bytes(items[0][1], policy=default_policy)
        return Draft(draft_id, _header(msg, "to"), _header(msg, "subject"))

    def delete_draft(self, draft_id):
        """Deletes exactly this draft: flagged \\Deleted and removed by its UID only (UID EXPUNGE), so no
        other message in Drafts is ever expunged."""
        validity, uid = self._parse(draft_id, DRAFT_ID)
        with self._imap() as conn:
            typ, caps = conn.capability()
            if "UIDPLUS" not in b" ".join(c for c in caps or [] if isinstance(c, bytes)).decode("ascii", "replace").upper():
                raise YahooError("Yahoo cannot delete only this one draft right now; nothing was deleted")
            if self._select(conn, self._drafts_folder(conn), readonly=False) != validity:
                raise YahooError("that Yahoo draft id is out of date; nothing was deleted")
            typ, data = conn.uid("FETCH", uid, "(UID FLAGS)")
            if typ != "OK" or uid not in _uids_in(data):
                raise YahooError("not found in your Yahoo account; nothing was deleted")
            typ, _ = conn.uid("STORE", uid, "+FLAGS.SILENT", "(\\Deleted)")
            _ok(typ, "to delete the draft")
            typ, _ = conn.uid("EXPUNGE", uid)
            _ok(typ, "to delete the draft")

    # ---------- SMTP (only after Approve) ----------
    def send(self, to, cc, bcc, subject, body, in_reply_to=None):
        address, password = self._credentials()
        reply = {}
        if in_reply_to:
            with self._imap() as conn:
                reply = self._reply_headers(conn, in_reply_to)
        msg = self._message(address, to, cc, subject, body, reply)  # Bcc is never written into the message
        try:
            conn = self._smtp_connect(self.timeout)
        except (OSError, smtplib.SMTPException):
            raise YahooError("Yahoo unreachable; nothing was sent", retryable=True) from None
        try:
            try:
                conn.login(address, password)
            except smtplib.SMTPAuthenticationError:
                raise AuthRefused("Yahoo refused the app password; nothing was sent. Make a new one and store "
                                  "it with snafi.cmd set-secrets") from None
            except (smtplib.SMTPException, OSError):  # before any message data: nothing went out (SEC-111)
                raise YahooError("Yahoo could not sign in for sending; nothing was sent", retryable=True) from None
            refused = conn.send_message(msg, from_addr=address, to_addrs=list(to) + list(cc) + list(bcc))
        except smtplib.SMTPRecipientsRefused:
            raise YahooError("Yahoo refused every recipient; nothing was sent") from None
        except (smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
            raise YahooError("Yahoo did not accept the email; nothing was sent") from None
        except (smtplib.SMTPException, OSError):
            raise YahooError("Yahoo did not confirm the send; check Sent in Yahoo before trying again") from None
        finally:
            try:
                conn.quit()
            except Exception:
                pass
        if refused:
            raise PartlySent(f"Yahoo refused {len(refused)} of the recipients", sorted(refused))
        return str(msg["Message-ID"])
