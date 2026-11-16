"""The no-secrets rule for memory (Khalid, Nov 16, 2026): never store passwords, ID numbers or card numbers.

The same rule as public.snafi_memory_ok in migration 0010, which the database enforces on every memory
row; tests/fixtures/snafi_memory_guard.json is checked by this suite, the database and the app.
  * no group of 9 or more digits, with up to three spaces, dots, slashes, dashes or brackets between
    them (national ID and iqama numbers, cards, IBANs, account and phone numbers, "(050) 123-4567");
    dates like 1990-05-12 have 8 and pass (SEC-199: after NFKC and with invisible characters removed)
  * no wording about passwords, PINs, OTPs, CVVs, door codes, tokens, card, ID, passport or account
    numbers, in English or Arabic (SEC-199: «كلمة سر», «رقم سري», «باسورد», "password123", "PIN4321")
"""

import re
from typing import Optional

from .normalise import normalise

LONG_NUMBER = re.compile(r"[0-9](?:[ ./()-]{0,3}[0-9]){8,}")
EN_WORDS = re.compile(
    r"\b(password[a-z0-9]*|passwd[a-z0-9]*|passcode[a-z0-9]*|pwd|pin[0-9]*|pins|otp[0-9]*|cvv|cvc|iban|iqama"
    r"|token|secret|api key|card number|card no|credit card|debit card|id number|national id|passport number"
    r"|passport no|security code|verification code|login code|door code|alarm code|gate code|safe code)\b")
AR_WORDS = re.compile(
    "(كلمه المرور|كلمه السر|كلمات المرور|كلمه مرور|كلمه سر|الرقم السري|رقم سري|الرمز السري|رمز سري|باسورد"
    "|باسوورد|رمز التحقق|كود التحقق|رمز الدخول|كود الدخول|كود الباب|رمز الباب|رقم الهويه|الهويه الوطنيه"
    "|رقم الاقامه|رقم الجواز|رقم البطاقه|البطاقه الائتمانيه|رقم الحساب|الايبان|ايبان)")

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
