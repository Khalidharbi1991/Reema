"""The scheduler (PRD "Scheduler (not an agent)"): a thread in the worker, no Vercel cron, no brain call.

Every TICK seconds, each job runs once, short, and on its own (one failing never stops the others):
  held       messages held for prayer time go out once it ends
  reminders  saved reminders whose time has come go off once: a card plus a push (reminders never
             count toward the daily cap)
  brief      the morning brief once a day at Khalid's time (user_settings.brief_time, default 7:00 AM),
             or later the same morning if the PC was off then (until BRIEF_WINDOW hours after it)
  mail       every MAIL_MINUTES: a card and a push only for truly important new mail (Gmail: unread,
             Inbox, Important, Primary; Yahoo: the Today rule and from someone Khalid emailed from Yahoo
             in the last 90 days). The first run for each account only learns what is already there.
  clear      once an hour, cards and the sent record older than 30 days are deleted (SEC-127)
Everything goes through Notifier.deliver, which enforces the manners (see notify.py). Texts are
built here from fixed templates in English or Arabic (user_settings.lang), times 12-hour with
AM/PM or ص/م. Only sender names and subjects of mail are used, never a body.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from zoneinfo import ZoneInfo

from ..clock import clock, day_clock, day_only
from ..today_feed import _emails, _tasks, sender_name
from .notify import Notifier, _parse
from .prayer import ORDER, prayer_times

log = logging.getLogger("snafi_worker")
TICK = 30
MAIL_MINUTES = 10
BRIEF_WINDOW = timedelta(hours=5)
CLEAR_EVERY = timedelta(hours=1)
WATCH_HOURS = 24
WATCH_LIMIT = 10
BRIEF_ITEMS = 5
REMINDER_SCAN = 200
ACCOUNTS = {"gmail": ("Gmail", "Gmail"), "yahoo": ("Yahoo", "Yahoo")}

T = {
    "en": {
        "reminder": "Reminder", "set_for": "Set for {t}", "was_due": "Was due {t}",
        "brief": "Good morning · {d}", "prayers": "Prayer times", "events": "Today's events",
        "no_events": "No events today.", "tasks": "Top tasks", "no_tasks": "Nothing due today.",
        "mail": "Important email", "no_mail": "No important unread email.", "unread": "couldn't be read just now",
        "overdue": "overdue", "all_day": "All day",
        "prayer_names": {"fajr": "Fajr", "dhuhr": "Dhuhr", "asr": "Asr", "maghrib": "Maghrib", "isha": "Isha"},
        "new_mail": "{a} · {s}", "received": "Received {t}",
        "test": "Test from Ahmad", "test_body": "If this reached your phone, push notifications work.",
    },
    "ar": {
        "reminder": "تذكير", "set_for": "موعده {t}", "was_due": "كان موعده {t}",
        "brief": "صباح الخير · {d}", "prayers": "مواقيت الصلاة", "events": "مواعيد اليوم",
        "no_events": "لا مواعيد اليوم.", "tasks": "أهم المهام", "no_tasks": "لا شيء مستحق اليوم.",
        "mail": "بريد مهم", "no_mail": "لا بريد مهم غير مقروء.", "unread": "تعذّرت قراءته الآن",
        "overdue": "متأخرة", "all_day": "طوال اليوم",
        "prayer_names": {"fajr": "الفجر", "dhuhr": "الظهر", "asr": "العصر", "maghrib": "المغرب", "isha": "العشاء"},
        "new_mail": "{a} · {s}", "received": "وصل {t}",
        "test": "تجربة من أحمد", "test_body": "إذا وصلك هذا على هاتفك فالإشعارات تعمل.",
    },
}


def _cut(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


class Scheduler(threading.Thread):
    def __init__(self, notifier: Notifier, personal, stop: Optional[threading.Event] = None,
                 time_zone: str = "Asia/Riyadh", latitude: float = 21.4858, longitude: float = 39.1925,
                 mail_minutes: float = MAIL_MINUTES):
        super().__init__(name="scheduler", daemon=True)
        self.notifier, self.personal = notifier, personal
        self.store, self.owner_id = notifier.store, notifier.owner_id
        self.stop = stop or threading.Event()
        self.tz = ZoneInfo(time_zone)
        self.latitude, self.longitude = latitude, longitude
        self.mail_every = timedelta(minutes=max(2.0, float(mail_minutes)))
        self.last_mail: Optional[datetime] = None
        self.last_clear: Optional[datetime] = None

    # ---------- one pass ----------
    def tick(self, now: Optional[datetime] = None) -> Dict[str, object]:
        now = now or datetime.now(timezone.utc)
        out: Dict[str, object] = {}
        for name, job in (("held", self.release_held), ("reminders", self.reminders), ("brief", self.brief),
                          ("mail", self.mail_watch), ("clear", self.clear_old)):
            try:
                out[name] = job(now)
            except Exception as exc:  # noqa: BLE001 (only the type is logged, never any text)
                log.warning("scheduler %s failed: %s", name, type(exc).__name__)
                out[name] = "error"
        return out

    def run(self):
        while not self.stop.is_set():
            self.tick()
            self.stop.wait(TICK)

    def _lang(self) -> str:
        return self.notifier.settings()["lang"]

    # ---------- SEC-127: clear cards and the sent record after 30 days (once an hour) ----------
    def clear_old(self, now: datetime):
        if self.last_clear is not None and now - self.last_clear < CLEAR_EVERY:
            return None
        self.last_clear = now
        return self.notifier.prune(now)

    # ---------- held ----------
    def release_held(self, now: datetime):
        return self.notifier.release_held(now)

    # ---------- reminders ----------
    def reminders(self, now: datetime) -> List[str]:
        rows = self.store.select("reminders", {"user_id": self.owner_id}, order="due_at", limit=REMINDER_SCAN,
                                 null=("deleted_at", "fired_at"))
        t = T[self._lang()]
        lang = self._lang()
        out = []
        for row in rows:
            due = _parse(row.get("due_at"))
            if due is None or due > now:
                continue
            local = due.astimezone(self.tz)
            same_day = local.date() == now.astimezone(self.tz).date()
            when = t["set_for"].format(t=clock(local, lang)) if same_day else t["was_due"].format(t=day_clock(local, lang))
            # SEC-121: the ledger row (UNIQUE reminder:<id>) comes first, so it goes off once; fired_at is
            # set only after it exists, so an error in between means it is tried again, never lost.
            outcome = self.notifier.deliver("reminder", f"reminder:{row['id']}", t["reminder"],
                                            f"{_cut(row.get('body') or '', 900)}\n{when}", counts_to_cap=False, now=now)
            self.store.update_if("reminders", row["id"], {"fired_at": None}, {"fired_at": now.isoformat()})
            if outcome != "duplicate":
                out.append(outcome)
        return out

    # ---------- morning brief ----------
    def brief_due(self, now: datetime) -> Optional[str]:
        settings = self.notifier.settings()
        local = now.astimezone(self.tz)
        hour, minute = (int(x) for x in settings["brief_time"].split(":"))
        start = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if not start <= local < start + BRIEF_WINDOW:
            return None
        key = f"brief:{local.date().isoformat()}"
        return None if self.notifier.known(key) else key

    def brief(self, now: datetime) -> Optional[str]:
        key = self.brief_due(now)
        if key is None:
            return None
        lang = self._lang()
        title, body = self.compose_brief(now, lang)
        return self.notifier.deliver("brief", key, title, body, counts_to_cap=True, now=now)

    def compose_brief(self, now: datetime, lang: str):
        t = T[lang]
        local = now.astimezone(self.tz)
        title = t["brief"].format(d=day_only(local, lang))
        times = prayer_times(local.date(), self.latitude, self.longitude)
        prayers = " · ".join(f"{t['prayer_names'][p]} {clock(times[p].astimezone(self.tz), lang)}" for p in ORDER)
        sections = [f"{t['prayers']}: {prayers}"]
        sections.append(self._section(t["events"], lambda: self._events(local, lang), t, t["no_events"]))
        sections.append(self._section(t["tasks"], lambda: self._top_tasks(now, t), t, t["no_tasks"]))
        sections.append(self._section(t["mail"], lambda: self._important_mail(now, lang), t, t["no_mail"]))
        return title, "\n\n".join(s for s in sections if s)

    @staticmethod
    def _section(heading: str, read, t, empty: str) -> str:
        try:
            lines = read()
        except Exception as exc:  # noqa: BLE001 (each source on its own; the brief still goes out)
            log.warning("brief: a source failed (%s)", type(exc).__name__)
            return f"{heading}: {t['unread']}"
        if lines is None:
            return ""
        return f"{heading}:\n" + "\n".join(f"• {line}" for line in lines) if lines else f"{heading}: {empty}"

    def _events(self, local: datetime, lang: str):
        calendar = getattr(self.personal, "calendar", None)
        if calendar is None:
            return None
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        events = calendar.list_events(start.isoformat(), (start + timedelta(days=1)).isoformat(), 10)
        lines = []
        for e in events[:BRIEF_ITEMS]:
            if e.all_day:
                at = T[lang]["all_day"]
            else:
                when = _parse(e.start)
                at = clock(when.astimezone(self.tz), lang) if when else ""
            place = f" · {_cut(e.location, 60)}" if e.location else ""
            lines.append(f"{at} {_cut(e.title, 80) or '—'}{place}".strip())
        return lines

    def _top_tasks(self, now: datetime, t):
        tasks = getattr(self.personal, "tasks", None)
        if tasks is None:
            return None
        return [f"{_cut(x['content'], 80)}{' (' + t['overdue'] + ')' if x['overdue'] else ''}"
                for x in _tasks(tasks, now, self.tz)[:BRIEF_ITEMS]]

    def _important_mail(self, now: datetime, lang: str):
        accounts = [(a, getattr(self.personal, attr, None)) for a, attr in (("gmail", "mail"), ("yahoo", "yahoo"))]
        accounts = [(a, m) for a, m in accounts if m is not None]
        if not accounts:
            return None
        found, failed = [], 0
        for account, mail in accounts:
            try:
                found += _emails(mail, account)
            except Exception as exc:  # noqa: BLE001
                log.warning("brief: %s failed (%s)", account, type(exc).__name__)
                failed += 1
        if failed == len(accounts):
            raise RuntimeError("no mail account could be read")
        found.sort(key=lambda m: m.get("received_at") or "", reverse=True)
        return [f"[{ACCOUNTS[m['account']][0]}] {_cut(m['from'], 40)}: {_cut(m['subject'], 80)}"
                for m in found[:BRIEF_ITEMS]]

    # ---------- mail watch ----------
    def mail_watch(self, now: datetime):
        if self.last_mail is not None and now - self.last_mail < self.mail_every:
            return None
        self.last_mail = now
        out = {}
        for account, attr in (("gmail", "mail"), ("yahoo", "yahoo")):
            adapter = getattr(self.personal, attr, None)
            if adapter is None or not hasattr(adapter, "watch_unread"):
                continue
            try:
                out[account] = self._watch(account, adapter, now)
            except Exception as exc:  # noqa: BLE001 (each account on its own)
                log.warning("mail watch: %s failed (%s)", account, type(exc).__name__)
                out[account] = "error"
        return out

    def _watch(self, account: str, adapter, now: datetime):
        found = adapter.watch_unread(WATCH_HOURS, WATCH_LIMIT)
        marker = f"mail-learned:{account}"
        if not self.notifier.known(marker):
            for m in found:
                self.notifier.learn(f"mail:{account}:{m.id}")
            self.notifier.learn(marker)
            log.info("mail watch: %s first run learned %d", account, len(found))
            return f"learned {len(found)}"
        lang = self._lang()
        t = T[lang]
        results = []
        for m in found:
            key = f"mail:{account}:{m.id}"
            if self.notifier.known(key):
                continue
            when = _parse(m.date)
            received = t["received"].format(t=day_clock(when.astimezone(self.tz), lang)) if when else ""
            title = t["new_mail"].format(a=ACCOUNTS[account][0], s=sender_name(m.sender) or "—")
            body = "\n".join(x for x in (_cut(m.subject, 300) or "—", received) if x)
            results.append(self.notifier.deliver("mail", key, title, body, counts_to_cap=True, now=now))
        return results

    # ---------- test push (a background job from Settings) ----------
    def test_push(self, job_id: str, now: Optional[datetime] = None) -> str:
        now = now or datetime.now(timezone.utc)
        lang = self._lang()
        body = f"{T[lang]['test_body']}\n{day_clock(now.astimezone(self.tz), lang)}"
        return self.notifier.deliver("test", f"test:{job_id}", T[lang]["test"], body, counts_to_cap=False, now=now)
