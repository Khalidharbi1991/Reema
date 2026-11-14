"""The honesty check: Ahmad may say "done", "sent" or "saved" only if a tool really did it.

The brain writes its reply before any action runs, so its words are checked against what
actually happened:
  - "sent" (and the like) is allowed only if a send really ran; no send ever runs in a chat
    turn, because sending needs Khalid's approval first.
  - other completion claims ("done", "saved", "added", ...) are allowed only if at least one
    action really succeeded in this turn.
  - step 4, two mail accounts: when a draft, send or draft delete is made or proposed in this
    turn, a sentence about mail that names only the other account (Gmail or Yahoo) is removed,
    so Ahmad never says a reply goes from the wrong account.
A sentence that breaks a rule is removed, and the real outcome of every action is always
added by code underneath, naming the account.
"""

import re
from typing import Iterable, List, Optional

AR_LETTER = "؀-ۿ"


def _arabic_words(*words: str) -> str:
    # Arabic has no \b: a word stands alone or after the و / ف prefix, never inside another word.
    return rf"(?<![{AR_LETTER}])[وف]?(?:{'|'.join(words)})(?![{AR_LETTER}])"


SEND = re.compile(r"\b(sent|emailed|messaged|forwarded|invited|shared)\b|"
                  + _arabic_words("أرسلت", "ارسلت", "أرسلنا", "بعثت", "تم الإرسال", "تم ارسال", "تم إرسال", "تم إرساله", "تم إرسالها"), re.I)
DONE = re.compile(
    r"\b(done|saved|added|created|scheduled|rescheduled|booked|deleted|removed|stored|recorded|noted|updated|set up"
    r"|completed|drafted)\b|"
    + _arabic_words("تم", "تمت", "حفظت", "أضفت", "اضفت", "سجلت", "سجّلت", "أنشأت", "حذفت", "جدولت", "أكملت",
                    "نفذت", "نفّذت"), re.I)
SENTENCE = re.compile(r"[^.!?؟\n]+[.!?؟]?\s*")
NEUTRAL = {"en": "Here is where things stand:", "ar": "هذا وضع طلبك:"}


def _arabic_name(*words: str) -> str:
    # SEC-109: an account name may follow و / ف and then ب / ل / ال / بال / لل (بياهو، لياهو، الياهو، بالجيميل).
    return rf"(?<![{AR_LETTER}])[وف]?(?:بال|لل|ال|ب|ل)?(?:{'|'.join(words)})(?![{AR_LETTER}])"


ACCOUNT_NAMES = {
    "gmail": re.compile(r"\bg-?mail\b|\bgoogle\b|" + _arabic_name("جيميل", "جي ميل", "جوجل", "قوقل", "غوغل"), re.I),
    "yahoo": re.compile(r"\byahoo\b|" + _arabic_name("ياهو"), re.I),
}
MAIL_WORDS = re.compile(r"\b(drafts?|drafted|send|sending|sent|repl(y|ies|ied)|e-?mails?|mail|from)\b|"
                        r"مسود|إرسال|ارسال|يرسل|سأرسل|الرد|ردّ|بريد|رسالة", re.I)


def _wrong_account(sentence: str, accounts: Iterable[str]) -> bool:
    used = set(accounts)
    named = {name for name, pattern in ACCOUNT_NAMES.items() if pattern.search(sentence)}
    return bool(named) and not (named & used) and bool(MAIL_WORDS.search(sentence))


def check(reply: str, lang: str, succeeded: Iterable[str], sends_ran: bool = False,
          accounts: Optional[Iterable[str]] = None) -> str:
    """Return the reply with any unearned claim removed. succeeded: tool names that really ran OK.
    accounts: the mail accounts ("gmail", "yahoo") drafted in, sent from or proposed in this turn."""
    any_success = bool(list(succeeded))
    accounts = list(accounts or [])
    kept: List[str] = []
    for sentence in SENTENCE.findall(reply or ""):
        if SEND.search(sentence) and not sends_ran:
            continue
        if DONE.search(sentence) and not any_success and not sends_ran:
            continue
        if accounts and _wrong_account(sentence, accounts):
            continue
        kept.append(sentence)
    text = "".join(kept).strip()
    return text or NEUTRAL.get(lang, NEUTRAL["en"])


def unearned(reply: str, succeeded: Iterable[str], sends_ran: bool = False) -> bool:
    return check(reply, "en", succeeded, sends_ran).strip() != (reply or "").strip()
