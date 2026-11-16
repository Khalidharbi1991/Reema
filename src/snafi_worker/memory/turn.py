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
from .search import Item
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
    return all_items(book, user_id)


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


def forgetful(reply: str) -> bool:
    return bool(DONT_REMEMBER.search(reply or ""))


def drop_forgetful(reply: str) -> str:
    return "".join(s for s in SENTENCE.findall(reply or "") if not DONT_REMEMBER.search(s)).strip()


def recall_line(found: Sequence[Item], lang: str) -> str:
    bullets = "\n".join(f"• {i.text[:160]}" for i in found)
    return f"{FROM_MEMORY[lang]}\n{bullets}"
