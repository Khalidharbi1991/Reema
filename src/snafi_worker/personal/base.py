"""The personal services behind Ahmad's step 3 tools: mail, calendar and files.

Each kind has one interface here and its providers in their own files, chosen in worker.yaml:
  mail:     gmail (google/gmail.py)            | fake (tests) | none
  calendar: google_calendar (google/gcal.py)   | fake (tests) | none
  files:    google_drive (google/drive.py)     | fake (tests) | none
Everything these return from outside (mail, event descriptions, file text) is untrusted data:
the engine gives it to the brain only inside marked data blocks.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Protocol

from ..google.http import GoogleAuthError, GoogleError, GoogleNotConnected  # noqa: F401  (re-exported)

MAX_BODY = 20_000          # characters of one email or file given to the brain
SNAFI_TAG = "snafi"        # private property on events Snafi created (Undo deletes only those)


class ServiceError(GoogleError):
    """A personal service failed; the message is safe to show (never content or tokens)."""


class NotConnected(ServiceError):
    """This service is switched off (provider none) or not connected."""


@dataclass(frozen=True)
class MailSummary:
    id: str
    thread_id: str
    sender: str            # "Name <address>" as written by the sender: untrusted
    subject: str           # untrusted
    date: str              # ISO 8601
    snippet: str = ""      # untrusted
    unread: bool = False
    important: bool = False


@dataclass(frozen=True)
class MailMessage:
    id: str
    thread_id: str
    sender: str
    to: str
    cc: str
    subject: str
    date: str
    body: str              # plain text, at most MAX_BODY characters: untrusted
    message_id_header: str = ""


@dataclass(frozen=True)
class Draft:
    id: str
    to: str = ""
    subject: str = ""


@dataclass(frozen=True)
class Event:
    id: str
    title: str
    start: str             # ISO 8601, or a date for all-day events
    end: str
    location: str = ""
    description: str = ""  # untrusted
    attendees: List[str] = field(default_factory=list)
    all_day: bool = False
    created_by_snafi: bool = False


@dataclass(frozen=True)
class FileInfo:
    id: str
    name: str              # untrusted
    mime_type: str
    modified: str
    link: str = ""


class Mail(Protocol):
    PROVIDER: str

    def search(self, query: str, limit: int) -> List[MailSummary]: ...
    def read(self, message_id: str) -> MailMessage: ...
    def important_unread(self, hours: int, limit: int) -> List[MailSummary]: ...
    def create_draft(self, to: List[str], cc: List[str], subject: str, body: str,
                     in_reply_to: Optional[str] = None) -> Draft: ...
    def get_draft(self, draft_id: str) -> Draft: ...
    def delete_draft(self, draft_id: str) -> None: ...
    def send(self, to: List[str], cc: List[str], bcc: List[str], subject: str, body: str,
             in_reply_to: Optional[str] = None) -> str: ...


class Calendar(Protocol):
    PROVIDER: str

    def list_events(self, start: str, end: str, limit: int) -> List[Event]: ...
    def get_event(self, event_id: str) -> Event: ...
    def create_event(self, title: str, start: str, end: str, location: str = "", description: str = "",
                     attendees: Optional[List[str]] = None) -> Event: ...
    def delete_event(self, event_id: str) -> None: ...


class Files(Protocol):
    PROVIDER: str

    def search(self, query: str, limit: int) -> List[FileInfo]: ...
    def read(self, file_id: str) -> str: ...
