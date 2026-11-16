"""The worker's database interface. Supabase today (supabase_rest); any Postgres or an
in-memory store (memory, for tests) behind the same few calls."""

import re
from typing import Dict, List, Optional, Protocol

TABLES = ("messages", "jobs", "approvals", "action_log", "notes", "reminders", "facts", "worker_status",
          # Step 5: Khalid's settings.
          "user_settings",
          # Step 6: memory and family (Khalid, Nov 16, 2026: memory stays in the backup; a forgotten item
          # leaves the backups as they age out, within 30 days).
          "family_members", "family_dates", "interview_state")
# Rebuilt by the worker every few minutes, so never backed up or restored: today_feed (step 3) holds
# only the next event and the senders and subjects of important unread mail. push_subscriptions
# (step 5) are not backed up either: the phone simply subscribes again (Settings, Push on).
# SEC-127 (Khalid, Nov 14, 2026): Ahmad's cards and the sent record (notifications) are cleared after
# 30 days and are never in a backup, so no copy of them is older than 30 days anywhere.
CACHE_TABLES = ("today_feed", "push_subscriptions", "notifications", "cards")
KEYED_BY_USER = ("worker_status", "today_feed", "user_settings", "interview_state")
NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
# Stable order for paging and backups.
ORDER = {"worker_status": "user_id", "today_feed": "user_id", "user_settings": "user_id", "interview_state": "user_id"}


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
    def insert_once(self, table: str, row: Dict, keys: tuple) -> Optional[Dict]:
        """Insert unless a row with the same values in `keys` (a UNIQUE constraint) exists: then None.
        The database decides, in one statement, so two tries can never both insert (step 5 ledger)."""
    def delete(self, table: str, row_id: str) -> None: ...
    def claim_job(self, lane: str, worker_id: str) -> Optional[Dict]: ...
    def page(self, table: str, offset: int, limit: int) -> List[Dict]: ...
