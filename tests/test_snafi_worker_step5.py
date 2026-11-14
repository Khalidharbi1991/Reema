"""Snafi step 5: Proactive Ahmad. The scheduler, Web Push, and the manners enforced in code.

Offline: the memory store, fake mail/calendar/tasks, a fake push service. No network, no brain call.
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from src.snafi_worker import restore
from src.snafi_worker.clock import clock, day_clock, hhmm_to_clock
from src.snafi_worker.config import Secrets, Settings
from src.snafi_worker.engine import Engine
from src.snafi_worker.personal.fake import FakeCalendar, FakeMail, FakeTasks
from src.snafi_worker.proactive import webpush
from src.snafi_worker.proactive.notify import Notifier
from src.snafi_worker.proactive.prayer import RAMADAN, in_ramadan, prayer_times, quiet_until
from src.snafi_worker.proactive.scheduler import Scheduler
from src.snafi_worker.services import Personal
from src.snafi_worker.store.memory import MemoryStore
from src.snafi_worker.store.supabase_rest import SupabaseRestStore

OWNER = "11111111-1111-4111-8111-111111111111"
TZ = ZoneInfo("Asia/Riyadh")
LAT, LON = 21.4858, 39.1925
FIXTURE = Path(__file__).parent / "fixtures" / "snafi_prayer_times.json"
UA_PRIVATE = "q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94"   # RFC 8291 Appendix A
UA_AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
APPLE = "https://web.push.apple.com/QGuQyavXutnMH6mIqdJu8g"


def local(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=TZ).astimezone(timezone.utc)


def ua_key():
    return ec.derive_private_key(int.from_bytes(webpush.unb64u(UA_PRIVATE), "big"), ec.SECP256R1())


class FakeSender:
    def __init__(self, status=201):
        self.sent, self.status = [], status

    def send(self, sub, kind, lang, notification_id, urgent=False):
        self.sent.append({"endpoint": sub["endpoint"], "kind": kind, "lang": lang, "id": notification_id, "urgent": urgent})
        return webpush.Outcome(self.status in (200, 201), gone=self.status in (404, 410), status=self.status)


def setup(push=True, cap=10, lang="en", brief="07:00", sender=None, subs=1):
    store = MemoryStore()
    store.insert("user_settings", {"user_id": OWNER, "push_enabled": push, "brief_time": brief, "daily_cap": cap,
                                   "lang": lang})
    for i in range(subs):
        store.insert("push_subscriptions", {"user_id": OWNER, "endpoint": f"{APPLE}{i}", "p256dh": "x" * 87,
                                            "auth": "y" * 22})
    sender = sender if sender is not None else FakeSender()
    notifier = Notifier(store, OWNER, sender)
    return store, notifier, sender


def quiet_free(day=date(2026, 11, 15), hour=10):
    """A time on `day` that is not within 20 minutes after any adhan."""
    when = local(day.year, day.month, day.day, hour)
    assert quiet_until(when, LAT, LON, TZ, 20) is None
    return when


# ---------- prayer times: the worker and the app agree ----------
def test_prayer_times_match_the_apps_adhan_on_every_fixture_day():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["city"]["latitude"] == LAT and data["city"]["longitude"] == LON
    assert len(data["days"]) > 500
    for day, expected in data["days"].items():
        got = prayer_times(date.fromisoformat(day), LAT, LON)
        for prayer, iso in expected.items():
            assert got[prayer] == datetime.fromisoformat(iso.replace("Z", "+00:00")), (day, prayer)


def test_isha_is_120_minutes_after_maghrib_in_ramadan_and_90_otherwise():
    first, _ = RAMADAN[1]
    ramadan = prayer_times(date.fromisoformat(first), LAT, LON)
    before = prayer_times(date.fromisoformat(first) - timedelta(days=1), LAT, LON)
    assert ramadan["isha"] - ramadan["maghrib"] == timedelta(minutes=120)
    assert before["isha"] - before["maghrib"] == timedelta(minutes=90)
    assert in_ramadan(date(2027, 2, 20)) and not in_ramadan(date(2027, 3, 9))


def test_quiet_for_20_minutes_after_each_adhan_only():
    dhuhr = prayer_times(date(2026, 11, 15), LAT, LON)["dhuhr"]
    assert quiet_until(dhuhr, LAT, LON, TZ, 20) == dhuhr + timedelta(minutes=20)
    assert quiet_until(dhuhr + timedelta(minutes=19), LAT, LON, TZ, 20) == dhuhr + timedelta(minutes=20)
    assert quiet_until(dhuhr + timedelta(minutes=20), LAT, LON, TZ, 20) is None
    assert quiet_until(dhuhr - timedelta(minutes=1), LAT, LON, TZ, 20) is None


# ---------- 12-hour times ----------
@pytest.mark.parametrize("h, m, en, ar", [(0, 5, "12:05 AM", "12:05 ص"), (7, 0, "7:00 AM", "7:00 ص"),
                                          (12, 0, "12:00 PM", "12:00 م"), (23, 59, "11:59 PM", "11:59 م")])
def test_times_are_12_hour_with_am_pm_in_both_languages(h, m, en, ar):
    when = datetime(2026, 11, 15, h, m, tzinfo=TZ)
    assert clock(when, "en") == en and clock(when, "ar") == ar
    assert hhmm_to_clock(f"{h:02d}:{m:02d}", "en") == en
    assert day_clock(when, "en").startswith("Sun 15 Nov") and day_clock(when, "ar").startswith("الأحد 15 نوفمبر")


def test_chat_tool_results_show_12_hour_times():
    from src.snafi_worker.personal_tools import _local_time
    assert _local_time("2026-11-20T15:30:00+03:00", TZ, "en") == "3:30 PM"
    assert _local_time("2026-11-20T15:30:00+03:00", TZ, "ar") == "3:30 م"
    from src.snafi_worker.prompt import system_prompt
    text = system_prompt("en", local(2026, 11, 15, 15, 5))
    assert "3:05 PM in Jeddah" in text and "12-hour clock" in text


# ---------- Web Push ----------
def test_encryption_matches_the_rfc_8291_example():
    server = ec.derive_private_key(int.from_bytes(webpush.unb64u("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"),
                                   ec.SECP256R1())
    body = webpush.encrypt(b"When I grow up, I want to be a watermelon", webpush.public_key_b64(ua_key()), UA_AUTH,
                           webpush.unb64u("DGv6ra1nlYgDCS1FRnbzlw"), server)
    assert webpush.b64u(body) == (
        "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PB"
        "ru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")


@pytest.mark.parametrize("endpoint, ok", [
    (APPLE, True),
    ("https://fcm.googleapis.com/fcm/send/abc:def", True),
    ("https://updates.push.services.mozilla.com/wpush/v2/gAAAA", True),
    ("https://wns2-par02p.notify.windows.com/w/?token=BQYAAA", True),
    ("http://fcm.googleapis.com/fcm/send/abc", False),
    ("https://fcm.googleapis.com.evil.example/fcm/send/abc", False),
    ("https://evil.example/fcm.googleapis.com/abc", False),
    ("https://user@fcm.googleapis.com/fcm/send/abc", False),
    ("https://fcm.googleapis.com:8443/fcm/send/abc", False),
    ("https://169.254.169.254/latest/meta-data", False),
    ("https://localhost/push/abc12345678", False),
    ("https://web.push.apple.com/abc\nHost: x", False),
])
def test_only_the_four_browser_push_services_are_ever_posted_to(endpoint, ok):
    assert webpush.endpoint_ok(endpoint) is ok
    posted = []
    sender = webpush.PushSender(webpush.new_private_key(), "https://snafi.example.com",
                                post=lambda *a: posted.append(a) or 201)
    outcome = sender.send({"endpoint": endpoint, "p256dh": webpush.public_key_b64(ua_key()), "auth": UA_AUTH},
                          "reminder", "en", "33333333-3333-4333-8333-333333333333")
    assert bool(posted) is ok and outcome.ok is ok


def test_the_push_carries_no_private_text_and_a_valid_vapid_signature():
    captured = {}
    sender = webpush.PushSender(webpush.new_private_key(), "https://snafi.example.com",
                                post=lambda url, headers, body, timeout: captured.update(h=headers, b=body) or 201)
    sub = {"endpoint": APPLE, "p256dh": webpush.public_key_b64(ua_key()), "auth": UA_AUTH}
    assert sender.send(sub, "mail", "ar", "33333333-3333-4333-8333-333333333333").ok
    plain = json.loads(webpush.decrypt_for_tests(captured["b"], ua_key(), UA_AUTH))
    assert plain == {"k": "mail", "l": "ar", "n": "33333333-3333-4333-8333-333333333333"}
    auth = captured["h"]["Authorization"]
    token, key = auth[len("vapid t="):].split(", k=")
    head, claims, sig = token.split(".")
    assert json.loads(webpush.unb64u(claims)) | {"exp": 0} == {"aud": "https://web.push.apple.com", "exp": 0,
                                                               "sub": "https://snafi.example.com"}
    raw = webpush.unb64u(sig)
    public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), webpush.unb64u(key))
    public.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")),
                  f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))
    assert key == sender.public_key


def test_payload_refuses_anything_but_kind_language_and_id():
    with pytest.raises(webpush.PushError):
        webpush.payload("Meeting with the bank at 3 PM", "en", "33333333-3333-4333-8333-333333333333")
    with pytest.raises(webpush.PushError):
        webpush.payload("mail", "en", "not an id")
    with pytest.raises(webpush.PushError):
        webpush.PushSender(webpush.new_private_key(), "http://snafi.example.com")


def test_redirects_are_never_followed():
    handler = [h for h in webpush._OPENER.handlers if isinstance(h, webpush._NoRedirect)]
    assert handler and handler[0].redirect_request() is None


# ---------- the notifier: manners in code ----------
def test_never_twice_for_the_same_key():
    store, notifier, sender = setup()
    now = quiet_free()
    assert notifier.deliver("mail", "mail:gmail:1", "Gmail · Sara", "Contract", now=now) == "sent"
    assert notifier.deliver("mail", "mail:gmail:1", "Gmail · Sara", "Contract", now=now) == "duplicate"
    assert len(store.tables["cards"]) == 1 and len(sender.sent) == 1


def test_same_text_is_not_repeated_within_a_day():
    store, notifier, sender = setup()
    now = quiet_free()
    notifier.deliver("brief", "brief:a", "Good morning", "Same body", now=now)
    assert notifier.deliver("brief", "brief:b", "Good morning", "Same body", now=now + timedelta(hours=1)) == "skipped"
    assert len(store.tables["cards"]) == 1


def test_held_during_prayer_quiet_time_then_sent_after():
    store, notifier, sender = setup()
    dhuhr = prayer_times(date(2026, 11, 15), LAT, LON)["dhuhr"]
    assert notifier.deliver("mail", "mail:gmail:2", "Gmail · Sara", "Contract", now=dhuhr + timedelta(minutes=3)) == "held"
    assert store.tables["cards"] == [] and sender.sent == []
    assert notifier.release_held(dhuhr + timedelta(minutes=10)) == []         # still quiet
    assert notifier.release_held(dhuhr + timedelta(minutes=20)) == ["sent"]
    assert len(store.tables["cards"]) == 1 and len(sender.sent) == 1
    assert notifier.release_held(dhuhr + timedelta(minutes=30)) == []         # never again


def test_daily_cap_silences_pushes_but_cards_still_appear_and_reminders_do_not_count():
    store, notifier, sender = setup(cap=2)
    now = quiet_free()
    results = [notifier.deliver("mail", f"mail:gmail:{i}", f"Gmail · {i}", f"Subject {i}", now=now) for i in range(4)]
    assert results == ["sent", "sent", "silent", "silent"]
    assert len(store.tables["cards"]) == 4 and len(sender.sent) == 2
    assert notifier.deliver("reminder", "reminder:x", "Reminder", "Call mum", counts_to_cap=False, now=now) == "sent"
    # the next Jeddah day starts a new count
    assert notifier.deliver("mail", "mail:gmail:9", "Gmail · 9", "Subject 9", now=now + timedelta(days=1)) == "sent"


def test_push_off_or_no_phone_means_a_silent_card():
    store, notifier, sender = setup(push=False)
    assert notifier.deliver("mail", "mail:gmail:3", "Gmail · Sara", "Hi", now=quiet_free()) == "silent"
    assert sender.sent == [] and len(store.tables["cards"]) == 1
    store, notifier, sender = setup(subs=0)
    assert notifier.deliver("mail", "mail:gmail:3", "Gmail · Sara", "Hi", now=quiet_free()) == "silent"


def test_an_unsubscribed_phone_is_removed():
    store, notifier, _ = setup(sender=FakeSender(status=410))
    notifier.deliver("mail", "mail:gmail:4", "Gmail · Sara", "Hi", now=quiet_free())
    assert store.tables["push_subscriptions"] == []


# ---------- the scheduler ----------
def personal():
    return Personal(mail=FakeMail(), calendar=FakeCalendar(), yahoo=FakeMail(prefix="y"), tasks=FakeTasks())


def test_a_reminder_fires_once_at_its_time_and_never_before():
    store, notifier, sender = setup()
    sched = Scheduler(notifier, personal())
    due = quiet_free()
    rid = store.insert("reminders", {"user_id": OWNER, "body": "Call the bank", "due_at": due.isoformat()})["id"]
    gone = store.insert("reminders", {"user_id": OWNER, "body": "Deleted", "due_at": due.isoformat(),
                                      "deleted_at": due.isoformat()})["id"]
    assert sched.reminders(due - timedelta(minutes=1)) == []
    assert sched.reminders(due) == ["sent"]
    assert sched.reminders(due + timedelta(minutes=1)) == []
    card = store.tables["cards"][0]
    assert card["kind"] == "reminder" and "Call the bank" in card["body"] and "Set for 10:00 AM" in card["body"]
    assert sender.sent[0]["urgent"] is True
    assert [r for r in store.tables["reminders"] if r["id"] == rid][0]["fired_at"]
    assert not [r for r in store.tables["reminders"] if r["id"] == gone][0]["fired_at"]


def test_morning_brief_once_at_the_chosen_time_with_12_hour_times():
    store, notifier, sender = setup()
    p = personal()
    p.calendar.add("Board meeting", "2026-11-15T09:30:00+03:00", "2026-11-15T10:30:00+03:00", "Office")
    p.tasks.put("Pay the electricity bill", priority=1)
    p.mail.add("Sara <sara@example.com>", "Contract", "body text never shown", important=True)
    sched = Scheduler(notifier, p)
    assert sched.brief(local(2026, 11, 15, 6, 59)) is None
    assert sched.brief(local(2026, 11, 15, 7, 0)) == "sent"
    assert sched.brief(local(2026, 11, 15, 7, 30)) is None
    card = store.tables["cards"][0]
    assert card["title"] == "Good morning · Sun 15 Nov"
    assert "9:30 AM Board meeting · Office" in card["body"] and "Pay the electricity bill" in card["body"]
    assert "[Gmail] Sara: Contract" in card["body"] and "body text never shown" not in card["body"]
    assert "Fajr " in card["body"] and " AM" in card["body"] and " PM" in card["body"]
    assert ":" in card["body"] and not any(f" {h}:" in card["body"] for h in range(13, 24))


def test_brief_in_arabic_uses_sad_and_mim():
    store, notifier, _ = setup(lang="ar")
    sched = Scheduler(notifier, Personal())
    assert sched.brief(local(2026, 11, 15, 7, 0)) == "sent"
    body = store.tables["cards"][0]["body"]
    assert "الفجر" in body and " ص" in body and " م" in body and "AM" not in body


def test_brief_comes_later_if_the_pc_was_off_but_not_after_the_window():
    store, notifier, _ = setup(brief="07:00")
    assert Scheduler(notifier, Personal()).brief(local(2026, 11, 15, 12, 1)) is None
    assert Scheduler(notifier, Personal()).brief(local(2026, 11, 15, 9, 0)) == "sent"


def test_mail_watch_first_run_only_learns_then_tells_about_new_important_mail():
    store, notifier, sender = setup()
    p = personal()
    p.mail.add("Old <old@example.com>", "Already there", "", important=True)
    sched = Scheduler(notifier, p)
    now = quiet_free()
    first = sched.mail_watch(now)
    assert first["gmail"] == "learned 1" and store.tables["cards"] == [] and sender.sent == []
    assert sched.mail_watch(now + timedelta(minutes=5)) is None             # every 10 minutes only
    p.mail.add("Sara <sara@example.com>", "Contract signed", "", important=True)
    p.mail.add("News <news@example.com>", "Newsletter", "", important=False)
    mid = p.mail.add("Promo <p@example.com>", "Not primary", "", important=True)
    p.mail.flags[mid]["watch"] = False
    second = sched.mail_watch(now + timedelta(minutes=10))
    assert second["gmail"] == ["sent"]
    assert [c["title"] for c in store.tables["cards"]] == ["Gmail · Sara"]
    assert sched.mail_watch(now + timedelta(minutes=20))["gmail"] == []      # never twice


def test_gmail_watch_asks_for_important_primary_unread_inbox_mail():
    from src.snafi_worker.google.gmail import GmailMail as Gmail
    calls = []

    class Api:
        def call(self, method, url, params=None, body=None):
            calls.append(params)
            return {}
    g = Gmail.__new__(Gmail)
    g.api = Api()
    assert g.watch_unread(24, 10) == []
    assert calls[0]["q"] == "is:unread in:inbox is:important category:primary newer_than:1d"


def test_yahoo_watch_only_from_people_khalid_emailed():
    from src.snafi_worker.personal.base import MailSummary
    from src.snafi_worker.yahoo.mail import YahooMail
    y = YahooMail.__new__(YahooMail)
    y.important_unread = lambda hours, limit: [
        MailSummary("y1_1", "y1_1", "Sara <SARA@example.com>", "Hi", "", "", True, False),
        MailSummary("y1_2", "y1_2", "Stranger <s@example.com>", "Hi", "", "", True, False)]
    y.known_correspondents = lambda: {"sara@example.com"}
    assert [m.id for m in y.watch_unread(24, 10)] == ["y1_1"]


def test_one_failing_job_never_stops_the_others():
    store, notifier, _ = setup()

    class Broken:
        def watch_unread(self, hours, limit):
            raise RuntimeError("down")
    sched = Scheduler(notifier, Personal(mail=Broken()))
    due = quiet_free()
    store.insert("reminders", {"user_id": OWNER, "body": "Still fires", "due_at": due.isoformat()})
    out = sched.tick(due)
    assert out["reminders"] == ["sent"] and out["mail"] == {"gmail": "error"}


# ---------- the Settings test push, wiring, backup ----------
def test_test_push_job_runs_for_the_owner_only():
    store, notifier, sender = setup()
    engine = Engine(store, brain=None)
    engine.scheduler = Scheduler(notifier, Personal())
    job = store.insert("jobs", {"user_id": OWNER, "kind": "push.test", "lane": "background"})
    result = engine.handle(job)
    assert result["outcome"] in ("sent", "held")
    other = store.insert("jobs", {"user_id": "22222222-2222-4222-8222-222222222222", "kind": "push.test"})
    with pytest.raises(Exception, match="only for Snafi's owner"):
        engine.handle(other)


def test_restore_never_sends_what_was_waiting():
    tables = {"notifications": [{"id": "a", "status": "held"}, {"id": "b", "status": "sent"}]}
    out = restore.neutralise(tables)
    assert [n["status"] for n in out["notifications"]] == ["cancelled", "sent"]
    assert {"notifications", "cards", "user_settings"} <= set(restore.ORDER)


def test_worker_yaml_has_the_scheduler_settings():
    s = Settings.load()
    assert s.mail_watch_minutes == 10 and s.quiet_minutes == 20 and (s.latitude, s.longitude) == (LAT, LON)
    with pytest.raises(Exception):
        Settings.load(overrides={"proactive.quiet_minutes": 600})


def test_supabase_insert_once_and_null_checks():
    calls = []

    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers.get("Prefer")))
        return 201, b"[]"
    store = SupabaseRestStore({}, Secrets({"SNAFI_SUPABASE_URL": "https://abcd.supabase.co",
                                           "SNAFI_SUPABASE_SECRET_KEY": "sb_secret_x"}), transport)
    assert store.insert_once("notifications", {"dedupe_key": "k"}, ("user_id", "dedupe_key")) is None
    assert "on_conflict=user_id%2Cdedupe_key" in calls[0][1] or "on_conflict=user_id,dedupe_key" in calls[0][1]
    assert calls[0][2] == "resolution=ignore-duplicates,return=representation"
    store.update_if("reminders", "r1", {"fired_at": None}, {"fired_at": "now"})
    assert "fired_at=is.null" in calls[1][1]


def test_set_secrets_makes_the_push_key_and_prints_only_the_public_half():
    from src.snafi_worker.secret_store import MemoryCredentials
    from src.snafi_worker import set_secrets
    creds = MemoryCredentials()
    lines = []
    assert set_secrets.make_push_key(creds) is True
    assert set_secrets.make_push_key(creds) is False
    private = creds.read("SNAFI_VAPID_PRIVATE_KEY")
    assert set_secrets.print_push_public_key(creds, lines.append)
    assert private not in "\n".join(lines)
    assert webpush.public_key_b64(webpush.load_private_key(private)) in lines[-1]
    assert set_secrets.check_push_contact("https://snafi.vercel.app/") == "https://snafi.vercel.app"
    for bad in ("http://snafi.vercel.app", "https://snafi.vercel.app/x", "https://localhost", "https://a.supabase.co"):
        with pytest.raises(ValueError):
            set_secrets.check_push_contact(bad)
