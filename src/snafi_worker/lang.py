"""Language of Khalid's message: Arabic or English, decided in code."""

import re

ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LATIN = re.compile(r"[A-Za-z]")


def detect_lang(text: str) -> str:
    arabic, latin = len(ARABIC.findall(text or "")), len(LATIN.findall(text or ""))
    return "ar" if arabic and arabic >= latin else "en"
