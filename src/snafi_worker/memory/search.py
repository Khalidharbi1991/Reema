"""Memory search adapters. Keyword search today; meaning search (pgvector) can replace it later by one
setting in worker.yaml (memory.search) plus its own file.

Keyword search: both the question and every memory item are normalised first (أإآ -> ا, ة -> ه,
ى -> ي, no tashkeel, lower case), so "زوجتى" finds "زوجتي" and "Sara" finds "sara". An item scores
one point per question word found inside it; common words do not count.
"""

from dataclasses import dataclass
from typing import Dict, List, Sequence

from ..registry import register
from .normalise import normalise, words

STOP = frozenset({
    # English
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "for", "is", "are", "was", "were", "be", "my",
    "me", "i", "you", "your", "do", "does", "did", "what", "who", "when", "where", "which", "how", "about", "it",
    "that", "this", "with", "from", "remember", "know", "tell", "please", "can", "could", "her", "his", "their",
    # Arabic (normalised)
    "في", "من", "علي", "الي", "عن", "ما", "ماذا", "متي", "اين", "هل", "كيف", "هو", "هي", "انا", "انت", "لي",
    "مع", "او", "و", "ان", "كان", "التي", "الذي", "هذا", "هذه", "تذكر", "تعرف", "اعرف", "قل", "لو", "يا",
})


@dataclass(frozen=True)
class Item:
    kind: str       # "fact", "member" or "date"
    id: str
    text: str       # what Ahmad and the About me page show
    section: str    # me, family, preferences, routine


@register("memory_search", "keyword")
class KeywordSearch:
    SECRET_NAMES = ()

    def __init__(self, options: Dict = None, secrets=None):
        self.options = dict(options or {})

    @staticmethod
    def terms(query: str) -> List[str]:
        out = []
        for word in words(query):
            if word in STOP or len(word) < 2:
                continue
            out.append(word)
            if word.startswith("ال") and len(word) > 3:  # "الزواج" also finds "زواج"
                out.append(word[2:])
        return list(dict.fromkeys(out))

    def search(self, items: Sequence[Item], query: str, limit: int = 15) -> List[Item]:
        terms = self.terms(query)
        if not terms:
            return []
        scored = []
        for index, item in enumerate(items):
            text = normalise(item.text)
            score = sum(1 for t in terms if t in text)
            if score:
                scored.append((-score, index, item))
        scored.sort()
        return [item for _, _, item in scored[:limit]]
