"""Arabic and English text normalised for memory search and the no-secrets check.

The same steps as public.snafi_norm in migration 0010, so the worker, the database and the app agree:
  أ إ آ ٱ -> ا,  ة -> ه,  ى -> ي,  Arabic-Indic digits -> 0-9,
  tashkeel (U+064B-U+065F), the dagger alef (U+0670) and tatweel (U+0640) removed, then lower case.
"""

import re

_MAP = str.maketrans("أإآٱةى٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "ااااهي01234567890123456789")
_MARKS = re.compile("[ً-ٰٟـ]")
_SPACE = re.compile(r"\s+")
_WORD = re.compile(r"[0-9a-zء-ي]+")


def normalise(text: str) -> str:
    return _MARKS.sub("", (text or "").translate(_MAP)).lower()


def squash(text: str) -> str:
    """Normalised, with runs of white space made one space (for comparing two facts)."""
    return _SPACE.sub(" ", normalise(text)).strip()


def words(text: str):
    return _WORD.findall(normalise(text))
