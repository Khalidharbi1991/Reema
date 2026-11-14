"""Times as Khalid reads them: 12-hour with AM/PM in English and ص/م in Arabic (Nov 14, 2026).

Used for everything the worker writes for Khalid to read: chat tool results, cards, the morning
brief. Times sent to tools and stored in the database stay ISO 8601 with their offset.
Western digits in both languages, as in the rest of Snafi.
"""

from datetime import datetime, time
from typing import Union

PERIOD = {"en": ("AM", "PM"), "ar": ("ص", "م")}
DAYS = {"en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        "ar": ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")}
MONTHS = {"en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
          "ar": ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر",
                 "نوفمبر", "ديسمبر")}


def clock(value: Union[datetime, time], lang: str = "en") -> str:
    """7:05 AM, 12:00 PM, 12:30 AM; in Arabic 7:05 ص, 12:00 م."""
    am, pm = PERIOD.get(lang, PERIOD["en"])
    hour = value.hour % 12 or 12
    return f"{hour}:{value.minute:02d} {pm if value.hour >= 12 else am}"


def day_clock(value: datetime, lang: str = "en") -> str:
    """Tue 18 Nov 7:05 PM; in Arabic الثلاثاء 18 نوفمبر 7:05 م."""
    lang = lang if lang in DAYS else "en"
    return f"{DAYS[lang][value.weekday()]} {value.day} {MONTHS[lang][value.month - 1]} {clock(value, lang)}"


def day_only(value: datetime, lang: str = "en") -> str:
    lang = lang if lang in DAYS else "en"
    return f"{DAYS[lang][value.weekday()]} {value.day} {MONTHS[lang][value.month - 1]}"


def hhmm_to_clock(hhmm: str, lang: str = "en") -> str:
    """"07:00" (as stored in user_settings) -> "7:00 AM"."""
    hour, minute = (int(x) for x in hhmm.split(":"))
    return clock(time(hour, minute), lang)
