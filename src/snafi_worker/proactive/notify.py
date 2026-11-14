"""The one door every proactive message goes through. The manners are enforced here, in code:

  1. Never twice.  Each message has a dedupe key (reminder:<id>, brief:<date>, mail:<account>:<id>,
                   test:<job id>). The ledger row is inserted with ON CONFLICT DO NOTHING on the
                   UNIQUE (user_id, dedupe_key): a second try finds it and stops, before anything is
                   shown or pushed. A row is claimed (new/held -> delivering) in one conditional update
                   before its card and push, so a crash part-way never sends it again; it may at worst
                   stay unsent ("delivering"), which the log shows.
  2. No repeats.   A message whose title and body (content_hash) match one already shown in the last
                   24 hours is skipped.
  3. Prayer quiet. Nothing for QUIET_MINUTES (20) after each adhan (Jeddah, Umm al-Qura). A message
                   due then is held and goes out when the quiet time ends (Khalid, Nov 14, 2026).
  4. Daily cap.    At most user_settings.daily_cap pushes (default 10) per Jeddah day. Reminders do not
                   count (Khalid set them himself). Past the cap the card still appears, silently.
  5. Lock screen.  The push carries only its kind, language and id (webpush.payload); the phone shows
                   fixed text. The card with the details is inside the signed-in app only.
  Night: no quiet hours. Ahmad may message any time (Khalid's phone is silent at night).
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from zoneinfo import ZoneInfo

from .prayer import quiet_until

log = logging.getLogger("snafi_worker")
QUIET_MINUTES = 20
DEFAULT_SETTINGS = {"push_enabled": False, "brief_time": "07:00", "daily_cap": 10, "lang": "en"}
TITLE_MAX, BODY_MAX = 200, 3000
REPEAT_HOURS = 24
LEDGER_SCAN = 500
MAX_FAILURES = 5


def content_hash(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\n{body}".encode("utf-8")).hexdigest()


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


class Notifier:
    def __init__(self, store, owner_id: str, sender=None, time_zone: str = "Asia/Riyadh",
                 latitude: float = 21.4858, longitude: float = 39.1925, quiet_minutes: int = QUIET_MINUTES):
        self.store, self.owner_id, self.sender = store, owner_id, sender
        self.tz = ZoneInfo(time_zone)
        self.latitude, self.longitude, self.quiet_minutes = latitude, longitude, quiet_minutes

    # ---------- settings ----------
    def settings(self) -> Dict:
        rows = self.store.select("user_settings", {"user_id": self.owner_id}, order="user_id", limit=1)
        merged = dict(DEFAULT_SETTINGS)
        if rows:
            merged.update({k: rows[0][k] for k in DEFAULT_SETTINGS if rows[0].get(k) is not None})
        cap = merged["daily_cap"]
        merged["daily_cap"] = cap if isinstance(cap, int) and 1 <= cap <= 50 else DEFAULT_SETTINGS["daily_cap"]
        if merged["lang"] not in ("en", "ar"):
            merged["lang"] = "en"
        return merged

    def quiet_until(self, now: datetime) -> Optional[datetime]:
        return quiet_until(now, self.latitude, self.longitude, self.tz, self.quiet_minutes)

    # ---------- the door ----------
    def learn(self, dedupe_key: str) -> bool:
        """Record something as already known, without telling Khalid (the mail watch's first run)."""
        row = {"user_id": self.owner_id, "kind": "learned", "dedupe_key": dedupe_key, "status": "skipped",
               "reason": "already there on the first run", "counts_to_cap": False}
        return self.store.insert_once("notifications", row, ("user_id", "dedupe_key")) is not None

    def known(self, dedupe_key: str) -> bool:
        return bool(self.store.select("notifications", {"user_id": self.owner_id, "dedupe_key": dedupe_key}, limit=1))

    def deliver(self, kind: str, dedupe_key: str, title: str, body: str, counts_to_cap: bool = True,
                now: Optional[datetime] = None) -> str:
        """new -> held (prayer time) or sent / silent / skipped. 'duplicate' if it was ever handled before."""
        now = now or datetime.now(timezone.utc)
        title, body = " ".join(title.split())[:TITLE_MAX] or "Ahmad", body.strip()[:BODY_MAX] or "—"
        row = {"user_id": self.owner_id, "kind": kind, "dedupe_key": dedupe_key[:300], "status": "new",
               "content_hash": content_hash(title, body), "counts_to_cap": bool(counts_to_cap),
               "card": {"title": title, "body": body}}
        saved = self.store.insert_once("notifications", row, ("user_id", "dedupe_key"))
        if saved is None:
            return "duplicate"
        return self._release(saved, now)

    def release_held(self, now: Optional[datetime] = None) -> List[str]:
        """Held messages whose quiet time is over go out now (oldest first)."""
        now = now or datetime.now(timezone.utc)
        held = self.store.select("notifications", {"user_id": self.owner_id, "status": "held"}, limit=50)
        out = []
        for row in held:
            until = _parse(row.get("hold_until"))
            if until is None or until <= now:
                out.append(self._release(row, now))
        return out

    def _release(self, row: Dict, now: datetime) -> str:
        quiet = self.quiet_until(now)
        if quiet is not None:
            if row.get("status") != "held" or _parse(row.get("hold_until")) != quiet:
                self.store.update_if("notifications", row["id"], {"status": row["status"]},
                                     {"status": "held", "hold_until": _iso(quiet), "reason": "prayer time"})
            log.info("notification held for prayer time kind=%s", row.get("kind"))
            return "held"
        claimed = self.store.update_if("notifications", row["id"], {"status": row["status"]}, {"status": "delivering"})
        if claimed is None:
            return "duplicate"  # another pass took it
        card = row.get("card") or {}
        title, body = str(card.get("title") or "Ahmad"), str(card.get("body") or "—")
        if self._repeat(row, now):
            self._finish(row, "skipped", now, reason="same as one shown in the last 24 hours")
            return "skipped"
        self.store.insert("cards", {"user_id": self.owner_id, "notification_id": row["id"], "kind": row["kind"],
                                    "title": title, "body": body})
        pushed, reason = self._push(row, now)
        self._finish(row, "sent" if pushed else "silent", now, pushed=pushed, reason=reason)
        log.info("notification %s kind=%s", "sent" if pushed else f"silent ({reason})", row.get("kind"))
        return "sent" if pushed else "silent"

    def _finish(self, row: Dict, status: str, now: datetime, pushed: bool = False, reason: Optional[str] = None):
        self.store.update("notifications", row["id"], {"status": status, "pushed": pushed, "reason": reason,
                                                       "delivered_at": _iso(now), "card": None if status == "skipped" else row.get("card")})

    def _recent(self) -> List[Dict]:
        return self.store.select("notifications", {"user_id": self.owner_id}, descending=True, limit=LEDGER_SCAN)

    def _repeat(self, row: Dict, now: datetime) -> bool:
        since = now - timedelta(hours=REPEAT_HOURS)
        for other in self._recent():
            if (other["id"] != row["id"] and other.get("content_hash") == row.get("content_hash")
                    and other.get("status") in ("sent", "silent")):
                when = _parse(other.get("delivered_at"))
                if when and when >= since:
                    return True
        return False

    def pushed_today(self, now: datetime) -> int:
        today = now.astimezone(self.tz).date()
        count = 0
        for other in self._recent():
            when = _parse(other.get("delivered_at"))
            if other.get("pushed") and other.get("counts_to_cap") and when and when.astimezone(self.tz).date() == today:
                count += 1
        return count

    def _push(self, row: Dict, now: datetime):
        settings = self.settings()
        if not settings["push_enabled"]:
            return False, "push is off"
        if self.sender is None:
            return False, "push is not set up on the PC"
        if row.get("counts_to_cap") and self.pushed_today(now) >= settings["daily_cap"]:
            return False, "daily cap reached"
        subscriptions = self.store.select("push_subscriptions", {"user_id": self.owner_id}, limit=5)
        if not subscriptions:
            return False, "no phone subscribed"
        pushed = False
        for sub in subscriptions:
            try:
                outcome = self.sender.send(sub, row["kind"], settings["lang"], row["id"], urgent=row["kind"] == "reminder")
            except Exception as exc:  # noqa: BLE001 (one phone's bad keys never stop the others)
                log.warning("push failed: %s", type(exc).__name__)
                outcome = None
            if outcome is not None and outcome.ok:
                pushed = True
                self.store.update("push_subscriptions", sub["id"], {"failures": 0, "last_ok_at": _iso(now)})
            elif outcome is not None and outcome.gone:
                self.store.delete("push_subscriptions", sub["id"])
                log.info("push address removed (the phone unsubscribed)")
            else:
                failures = int(sub.get("failures") or 0) + 1
                if failures >= MAX_FAILURES:
                    self.store.delete("push_subscriptions", sub["id"])
                    log.info("push address removed after %d failures", failures)
                else:
                    self.store.update("push_subscriptions", sub["id"], {"failures": failures})
                if outcome is not None:
                    log.warning("push refused (HTTP %s)", outcome.status)
        return pushed, None if pushed else "the push service did not accept it"
