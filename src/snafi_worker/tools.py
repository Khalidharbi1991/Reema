"""Ahmad's tools in step 2, each with its permission level fixed here in code.

Level 1 just runs (reads). Level 2 runs, is logged and can be undone. Level 3 waits for
Khalid's Approve on an approval card. Level 4 is never run. A tool that is not listed is
refused. The brain can only propose; it cannot change a tool's level.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Tuple

ArgSpec = Dict[str, Tuple[type, int, bool]]  # name -> (type, max length, required)


@dataclass
class ToolResult:
    ok: bool
    summary: Dict[str, str]          # {"en": ..., "ar": ...}: what really happened, written by code
    data: Dict = field(default_factory=dict)
    undo: Optional[Dict] = None      # how to undo, for Level 2


@dataclass(frozen=True)
class Tool:
    name: str
    level: int
    args: ArgSpec
    run: Callable
    undo: Optional[Callable] = None
    describe: Callable = lambda args: {"en": "", "ar": ""}
    validate: Optional[Callable] = None   # extra checks, run by the gate before anything runs


class ToolArgError(ValueError):
    pass


def clean_args(tool: Tool, args: Dict) -> Dict:
    clean = {}
    for name, (kind, limit, required) in tool.args.items():
        value = args.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                raise ToolArgError(f"{name} is required")
            continue
        if kind is str:
            if not isinstance(value, str):
                raise ToolArgError(f"{name} must be text")
            value = value.strip()
            if len(value) > limit:
                raise ToolArgError(f"{name} is too long")
        elif kind is int:
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= limit:
                raise ToolArgError(f"{name} must be a number from 1 to {limit}")
        clean[name] = value
    return tool.validate(clean) if tool.validate else clean


def args_hash(tool: str, args: Dict) -> str:
    """SHA-256 of exactly what an approval card shows and what will run (SEC-13)."""
    text = json.dumps({"tool": tool, "args": args}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short(text: str, n: int = 80) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------- adders (Level 2, undoable by soft delete) ----------
def _adder(table: str, en: str, ar: str):
    def run(store, user_id, args, ctx):
        row = {"user_id": user_id, "body": args["body"]}
        if table == "reminders" and args.get("due"):
            row["due_at"] = args["due"]
        saved = store.insert(table, row)
        text = _short(args["body"])
        return ToolResult(True, {"en": f"{en}: {text}", "ar": f"{ar}: {text}"},
                          {"id": saved["id"]}, {"table": table, "id": saved["id"]})
    return run


def _soft_delete(store, undo: Dict):
    store.update(undo["table"], undo["id"], {"deleted_at": _now()})


def _lister(table: str, en: str, ar: str, none_en: str, none_ar: str):
    def run(store, user_id, args, ctx):
        rows = store.select(table, {"user_id": user_id}, descending=True, limit=args.get("limit", 10), null=("deleted_at",))
        if not rows:
            return ToolResult(True, {"en": none_en, "ar": none_ar}, {"items": []})
        items = [_short(r["body"], 120) for r in rows]
        bullets = "\n".join(f"• {i}" for i in items)
        return ToolResult(True, {"en": f"{en}:\n{bullets}", "ar": f"{ar}:\n{bullets}"}, {"items": items})
    return run


def _check_due(args):
    due = args.get("due")
    if due:
        try:
            parsed = datetime.fromisoformat(due.replace("Z", "+00:00"))
        except ValueError:
            raise ToolArgError("due must be a date and time like 2026-11-10T09:00+03:00") from None
        if parsed.tzinfo is None:
            raise ToolArgError("due needs a time zone, like +03:00")
        args["due"] = parsed.isoformat()
    return args


_add_reminder = _adder("reminders", "Saved a reminder (it will alert you from step 5)",
                       "حفظت تذكيراً (سينبّهك ابتداءً من المرحلة الخامسة)")


# ---------- the fake Level 3 action: proves approvals end to end, sends nothing ----------
def _send_test_message(store, user_id, args, ctx):
    text = _short(args["text"])
    return ToolResult(True, {"en": f"Test action ran after your approval. Nothing was sent anywhere: \"{text}\"",
                             "ar": f"نُفّذ الإجراء التجريبي بعد موافقتك. لم يُرسل أي شيء إلى أي جهة: «{text}»"},
                      {"sent": False, "test": True})


BODY: ArgSpec = {"body": (str, 1000, True)}
LIMIT: ArgSpec = {"limit": (int, 20, False)}

TOOLS: Dict[str, Tool] = {t.name: t for t in [
    Tool("add_note", 2, {"body": (str, 4000, True)}, _adder("notes", "Saved a note", "حفظت ملاحظة"), _soft_delete,
         lambda a: {"en": f"Save a note: {_short(a['body'])}", "ar": f"حفظ ملاحظة: {_short(a['body'])}"}),
    Tool("add_fact", 2, BODY, _adder("facts", "Saved a fact about you", "حفظت معلومة عنك"), _soft_delete,
         lambda a: {"en": f"Remember: {_short(a['body'])}", "ar": f"تذكّر: {_short(a['body'])}"}),
    Tool("add_reminder", 2, {**BODY, "due": (str, 40, False)}, _add_reminder, _soft_delete,
         lambda a: {"en": f"Reminder: {_short(a['body'])}", "ar": f"تذكير: {_short(a['body'])}"}, _check_due),
    Tool("list_notes", 1, LIMIT, _lister("notes", "Your notes", "ملاحظاتك", "You have no notes yet.", "لا توجد ملاحظات بعد.")),
    Tool("list_facts", 1, LIMIT, _lister("facts", "What I know about you", "ما أعرفه عنك",
                                         "I have no saved facts yet.", "لا توجد معلومات محفوظة بعد.")),
    Tool("list_reminders", 1, LIMIT, _lister("reminders", "Your reminders", "تذكيراتك",
                                             "You have no reminders.", "لا توجد تذكيرات.")),
    Tool("send_test_message", 3, {"text": (str, 500, True)}, _send_test_message, None,
         lambda a: {"en": f"Test send (nothing leaves this PC): {_short(a['text'])}",
                    "ar": f"إرسال تجريبي (لا يخرج شيء من الجهاز): {_short(a['text'])}"}),
]}

# Level 4: never run, whatever is asked. Matched by name and by keywords in unknown names.
NEVER = {
    "make_payment", "pay", "transfer_money", "send_money", "buy", "purchase", "change_password",
    "reset_password", "share_password", "change_security_settings", "disable_2fa", "send_mass_message",
    "mass_message", "broadcast",
}
NEVER_WORDS = ("pay", "money", "transfer", "purchase", "password", "security", "2fa", "mass", "broadcast", "bank")
