"""Google Drive adapter (provider "google_drive"). Scope: drive.readonly. It can search and read,
nothing else: Snafi cannot change, share or delete a Drive file.

Google Docs are exported as plain text, Sheets as CSV and Slides as plain text; plain-text
files are downloaded as they are. Other types (PDF, images, Office files) are listed but not read.
"""

import re
import urllib.parse
from typing import List

from ..personal.base import MAX_BODY, FileInfo, ServiceError
from ..registry import register
from .http import GoogleApi

BASE = "https://www.googleapis.com/drive/v3/files"
ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
EXPORT = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}
TEXT = re.compile(r"^(text/|application/(json|csv|xml)$)")
MAX_DOWNLOAD = 2_000_000


def _id(value: str) -> str:
    if not isinstance(value, str) or not ID.match(value):
        raise ServiceError("that is not a Drive file id")
    return urllib.parse.quote(value, safe="")


def drive_query(words: str) -> str:
    """A Drive search for the words in names and contents. Quotes and backslashes are escaped."""
    safe = (words or "").replace("\\", "\\\\").replace("'", "\\'")
    return f"(name contains '{safe}' or fullText contains '{safe}') and trashed = false"


@register("files", "google_drive")
class GoogleDrive:
    def __init__(self, options: dict, auth):
        self.api = GoogleApi(auth)

    def __repr__(self) -> str:
        return "GoogleDrive(tokens=hidden)"

    def search(self, query, limit) -> List[FileInfo]:
        data = self.api.call("GET", BASE, {"q": drive_query(query), "pageSize": max(1, min(limit, 20)),
                                           "fields": "files(id,name,mimeType,modifiedTime,webViewLink,size)",
                                           "orderBy": "modifiedTime desc"})
        return [FileInfo(str(f.get("id")), str(f.get("name") or "")[:300], str(f.get("mimeType") or ""),
                         str(f.get("modifiedTime") or ""), str(f.get("webViewLink") or ""))
                for f in data.get("files") or [] if isinstance(f, dict) and ID.match(str(f.get("id") or ""))]

    def read(self, file_id) -> str:
        fid = _id(file_id)
        meta = self.api.call("GET", f"{BASE}/{fid}", {"fields": "id,mimeType,size"})
        mime = str(meta.get("mimeType") or "")
        if mime in EXPORT:
            raw = self.api.call("GET", f"{BASE}/{fid}/export", {"mimeType": EXPORT[mime]}, raw=True)
        elif TEXT.match(mime):
            if int(meta.get("size") or 0) > MAX_DOWNLOAD:
                raise ServiceError("that file is too large to read")
            raw = self.api.call("GET", f"{BASE}/{fid}", {"alt": "media"}, raw=True)
        else:
            raise ServiceError(f"I can't read this kind of file yet ({mime or 'unknown type'})")
        return raw[:MAX_DOWNLOAD].decode("utf-8", errors="replace").strip()[:MAX_BODY]
