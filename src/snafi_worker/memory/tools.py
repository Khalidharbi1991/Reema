"""Ahmad's memory tools, each with its level fixed here (step 6).

  add_fact            Level 2, Undo deletes it: a short durable fact Khalid told him (no secrets)
  add_family_member   Level 2, Undo deletes it (and its dates)
  add_family_date     Level 2, Undo deletes it: a birthday, anniversary or other key date
  search_memory       Level 1: keyword search over everything Ahmad knows
  list_family         Level 1: the family and their dates
Forgetting is the About me page's Forget (Khalid's own tap); there is no forget tool for the brain.
The engine refuses memory writes in a turn that read outside content and allows at most three a turn.
"""

import re
from typing import Dict, Optional

from ..tool_types import ArgSpec, Tool, ToolArgError, ToolResult
from .base import (CALENDARS, FACT_MAX, LABELS, LABEL_WORDS, NAME_MAX, NOTE_MAX, RELATION_WORDS, RELATIONS, SECTIONS,
                   TITLE_MAX, MemoryRefused)
from .guard import REASONS, refusal
from .search import Item, KeywordSearch
from .store_book import StoreMemoryBook, check_date

WRITES = frozenset({"add_fact", "add_family_member", "add_family_date"})
DATE = re.compile(r"^(?:(\d{4})-)?(\d{1,2})-(\d{1,2})$")
SECTION_WORDS = {"en": {"me": "me", "family": "family", "preferences": "preferences", "routine": "routine"},
                 "ar": {"me": "عنّي", "family": "العائلة", "preferences": "التفضيلات", "routine": "الروتين"}}


def _short(text: str, n: int = 80) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def book_of(store, ctx: Optional[Dict]):
    book = (ctx or {}).get("memory")
    return book if book is not None else StoreMemoryBook(store=store)


def search_of(ctx: Optional[Dict]):
    found = (ctx or {}).get("memory_search")
    return found if found is not None else KeywordSearch()


def _no_secrets(*names):
    def check(args):
        for name in names:
            why = refusal(args.get(name) or "")
            if why:
                raise ToolArgError(REASONS[why]["en"])
        return args
    return check


# ---------- what Ahmad knows, as one list (for search, the brain's memory block and the About me page) ----------
def describe_date(row: Dict, member: Optional[Dict], lang: str = "en") -> str:
    name = (member or {}).get("name") or "—"
    label = LABEL_WORDS[lang].get(row.get("label") or "other") or row.get("title") or ""
    year = f"{row['year']}-" if row.get("year") else ""
    cal = " (Hijri)" if row.get("calendar") == "hijri" and lang == "en" else (" هـ" if row.get("calendar") == "hijri" else "")
    return f"{name}: {label} {year}{int(row['month']):02d}-{int(row['day']):02d}{cal}"


def all_items(book, user_id: str):
    members = book.members(user_id)
    by_id = {m["id"]: m for m in members}
    items = [Item("fact", f["id"], f["body"], f.get("section") or "me") for f in book.facts(user_id)]
    for m in members:
        relation = RELATION_WORDS["en"].get(m.get("relation") or "other", "family")
        note = f" · {m['note']}" if m.get("note") else ""
        items.append(Item("member", m["id"], f"{m['name']} ({relation}, {RELATION_WORDS['ar'].get(m.get('relation'), '')}){note}",
                          "family"))
    for d in book.dates(user_id):
        items.append(Item("date", d["id"], describe_date(d, by_id.get(d.get("member_id"))), "family"))
    return items


# ---------- run ----------
def _add_fact(store, user_id, args, ctx):
    book = book_of(store, ctx)
    source = "interview" if (ctx or {}).get("interview_active") else "told"
    try:
        row = book.add_fact(user_id, args["body"], args.get("section") or "me", source)
    except MemoryRefused as exc:
        raise ToolArgError(str(exc)) from None
    text = _short(row["body"])
    if row.get("existing"):
        return ToolResult(True, {"en": f"Already in memory: {text}", "ar": f"محفوظ مسبقاً: {text}"}, {"id": row["id"]})
    return ToolResult(True, {"en": f"Saved to memory: {text}", "ar": f"حفظته في الذاكرة: {text}"},
                      {"id": row["id"]}, {"table": "facts", "id": row["id"]})


def _add_member(store, user_id, args, ctx):
    book = book_of(store, ctx)
    try:
        row = book.add_member(user_id, args["name"], args["relation"], args.get("note") or "")
    except MemoryRefused as exc:
        raise ToolArgError(str(exc)) from None
    en_rel, ar_rel = RELATION_WORDS["en"][row["relation"]], RELATION_WORDS["ar"][row["relation"]]
    if row.get("existing"):
        return ToolResult(True, {"en": f"Already in the family list: {row['name']} ({en_rel})",
                                 "ar": f"موجود مسبقاً في قائمة العائلة: {row['name']} ({ar_rel})"}, {"id": row["id"]})
    return ToolResult(True, {"en": f"Saved to the family list: {row['name']} ({en_rel})",
                             "ar": f"حفظته في قائمة العائلة: {row['name']} ({ar_rel})"},
                      {"id": row["id"]}, {"table": "family_members", "id": row["id"]})


def _check_date(args):
    args = _no_secrets("title")(args)
    match = DATE.match(args.get("date") or "")
    if not match:
        raise ToolArgError("date must look like 2015-03-14, or 03-14 when the year is not known")
    calendar = args.get("calendar") or "gregorian"
    if calendar not in CALENDARS:
        raise ToolArgError("calendar must be gregorian or hijri")
    if args.get("label") not in LABELS:
        raise ToolArgError("label must be birthday, anniversary or other")
    year = int(match.group(1)) if match.group(1) else None
    try:
        check_date(calendar, year, int(match.group(2)), int(match.group(3)))
    except MemoryRefused as exc:
        raise ToolArgError(str(exc)) from None
    if args["label"] == "other" and not args.get("title"):
        raise ToolArgError("a date labelled other needs a title")
    return {**args, "calendar": calendar}


def _add_date(store, user_id, args, ctx):
    book = book_of(store, ctx)
    member = book.member_named(user_id, args["person"]) if hasattr(book, "member_named") else None
    if member is None:
        raise ToolArgError(f"{args['person']} is not in the family list yet; add them first with add_family_member")
    match = DATE.match(args["date"])
    year = int(match.group(1)) if match.group(1) else None
    try:
        row = book.add_date(user_id, member["id"], args["label"], args.get("title") or "", args["calendar"], year,
                            int(match.group(2)), int(match.group(3)))
    except MemoryRefused as exc:
        raise ToolArgError(str(exc)) from None
    text = {lang: describe_date(row, member, lang) for lang in ("en", "ar")}
    if row.get("existing"):
        return ToolResult(True, {"en": f"Already saved: {text['en']}", "ar": f"محفوظ مسبقاً: {text['ar']}"},
                          {"id": row["id"]})
    return ToolResult(True, {"en": f"Saved the date: {text['en']}", "ar": f"حفظت التاريخ: {text['ar']}"},
                      {"id": row["id"]}, {"table": "family_dates", "id": row["id"]})


def _search(store, user_id, args, ctx):
    book = book_of(store, ctx)
    found = search_of(ctx).search(all_items(book, user_id), args["query"], args.get("limit", 10))
    if not found:
        return ToolResult(True, {"en": "Nothing in memory matches that.", "ar": "لا شيء في الذاكرة يطابق ذلك."},
                          {"items": 0})
    bullets = "\n".join(f"• {_short(i.text, 160)}" for i in found)
    return ToolResult(True, {"en": f"From memory:\n{bullets}", "ar": f"من الذاكرة:\n{bullets}"}, {"items": len(found)})


def _list_family(store, user_id, args, ctx):
    book = book_of(store, ctx)
    members = book.members(user_id)
    if not members:
        return ToolResult(True, {"en": "No family members saved yet.", "ar": "لا يوجد أفراد عائلة محفوظون بعد."},
                          {"items": 0})
    dates = book.dates(user_id)
    out = {}
    for lang in ("en", "ar"):
        lines = []
        for m in members:
            mine = [describe_date(d, m, lang).split(": ", 1)[1] for d in dates if d.get("member_id") == m["id"]]
            extra = f" — {'; '.join(mine)}" if mine else ""
            lines.append(f"• {m['name']} ({RELATION_WORDS[lang][m['relation']]}){extra}")
        out[lang] = ("Your family:\n" if lang == "en" else "عائلتك:\n") + "\n".join(lines)
    return ToolResult(True, out, {"items": len(members)})


def _delete(store, undo: Dict, ctx: Optional[Dict] = None):
    book_of(store, ctx).delete(undo["table"], undo["id"])


def _check_fact(args):
    args = _no_secrets("body")(args)
    if args.get("section") and args["section"] not in SECTIONS:
        raise ToolArgError("section must be me, family, preferences or routine")
    return args


def _check_member(args):
    args = _no_secrets("name", "note")(args)
    if args.get("relation") not in RELATIONS:
        raise ToolArgError("relation must be one of: " + ", ".join(RELATIONS))
    return args


FACT: ArgSpec = {"body": (str, FACT_MAX, True), "section": (str, 20, False)}
MEMBER: ArgSpec = {"name": (str, NAME_MAX, True), "relation": (str, 20, True), "note": (str, NOTE_MAX, False)}
FAMILY_DATE: ArgSpec = {"person": (str, NAME_MAX, True), "label": (str, 20, True), "date": (str, 10, True),
                        "calendar": (str, 10, False), "title": (str, TITLE_MAX, False)}

MEMORY_TOOLS = [
    Tool("add_fact", 2, FACT, _add_fact, _delete,
         lambda a: {"en": f"Remember: {_short(a['body'])}", "ar": f"تذكّر: {_short(a['body'])}"}, _check_fact),
    Tool("add_family_member", 2, MEMBER, _add_member, _delete,
         lambda a: {"en": f"Add to the family list: {a['name']}", "ar": f"إضافة إلى قائمة العائلة: {a['name']}"},
         _check_member),
    Tool("add_family_date", 2, FAMILY_DATE, _add_date, _delete,
         lambda a: {"en": f"Save a date for {a['person']}: {a['date']}", "ar": f"حفظ تاريخ لـ{a['person']}: {a['date']}"},
         _check_date),
    Tool("search_memory", 1, {"query": (str, 200, True), "limit": (int, 20, False)}, _search),
    Tool("list_family", 1, {}, _list_family),
]
