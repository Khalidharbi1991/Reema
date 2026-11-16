"""The memory interface (PRD "Memory"): what Ahmad knows about Khalid and his family.

A memory book keeps facts (grouped me, family, preferences, routine), family members, their key dates
and the interview's state. Today it lives in the worker's store (the cloud mailbox; in memory for tests), chosen
by memory.provider in worker.yaml. Search is a separate adapter (memory.search).
"""

from typing import Dict, List, Optional, Protocol

SECTIONS = ("me", "family", "preferences", "routine")
SOURCES = ("told", "interview", "learned")
RELATIONS = ("wife", "husband", "daughter", "son", "mother", "father", "sister", "brother", "other")
LABELS = ("birthday", "anniversary", "other")
CALENDARS = ("gregorian", "hijri")
FACT_MAX = 300          # a fact Ahmad saves from chat (the database allows 500 for Khalid's own edits)
NAME_MAX, NOTE_MAX, TITLE_MAX = 80, 300, 80
MEMORY_TABLES = ("facts", "family_members", "family_dates")

RELATION_WORDS = {
    "en": {"wife": "wife", "husband": "husband", "daughter": "daughter", "son": "son", "mother": "mother",
           "father": "father", "sister": "sister", "brother": "brother", "other": "family"},
    "ar": {"wife": "الزوجة", "husband": "الزوج", "daughter": "الابنة", "son": "الابن", "mother": "الأم",
           "father": "الأب", "sister": "الأخت", "brother": "الأخ", "other": "من العائلة"},
}
LABEL_WORDS = {
    "en": {"birthday": "birthday", "anniversary": "anniversary", "other": ""},
    "ar": {"birthday": "عيد الميلاد", "anniversary": "ذكرى الزواج", "other": ""},
}


class MemoryRefused(ValueError):
    """The text breaks the no-secrets rule, or a value is not allowed. Nothing was stored."""


class MemoryBook(Protocol):
    PROVIDER: str

    def facts(self, user_id: str, limit: int = 500) -> List[Dict]: ...
    def add_fact(self, user_id: str, body: str, section: str, source: str) -> Dict: ...
    def members(self, user_id: str) -> List[Dict]: ...
    def add_member(self, user_id: str, name: str, relation: str, note: str = "") -> Dict: ...
    def dates(self, user_id: str) -> List[Dict]: ...
    def add_date(self, user_id: str, member_id: str, label: str, title: str, calendar: str,
                 year: Optional[int], month: int, day: int) -> Dict: ...
    def delete(self, table: str, row_id: str) -> None: ...
    def interview(self, user_id: str) -> Optional[Dict]: ...
    def set_interview(self, user_id: str, changes: Dict) -> Dict: ...
