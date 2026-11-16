"""The no-secrets rule for memory (Khalid, Nov 16, 2026): never store passwords, ID numbers or card numbers.

The same rule as public.snafi_memory_ok in migration 0010, which the database enforces on every memory
row; tests/fixtures/snafi_memory_guard.json is checked by this suite, the database and the app.
  * no group of 9 or more digits, spaces, dots or dashes allowed between them (national ID and iqama
    numbers, cards, IBANs, account and phone numbers); dates like 1990-05-12 have 8 and pass
  * no wording about passwords, PINs, OTPs, CVVs, tokens, card, ID, passport or account numbers,
    in English or Arabic
"""

import re
from typing import Optional

from .normalise import normalise

LONG_NUMBER = re.compile(r"[0-9](?:[ .-]?[0-9]){8,}")
EN_WORDS = re.compile(
    r"\b(password|passwords|passcode|passwd|pin|pins|otp|cvv|cvc|iban|iqama|token|secret|api key|card number"
    r"|card no|credit card|debit card|id number|national id|passport number|passport no|security code"
    r"|verification code|login code)\b")
AR_WORDS = re.compile(
    "(كلمه المرور|كلمه السر|كلمات المرور|الرقم السري|الرمز السري|رمز التحقق|رمز الدخول|رقم الهويه"
    "|الهويه الوطنيه|رقم الاقامه|رقم الجواز|رقم البطاقه|البطاقه الائتمانيه|رقم الحساب|الايبان|ايبان)")

REASONS = {
    "number": {"en": "memory never keeps long numbers (ID, card, account or phone numbers)",
               "ar": "الذاكرة لا تحفظ الأرقام الطويلة (أرقام الهوية أو البطاقات أو الحسابات أو الجوال)"},
    "secret": {"en": "memory never keeps passwords, codes, or ID and card numbers",
               "ar": "الذاكرة لا تحفظ كلمات المرور أو الرموز أو أرقام الهوية والبطاقات"},
}


def refusal(text: str) -> Optional[str]:
    """None if the text may be stored, else "number" or "secret"."""
    norm = normalise(text)
    if LONG_NUMBER.search(norm):
        return "number"
    if EN_WORDS.search(norm) or AR_WORDS.search(norm):
        return "secret"
    return None


def ok(text: str) -> bool:
    return refusal(text) is None
