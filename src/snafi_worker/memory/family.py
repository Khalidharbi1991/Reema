"""Family key dates: when each one next falls, and the reminder texts (no brain call here).

A date is kept in the Gregorian or the Hijri (Umm al-Qura) calendar. Its next day is found in the
Gregorian calendar: a Gregorian 29 February falls on 28 February in other years; a Hijri day 30 in a
29-day month falls on the month's last day. Reminders go out a week before and on the day.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Optional

from .base import RELATION_WORDS
from .hijri import to_gregorian, to_hijri

WEEK = 7


@dataclass(frozen=True)
class Occurrence:
    on: date            # the Gregorian day it falls on
    year: int           # the year it falls in, in its own calendar
    days_away: int


def next_occurrence(row: Dict, today: date) -> Optional[Occurrence]:
    month, day = int(row["month"]), int(row["day"])
    if row.get("calendar") == "hijri":
        here = to_hijri(today)
        if here is None:
            return None
        for year in (here[0], here[0] + 1):
            on = to_gregorian(year, month, day)
            if on is not None and on >= today:
                return Occurrence(on, year, (on - today).days)
        return None
    for year in (today.year, today.year + 1):
        try:
            on = date(year, month, day)
        except ValueError:  # 29 February in a year without it
            on = date(year, 2, 28)
        if on >= today:
            return Occurrence(on, year, (on - today).days)
    return None


def age_turning(row: Dict, occurrence: Occurrence) -> Optional[int]:
    born = row.get("year")
    if not isinstance(born, int) or occurrence.year <= born:
        return None
    return occurrence.year - born


T = {
    "en": {
        "birthday_week": "Birthday in a week · {n}", "birthday_day": "Birthday today · {n}",
        "anniversary_week": "Anniversary in a week · {n}", "anniversary_day": "Anniversary today · {n}",
        "other_week": "In a week · {t} · {n}", "other_day": "Today · {t} · {n}",
        "turns": "{n} ({r}) turns {a} on {d}.", "on": "{n} ({r}): {d}.", "years": "{a} years on {d}.",
        "gifts": "Gift ideas", "no_gifts": "Gift ideas weren't available this time.",
    },
    "ar": {
        "birthday_week": "عيد ميلاد بعد أسبوع · {n}", "birthday_day": "عيد ميلاد اليوم · {n}",
        "anniversary_week": "ذكرى بعد أسبوع · {n}", "anniversary_day": "ذكرى اليوم · {n}",
        "other_week": "بعد أسبوع · {t} · {n}", "other_day": "اليوم · {t} · {n}",
        "turns": "{n} ({r}) يكمل {a} عاماً في {d}.", "on": "{n} ({r}): {d}.", "years": "{a} عاماً في {d}.",
        "gifts": "أفكار للهدايا", "no_gifts": "لم تتوفر أفكار للهدايا هذه المرة.",
    },
}


def reminder_text(row: Dict, member: Dict, occurrence: Occurrence, when: str, lang: str):
    """(title, body) for a family date. `when` is the day already written for Khalid (e.g. Thursday 23 November)."""
    t = T[lang]
    stage = "day" if occurrence.days_away == 0 else "week"
    name = member.get("name") or "—"
    relation = RELATION_WORDS[lang].get(member.get("relation") or "other", "")
    label = row.get("label") or "other"
    title = t[f"{label}_{stage}"].format(n=name, t=row.get("title") or "")
    age = age_turning(row, occurrence)
    if label == "birthday" and age:
        body = t["turns"].format(n=name, r=relation, a=age, d=when)
    elif label == "anniversary" and age:
        body = t["years"].format(a=age, d=when)
    else:
        body = t["on"].format(n=name, r=relation, d=when)
    return title, body


def stage_key(row: Dict, occurrence: Occurrence) -> Optional[str]:
    """The never-twice key for today's reminder of this date, or None when nothing is due today."""
    if occurrence.days_away == WEEK:
        return f"family:{row['id']}:{occurrence.on.isoformat()}:week"
    if occurrence.days_away == 0:
        return f"family:{row['id']}:{occurrence.on.isoformat()}:day"
    return None


def days(n: int) -> timedelta:
    return timedelta(days=n)
