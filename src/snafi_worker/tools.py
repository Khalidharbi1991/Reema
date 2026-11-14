"""Ahmad's tools in step 2, each with its permission level fixed here in code.

Level 1 just runs (reads). Level 2 runs, is logged and can be undone. Level 3 waits for
Khalid's Approve on an approval card. Level 4 is never run. A tool that is not listed is
refused. The brain can only propose; it cannot change a tool's level.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from zoneinfo import ZoneInfo

from .clock import day_clock
from .personal_tools import PERSONAL_TOOLS
from .tool_types import (LIST_ITEM_MAX, ArgSpec, NeverError, Tool, ToolArgError, ToolResult,  # noqa: F401
                         args_hash, clean_args)


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


def _soft_delete(store, undo: Dict, ctx: Optional[Dict] = None):
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


def _add_reminder(store, user_id, args, ctx):
    """Step 5: a reminder with a time goes off then, as a card on Today and a push to the phone."""
    row = {"user_id": user_id, "body": args["body"]}
    if args.get("due"):
        row["due_at"] = args["due"]
    saved = store.insert("reminders", row)
    text = _short(args["body"])
    if args.get("due"):
        when = datetime.fromisoformat(args["due"]).astimezone(ZoneInfo((ctx or {}).get("time_zone") or "Asia/Riyadh"))
        en = f"Saved a reminder for {day_clock(when, 'en')}; I'll alert you then: {text}"
        ar = f"حفظت تذكيراً في {day_clock(when, 'ar')}، وسأنبّهك حينها: {text}"
    else:
        en, ar = f"Saved a reminder (no time, so it won't alert you): {text}", f"حفظت تذكيراً (بلا وقت، فلن ينبّهك): {text}"
    return ToolResult(True, {"en": en, "ar": ar}, {"id": saved["id"]}, {"table": "reminders", "id": saved["id"]})


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
    # Step 3: mail rules and sharing change who receives Khalid's data; never done by Ahmad.
    "forward_all_mail", "set_forwarding", "create_mail_filter", "share_file", "change_sharing",
    "delete_email", "trash_email", "empty_trash", "delete_file",
}
NEVER_WORDS = ("pay", "money", "transfer", "purchase", "password", "security", "2fa", "mass", "broadcast", "bank",
               "forwarding", "filter", "share", "sharing", "trash")

# Step 3: Gmail, Calendar and Drive (personal_tools.py), each level fixed there.

TOOLS.update({t.name: t for t in PERSONAL_TOOLS})
