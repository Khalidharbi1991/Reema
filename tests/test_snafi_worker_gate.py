"""Snafi worker: the permission gate (four levels, in code) and the honesty check."""

import pytest

from src.snafi_worker.brain import ProposedAction
from src.snafi_worker.gate import APPROVE, REFUSE, RUN, decide
from src.snafi_worker.honesty import check, unearned
from src.snafi_worker.lang import detect_lang
from src.snafi_worker.tools import TOOLS


@pytest.mark.parametrize("tool,args,verdict,level", [
    ("list_notes", {}, RUN, 1),
    ("list_facts", {"limit": 5}, RUN, 1),
    ("add_note", {"body": "Call the architect"}, RUN, 2),
    ("add_reminder", {"body": "Renew iqama", "due": "2026-11-10T09:00+03:00"}, RUN, 2),
    ("add_fact", {"body": "Prefers Arabic in the morning"}, RUN, 2),
    ("send_test_message", {"text": "hello"}, APPROVE, 3),
    ("make_payment", {"amount": "500"}, REFUSE, 4),
    ("change_password", {}, REFUSE, 4),
    ("send_mass_message", {"text": "hi all"}, REFUSE, 4),
    ("bank_transfer_now", {}, REFUSE, 4),
    ("delete_all_email", {}, REFUSE, 0),
    ("run_shell", {"cmd": "rm -rf /"}, REFUSE, 0),
])
def test_gate_levels_come_from_code(tool, args, verdict, level):
    d = decide(ProposedAction(tool, args))
    assert (d.verdict, d.level) == (verdict, level)


def test_the_brain_cannot_lower_a_level():
    d = decide(ProposedAction("send_test_message", {"text": "x"}, claimed_level=1))
    assert d.verdict == APPROVE and d.level == 3
    d = decide(ProposedAction("make_payment", {"amount": "1"}, claimed_level=1))
    assert d.verdict == REFUSE and d.level == 4


@pytest.mark.parametrize("tool,args,why", [
    ("add_note", {}, "required"),
    ("add_note", {"body": 42}, "text"),
    ("add_fact", {"body": "x" * 1001}, "too long"),
    ("list_notes", {"limit": True}, "number"),   # limit 500 is now lowered to 20, not refused (test_snafi_worker_limits.py)
    ("add_reminder", {"body": "x", "due": "tomorrow"}, "date"),
    ("add_reminder", {"body": "x", "due": "2026-11-10T09:00"}, "time zone"),
])
def test_gate_refuses_bad_arguments(tool, args, why):
    d = decide(ProposedAction(tool, args))
    assert d.verdict == REFUSE and why in d.reason["en"]


def test_every_tool_has_a_level_and_level_two_tools_can_be_undone():
    assert {t.level for t in TOOLS.values()} == {1, 2, 3}
    assert all(t.undo for t in TOOLS.values() if t.level == 2)


@pytest.mark.parametrize("reply,lang,succeeded,expected", [
    ("I saved your note.", "en", [], "Here is where things stand:"),
    ("I saved your note.", "en", ["add_note"], "I saved your note."),
    ("Sure. I sent the message to the architect.", "en", ["add_note"], "Sure."),
    ("Done! Anything else?", "en", [], "Anything else?"),
    ("حفظت الملاحظة.", "ar", [], "هذا وضع طلبك:"),
    ("حاضر. تم إرسال الرسالة.", "ar", ["add_note"], "حاضر."),
    ("وأرسلت الدعوة.", "ar", ["add_note"], "هذا وضع طلبك:"),
    ("أقدّر اهتمامك. سأجهّزها لموافقتك.", "ar", [], "أقدّر اهتمامك. سأجهّزها لموافقتك."),
    ("I've prepared it for your approval.", "en", [], "I've prepared it for your approval."),
])
def test_honesty_check_removes_unearned_claims(reply, lang, succeeded, expected):
    assert check(reply, lang, succeeded) == expected


def test_send_claims_need_a_real_send():
    assert unearned("I sent it.", ["add_note"])
    assert not unearned("I sent it.", [], sends_ran=True)


@pytest.mark.parametrize("text,lang", [("Save a note", "en"), ("احفظ ملاحظة", "ar"),
                                       ("ذكّرني بموعد Dr. Ali", "ar"), ("", "en"), ("123", "en")])
def test_language_is_decided_in_code(text, lang):
    assert detect_lang(text) == lang
