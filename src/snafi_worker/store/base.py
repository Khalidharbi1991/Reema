"""The worker's database interface. Supabase today (supabase_rest); any Postgres or an
in-memory store (memory, for tests) behind the same few calls."""

import re
from typing import Dict, List, Optional, Protocol

TABLES = ("messages", "jobs", "approvals", "action_log", "notes", "reminders", "facts", "worker_status")
# Rebuilt by the worker every few minutes, so never backed up or restored: today_feed (step 3) holds
# only the next event and the senders and subjects of important unread mail.
CACHE_TABLES = ("today_feed",)
KEYED_BY_USER = ("worker_status", "today_feed")
NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
# Stable order for paging and backups.
ORDER = {"worker_status": "user_id", "today_feed": "user_id"}


class StoreError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def check_name(name: str) -> str:
    if not NAME.match(name or ""):
        raise StoreError(f"invalid name {name!r}")
    return name


class Store(Protocol):
    PROVIDER: str
    SECRET_NAMES: tuple

    def insert(self, table: str, row: Dict) -> Dict: ...
    def select(self, table: str, where: Optional[Dict] = None, order: str = "created_at",
               descending: bool = False, limit: int = 100, null: tuple = ()) -> List[Dict]: ...
    def update(self, table: str, row_id: str, changes: Dict) -> Dict: ...
    def update_if(self, table: str, row_id: str, expect: Dict, changes: Dict) -> Optional[Dict]:
        """Change the row only if it still matches `expect`, in one statement. None if it did not."""
    def upsert(self, table: str, row: Dict, key: str) -> Dict: ...
    def claim_job(self, lane: str, worker_id: str) -> Optional[Dict]: ...
    def page(self, table: str, offset: int, limit: int) -> List[Dict]: ...
