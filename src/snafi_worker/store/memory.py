"""In-memory store for offline tests. Same calls as the Supabase store, no network."""

import copy
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from ..registry import register
from .base import CACHE_TABLES, KEYED_BY_USER, ORDER, TABLES, StoreError, check_name

DEFAULTS = {
    "jobs": {"status": "queued", "lane": "chat", "attempts": 0, "max_attempts": 2, "payload": {},
             "result": None, "error": None, "claimed_by": None, "claimed_at": None, "finished_at": None,
             "conversation_id": None},
    "messages": {"job_id": None, "approval_id": None, "meta": {}, "lang": "en"},
    "approvals": {"status": "pending", "level": 3, "args": {}, "decided_at": None, "executed_at": None,
                  "result": None, "job_id": None, "args_hash": ""},
    "action_log": {"undoable": False, "undo": None, "undo_requested_at": None, "undone_at": None,
                   "result": None, "args": {}, "job_id": None, "approval_id": None, "conversation_id": None},
    "notes": {"deleted_at": None}, "reminders": {"deleted_at": None, "due_at": None, "fired_at": None},
    "facts": {"deleted_at": None, "section": "me", "source": "told"}, "worker_status": {}, "today_feed": {},
    "family_members": {"note": ""}, "family_dates": {"title": "", "calendar": "gregorian", "year": None},
    "interview_state": {"status": "invited", "step": 0, "lang": "en", "started_at": None, "finished_at": None},
    "notifications": {"status": "new", "content_hash": "", "counts_to_cap": True, "card": None, "hold_until": None,
                      "pushed": False, "reason": None, "delivered_at": None},
    "cards": {"notification_id": None, "dismissed_at": None},
    "user_settings": {"push_enabled": False, "brief_time": "07:00", "daily_cap": 10, "lang": "en"},
    "push_subscriptions": {"failures": 0, "last_ok_at": None},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@register("store", "memory")
class MemoryStore:
    SECRET_NAMES = ()

    def __init__(self, options: dict = None, secrets=None):
        self.tables: Dict[str, List[Dict]] = {t: [] for t in TABLES + CACHE_TABLES}
        self._lock = threading.Lock()

    def _table(self, name):
        if check_name(name) not in self.tables:
            raise StoreError(f"unknown table {name}")
        return self.tables[name]

    def insert(self, table, row):
        with self._lock:
            full = {**copy.deepcopy(DEFAULTS.get(table, {})), **copy.deepcopy(row)}
            if table in KEYED_BY_USER:  # keyed by user_id; no id or created_at, as in the database
                full.setdefault("updated_at", now_iso())
                if table == "worker_status":
                    full.setdefault("last_seen", now_iso())
                self._table(table).append(full)
                return copy.deepcopy(full)
            full.setdefault("id", str(uuid.uuid4()))
            full.setdefault("created_at", now_iso())
            if table == "approvals":
                full.setdefault("expires_at", (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat())
            if table == "jobs":
                full.setdefault("updated_at", full["created_at"])
                full.setdefault("run_after", full["created_at"])
            self._table(table).append(full)
            return copy.deepcopy(full)

    def select(self, table, where=None, order="created_at", descending=False, limit=100, null=()):
        rows = [r for r in self._table(table)
                if all(r.get(k) == v for k, v in (where or {}).items()) and all(r.get(c) is None for c in null)]
        rows.sort(key=lambda r: str(r.get(order) or ""), reverse=descending)
        return copy.deepcopy(rows[:limit])

    def update(self, table, row_id, changes):
        with self._lock:
            for row in self._table(table):
                if row.get("id") == row_id:
                    row.update(copy.deepcopy(changes))
                    if table == "jobs":
                        row["updated_at"] = now_iso()
                    return copy.deepcopy(row)
        raise StoreError(f"{table} row not found")

    def update_if(self, table, row_id, expect, changes):
        with self._lock:
            for row in self._table(table):
                if row.get("id") == row_id:
                    if any(row.get(k) != v for k, v in expect.items()):
                        return None
                    row.update(copy.deepcopy(changes))
                    return copy.deepcopy(row)
        return None

    def upsert(self, table, row, key):
        with self._lock:
            for existing in self._table(table):
                if existing.get(key) == row.get(key):
                    existing.update(copy.deepcopy(row))
                    return copy.deepcopy(existing)
        return self.insert(table, row)

    def insert_once(self, table, row, keys):
        with self._lock:
            if any(all(existing.get(k) == row.get(k) for k in keys) for existing in self._table(table)):
                return None
        return self.insert(table, row)

    def delete(self, table, row_id):
        with self._lock:
            rows = self._table(table)
            rows[:] = [r for r in rows if r.get("id") != row_id]

    def claim_job(self, lane, worker_id):
        with self._lock:
            now = now_iso()
            queued = sorted((j for j in self.tables["jobs"]
                             if j["status"] == "queued" and j["lane"] == lane and str(j.get("run_after", "")) <= now),
                            key=lambda j: j["created_at"])
            if not queued:
                return None
            job = queued[0]
            job.update(status="claimed", claimed_by=worker_id, claimed_at=now, attempts=job["attempts"] + 1)
            return copy.deepcopy(job)

    def page(self, table, offset, limit):
        key = ORDER.get(table, "created_at")
        rows = sorted(self._table(table), key=lambda r: (str(r.get(key) or ""), str(r.get("id") or "")))
        return copy.deepcopy(rows[offset:offset + limit])
