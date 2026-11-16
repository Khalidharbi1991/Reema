"""Memory kept in the worker's store (the cloud mailbox; the in-memory store in tests).

Every write is checked here first (the no-secrets rule, lengths, allowed values), and the database
checks the same rule again (migration 0010). A fact or person already saved is not saved twice: the
existing row comes back with "existing": True.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..registry import register
from .base import (CALENDARS, FACT_MAX, LABELS, MEMORY_TABLES, NAME_MAX, NOTE_MAX, RELATIONS, SECTIONS, SOURCES,
                   TITLE_MAX, MemoryRefused)
from .guard import REASONS, refusal
from .hijri import FIRST_YEAR, LAST_YEAR, month_length
from .normalise import squash

GREGORIAN_DAYS = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(text: str, most: int, what: str, required: bool = True) -> str:
    text = " ".join(str(text or "").split())
    if required and not text:
        raise MemoryRefused(f"{what} is empty")
    if len(text) > most:
        raise MemoryRefused(f"{what} is longer than {most} characters")
    why = refusal(text)
    if why:
        raise MemoryRefused(REASONS[why]["en"])
    return text


def check_date(calendar: str, year: Optional[int], month: int, day: int) -> None:
    if calendar not in CALENDARS:
        raise MemoryRefused("calendar must be gregorian or hijri")
    if not isinstance(month, int) or not isinstance(day, int) or not 1 <= month <= 12 or day < 1:
        raise MemoryRefused("not a real date")
    if calendar == "gregorian":
        if day > GREGORIAN_DAYS[month] or (year is not None and not 1900 <= year <= 2100):
            raise MemoryRefused("not a real date")
        if year is not None and month == 2 and day == 29 and not (year % 4 == 0 and (year % 100 or year % 400 == 0)):
            raise MemoryRefused("not a real date")
    else:
        if day > 30 or (year is not None and not 1300 <= year <= 1500):
            raise MemoryRefused("not a real Hijri date")
        if year is not None and FIRST_YEAR <= year <= LAST_YEAR and day > (month_length(year, month) or 30):
            raise MemoryRefused("that Hijri month has 29 days")


@register("memory", "store")
class StoreMemoryBook:
    SECRET_NAMES = ()

    def __init__(self, options: Dict = None, secrets=None, store=None):
        if store is None:
            raise ValueError("the store memory book needs the worker's store")
        self.store = store
        self.options = dict(options or {})

    # ---------- facts ----------
    def facts(self, user_id: str, limit: int = 500) -> List[Dict]:
        return self.store.select("facts", {"user_id": user_id}, limit=limit, null=("deleted_at",))

    def add_fact(self, user_id: str, body: str, section: str = "me", source: str = "told") -> Dict:
        body = _clean(body, FACT_MAX, "the fact")
        if section not in SECTIONS:
            section = "me"
        if source not in SOURCES:
            raise MemoryRefused("unknown source")
        same = squash(body)
        for row in self.facts(user_id):
            if squash(row.get("body") or "") == same:
                return {**row, "existing": True}
        return self.store.insert("facts", {"user_id": user_id, "body": body, "section": section, "source": source,
                                           "updated_at": _now()})

    # ---------- family ----------
    def members(self, user_id: str) -> List[Dict]:
        return self.store.select("family_members", {"user_id": user_id}, limit=100)

    def member_named(self, user_id: str, name: str) -> Optional[Dict]:
        want = squash(name)
        for row in self.members(user_id):
            if squash(row.get("name") or "") == want:
                return row
        return None

    def add_member(self, user_id: str, name: str, relation: str, note: str = "") -> Dict:
        name = _clean(name, NAME_MAX, "the name")
        note = _clean(note, NOTE_MAX, "the note", required=False)
        if relation not in RELATIONS:
            raise MemoryRefused("relation must be one of: " + ", ".join(RELATIONS))
        existing = self.member_named(user_id, name)
        if existing:
            return {**existing, "existing": True}
        return self.store.insert("family_members", {"user_id": user_id, "name": name, "relation": relation,
                                                    "note": note, "updated_at": _now()})

    def dates(self, user_id: str) -> List[Dict]:
        return self.store.select("family_dates", {"user_id": user_id}, limit=200)

    def add_date(self, user_id: str, member_id: str, label: str, title: str, calendar: str,
                 year: Optional[int], month: int, day: int) -> Dict:
        if label not in LABELS:
            raise MemoryRefused("label must be birthday, anniversary or other")
        title = _clean(title, TITLE_MAX, "the title", required=(label == "other"))
        check_date(calendar, year, month, day)
        if not self.store.select("family_members", {"id": member_id, "user_id": user_id}, limit=1):
            raise MemoryRefused("no such family member")
        for row in self.store.select("family_dates", {"user_id": user_id, "member_id": member_id}, limit=50):
            same = (row.get("calendar"), row.get("month"), row.get("day")) == (calendar, month, day)
            if (label == "birthday" and row.get("label") == "birthday") or (same and row.get("label") == label):
                return {**row, "existing": True}
        return self.store.insert("family_dates", {
            "user_id": user_id, "member_id": member_id, "label": label, "title": title, "calendar": calendar,
            "year": year, "month": month, "day": day, "updated_at": _now()})

    # ---------- delete (Undo of a save; the app's Forget runs in the database) ----------
    def delete(self, table: str, row_id: str) -> None:
        if table not in MEMORY_TABLES:
            raise MemoryRefused("not a memory table")
        if table == "family_members":  # its dates go with it, as ON DELETE CASCADE does in the database
            for row in self.store.select("family_dates", {"member_id": row_id}, limit=50):
                self.store.delete("family_dates", row["id"])
        self.store.delete(table, row_id)

    # ---------- the interview ----------
    def interview(self, user_id: str) -> Optional[Dict]:
        rows = self.store.select("interview_state", {"user_id": user_id}, order="user_id", limit=1)
        return rows[0] if rows else None

    def set_interview(self, user_id: str, changes: Dict) -> Dict:
        return self.store.upsert("interview_state", {"user_id": user_id, **changes, "updated_at": _now()}, "user_id")
