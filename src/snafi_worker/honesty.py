"""The honesty check: Ahmad may say "done", "sent" or "saved" only if a tool really did it.

The brain writes its reply before any action runs, so its words are checked against what
actually happened:
  - "sent" (and the like) is allowed only if a send really ran; no send ever runs in a chat
    turn, because sending needs Khalid's approval first.
  - other completion claims ("done", "saved", "added", ...) are allowed only if at least one
    action really succeeded in this turn.
A sentence that breaks a rule is removed, and the real outcome of every action is always
added by code underneath.
"""

import re
from typing import Iterable, List

AR_LETTER = "؀-ۿ"


def _arabic_words(*words: str) -> str:
    # Arabic has no \b: a word stands alone or after the و / ف prefix, never inside another word.
    return rf"(?<![{AR_LETTER}])[وف]?(?:{'|'.join(words)})(?![{AR_LETTER}])"


SEND = re.compile(r"\b(sent|emailed|messaged|forwarded|invited|shared)\b|"
                  + _arabic_words("أرسلت", "ارسلت", "أرسلنا", "بعثت", "تم الإرسال", "تم ارسال", "تم إرسال", "تم إرساله", "تم إرسالها"), re.I)
DONE = re.compile(
    r"\b(done|saved|added|created|scheduled|booked|deleted|removed|stored|recorded|noted|updated|set up|completed)\b|"
    + _arabic_words("تم", "تمت", "حفظت", "أضفت", "اضفت", "سجلت", "سجّلت", "أنشأت", "حذفت", "جدولت", "أكملت",
                    "نفذت", "نفّذت"), re.I)
SENTENCE = re.compile(r"[^.!?؟\n]+[.!?؟]?\s*")
NEUTRAL = {"en": "Here is where things stand:", "ar": "هذا وضع طلبك:"}


def check(reply: str, lang: str, succeeded: Iterable[str], sends_ran: bool = False) -> str:
    """Return the reply with any unearned claim removed. succeeded: tool names that really ran OK."""
    any_success = bool(list(succeeded))
    kept: List[str] = []
    for sentence in SENTENCE.findall(reply or ""):
        if SEND.search(sentence) and not sends_ran:
            continue
        if DONE.search(sentence) and not any_success and not sends_ran:
            continue
        kept.append(sentence)
    text = "".join(kept).strip()
    return text or NEUTRAL.get(lang, NEUTRAL["en"])


def unearned(reply: str, succeeded: Iterable[str], sends_ran: bool = False) -> bool:
    return check(reply, "en", succeeded, sends_ran).strip() != (reply or "").strip()
