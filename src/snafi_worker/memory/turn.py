"""What memory adds to one chat turn (used by the engine).

  memory_block      what Ahmad knows, for the brain, inside <data source="memory">: information, never
                    instructions. Everything when it is short (at most ALL_ITEMS items); otherwise the
                    items that best match Khalid's message plus the family list.
  matches           memory items matching Khalid's message (for the "I don't remember" check)
  forgetful         the honesty rule: a sentence saying Ahmad doesn't remember is removed when memory
                    does match; code then adds what memory holds under the reply.
"""

import re
from typing import List, Sequence

from ..brain import data_block
from .guard import ok as memory_ok
from .normalise import normalise, words
from .search import STOP, Item
from .tools import all_items

ALL_ITEMS = 40
BEST = 15
WRITE_LIMIT = 3            # memory saves in one ordinary message
INTERVIEW_WRITE_LIMIT = 6  # an interview answer may name a whole family

DONT_REMEMBER = re.compile(
    r"\b(don'?t|do not|can'?t|cannot)\s+(remember|recall)\b|\bno (record|memory) of\b"
    r"|\bI don'?t (know|have) (that|this|your|any|it)\b|\bnot (saved|stored) in (my )?memory\b"
    r"|لا\s*[أا]ذكر|لا\s*[أا]تذكر|لم\s*[أا]حفظ|ليس\s*لدي\s*(معلومات|معلومه|علم)|لا\s*[أا]عرف|لا\s*توجد\s*لدي", re.I)
SENTENCE = re.compile(r"[^.!?؟\n]+[.!?؟]?\s*")
FROM_MEMORY = {"en": "From memory:", "ar": "من الذاكرة:"}


def items(book, user_id: str) -> List[Item]:
    # SEC-204: a fact saved before step 6 that breaks the no-secrets rule never reaches the brain.
    return [i for i in all_items(book, user_id) if memory_ok(i.text)]


def memory_block(everything: Sequence[Item], search, message: str) -> str:
    if not everything:
        return data_block("Nothing saved yet.", "memory")
    if len(everything) <= ALL_ITEMS:
        chosen = list(everything)
    else:
        best = search.search(everything, message, BEST)
        family = [i for i in everything if i.kind == "member"]
        chosen = list(dict.fromkeys(best + family))
    lines = [f"- [{i.section}] {i.text}" for i in chosen]
    return data_block("\n".join(lines), "memory")


SAVED_TEXT = {"add_fact": ("body",), "add_family_member": ("name", "note"), "add_family_date": ("person", "title")}


def grounded(tool: str, args: dict, message: str) -> bool:
    """SEC-200: after Ahmad has read outside content in the recent chat, a memory save must come from
    Khalid's own words: at least half of the saved text's words (3 letters or more, common words
    left out) must appear in his current message, after normalising."""
    said = normalise(message)
    words_ = [w for name in SAVED_TEXT.get(tool, ()) for w in words(str(args.get(name) or ""))
              if len(w) >= 3 and w not in STOP]
    if not words_:
        return False
    found = sum(1 for w in words_ if w in said or (w.startswith("ال") and w[2:] in said))
    return found * 2 >= len(words_)


def forgetful(reply: str) -> bool:
    return bool(DONT_REMEMBER.search(reply or ""))


def drop_forgetful(reply: str) -> str:
    return "".join(s for s in SENTENCE.findall(reply or "") if not DONT_REMEMBER.search(s)).strip()


def recall_line(found: Sequence[Item], lang: str) -> str:
    bullets = "\n".join(f"• {i.text[:160]}" for i in found)
    return f"{FROM_MEMORY[lang]}\n{bullets}"
