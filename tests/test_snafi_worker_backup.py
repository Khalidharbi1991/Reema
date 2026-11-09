"""Snafi worker: daily backup, 30-day retention, status, restore, secrets handling and the task script."""

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.snafi_worker import backup, restore
from src.snafi_worker.config import ConfigError, Secrets, Settings
from src.snafi_worker.store.memory import MemoryStore
from src.snafi_worker.store.supabase_rest import SupabaseRestStore

OWNER = "11111111-1111-4111-8111-111111111111"
NEW_OWNER = "44444444-4444-4444-8444-444444444444"
TZ = "Asia/Riyadh"
KEY = "k" * 64
WORKER = Path(__file__).resolve().parents[1] / "src" / "snafi_worker"


def filled_store():
    store = MemoryStore()
    job = store.insert("jobs", {"user_id": OWNER, "kind": "chat.reply", "payload": {"message_id": "m"}})
    store.insert("messages", {"user_id": OWNER, "conversation_id": "c", "role": "user", "body": "It's 4 o'clock — مرحبا",
                              "job_id": job["id"]})
    store.insert("notes", {"user_id": OWNER, "body": "drawings"})
    store.insert("worker_status", {"user_id": OWNER, "worker_id": "pc", "lanes": {"chat": {"alive": True}}})
    return store


def test_backup_writes_one_dated_file_with_a_checked_manifest(tmp_path):
    now = datetime(2026, 11, 9, 0, 30, tzinfo=timezone.utc)  # 03:30 in Jeddah
    outcome = backup.run_backup(filled_store(), tmp_path, OWNER, "pc", TZ, 30, now, signing_key=KEY)
    assert outcome["ok"] and outcome["file"] == "snafi-backup-20261109-0330.json.gz"
    with gzip.open(tmp_path / outcome["file"]) as f:
        data = json.loads(f.read())
    assert set(data["tables"]) == set(backup.TABLES)
    assert data["manifest"]["tables"]["notes"]["rows"] == 1
    assert not list(tmp_path.glob("*.part"))


def test_backup_status_is_recorded_for_the_app(tmp_path):
    store = filled_store()
    backup.run_backup(store, tmp_path, OWNER, "pc", TZ, 30, signing_key=KEY)
    status = store.tables["worker_status"][0]
    assert status["last_backup_ok"] is True and status["last_backup_file"].startswith("snafi-backup-")


def test_a_failed_backup_is_recorded_without_any_data(tmp_path):
    store = filled_store()

    def broken(table, offset, limit):
        raise RuntimeError("database unreachable")
    store.page = broken
    outcome = backup.run_backup(store, tmp_path, OWNER, "pc", TZ, 30, signing_key=KEY)
    status = store.tables["worker_status"][0]
    assert not outcome["ok"] and status["last_backup_ok"] is False and "unreachable" in status["last_backup_error"]
    assert backup.backup_files(tmp_path) == []


def test_keeps_the_last_30_days_and_only_deletes_backup_files(tmp_path):
    today = datetime(2026, 11, 9).date()
    for days in range(0, 40):
        day = today - timedelta(days=days)
        (tmp_path / f"snafi-backup-{day:%Y%m%d}-0330.json.gz").write_bytes(b"x")
    (tmp_path / "README.md").write_text("keep me")
    (tmp_path / "snafi-backup-notes.txt").write_text("keep me too")
    removed = backup.prune(tmp_path, today, 30)
    left = backup.backup_files(tmp_path)
    assert len(removed) == 10 and len(left) == 30
    assert left[0].name == "snafi-backup-20261011-0330.json.gz"
    assert (tmp_path / "README.md").exists() and (tmp_path / "snafi-backup-notes.txt").exists()


def test_old_backups_are_kept_when_a_new_backup_fails(tmp_path):
    (tmp_path / "snafi-backup-20250101-0330.json.gz").write_bytes(b"x")
    store = filled_store()
    store.page = lambda *a: (_ for _ in ()).throw(RuntimeError("down"))
    backup.run_backup(store, tmp_path, OWNER, "pc", TZ, 30, signing_key=KEY)
    assert (tmp_path / "snafi-backup-20250101-0330.json.gz").exists()


@pytest.mark.parametrize("existing,now_local,due", [
    (None, "2026-11-09 01:00", True),                       # never backed up
    ("20261109-0330", "2026-11-09 12:00", False),           # done today
    ("20261108-0330", "2026-11-09 02:00", False),           # yesterday's, before today's time
    ("20261108-0330", "2026-11-09 03:31", True),            # after today's time
    ("20261107-0330", "2026-11-09 01:00", True),            # over 24 hours old
])
def test_backup_is_due_once_a_day(tmp_path, existing, now_local, due):
    from zoneinfo import ZoneInfo
    if existing:
        (tmp_path / f"snafi-backup-{existing}.json.gz").write_bytes(b"x")
    now = datetime.strptime(now_local, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(TZ))
    assert backup.is_due(tmp_path, now, TZ, "03:30") is due


def test_restore_checks_every_table_and_maps_the_owner(tmp_path):
    outcome = backup.run_backup(filled_store(), tmp_path, OWNER, "pc", TZ, 30, signing_key=KEY)
    tables = restore.map_users(restore.load(tmp_path / outcome["file"], KEY), {OWNER: NEW_OWNER})
    assert {r["user_id"] for rows in tables.values() for r in rows} == {NEW_OWNER}


def test_restore_refuses_a_changed_backup(tmp_path):
    outcome = backup.run_backup(filled_store(), tmp_path, OWNER, "pc", TZ, 30, signing_key=KEY)
    path = tmp_path / outcome["file"]
    with gzip.open(path) as f:
        data = json.loads(f.read())
    data["tables"]["notes"][0]["body"] = "tampered"
    with gzip.open(path, "wb") as f:
        f.write(json.dumps(data).encode())
    with pytest.raises(restore.RestoreError, match="notes does not match"):
        restore.load(path, KEY)


def test_restore_sql_quotes_safely_and_keeps_parents_first(tmp_path):
    outcome = backup.run_backup(filled_store(), tmp_path, OWNER, "pc", TZ, 30, signing_key=KEY)
    sql = restore.to_sql(restore.load(tmp_path / outcome["file"], KEY))
    assert "It''s 4 o''clock — مرحبا" in sql
    assert sql.index("insert into public.jobs") < sql.index("insert into public.messages")
    assert "'::jsonb" in sql and sql.strip().endswith("commit;")


def test_restore_into_a_database_refuses_unless_empty(tmp_path):
    outcome = backup.run_backup(filled_store(), tmp_path, OWNER, "pc", TZ, 30, signing_key=KEY)
    tables = restore.load(tmp_path / outcome["file"], KEY)
    target = MemoryStore()
    counts = restore.to_database(tables, target)
    assert counts["notes"] == 1 and target.tables["notes"][0]["body"] == "drawings"
    with pytest.raises(restore.RestoreError, match="already has"):
        restore.to_database(tables, target)


def test_restore_command_line(tmp_path, capsys):
    outcome = backup.run_backup(filled_store(), tmp_path, OWNER, "pc", TZ, 30, signing_key=KEY)
    out = tmp_path / "restore.sql"
    signed = Secrets({"SNAFI_BACKUP_SIGNING_KEY": KEY})
    assert restore.main([str(tmp_path / outcome["file"]), "--to-sql", str(out), "--map-user", f"{OWNER}={NEW_OWNER}"],
                        secrets=signed) == 0
    assert NEW_OWNER in out.read_text(encoding="utf-8") and OWNER not in out.read_text(encoding="utf-8")
    assert restore.main([str(tmp_path / "missing.json.gz"), "--verify"], secrets=signed) == 1


# ---------- secrets and settings ----------
def test_secrets_never_show_their_values():
    secrets = Secrets({"SNAFI_SUPABASE_SECRET_KEY": "sb_secret_abcdefghijklmnop", "GEMINI_API_KEY": "g-secret-123"})
    assert secrets.get("GEMINI_API_KEY") == "g-secret-123"
    for shown in (repr(secrets), str(secrets)):
        assert "sb_secret_abc" not in shown and "g-secret" not in shown
    with pytest.raises(ConfigError, match="set_secrets"):
        Secrets({}).get("GEMINI_API_KEY")


def test_logs_folder_is_outside_the_repo(monkeypatch):
    from src.snafi_worker.config import worker_data_dir
    monkeypatch.setenv("APPDATA", r"C:\Users\x\AppData\Roaming")
    assert worker_data_dir().parts[-2:] == ("REEMA", "snafi-worker")
    assert Path(__file__).resolve().parents[1] not in worker_data_dir().parents


def test_settings_point_backups_at_the_ignored_team_folder():
    s = Settings.load()
    assert s.backup_folder.as_posix().endswith("teams/coordination/snafi-backups")
    assert s.backup_keep_days == 30 and s.backup_time == "03:30" and s.time_zone == "Asia/Riyadh"
    assert s.lanes["chat"].timeout_seconds == 90 and s.lanes["chat"].retry_delay_seconds == 5
    assert s.lanes["background"].timeout_seconds == 600 and s.heartbeat_seconds == 15


def test_store_refuses_the_publishable_key_and_plain_http():
    with pytest.raises(Exception, match="secret key"):
        SupabaseRestStore({}, Secrets({"SNAFI_SUPABASE_URL": "https://x.supabase.co",
                                       "SNAFI_SUPABASE_SECRET_KEY": "sb_publishable_x"}))
    with pytest.raises(Exception, match="https"):
        SupabaseRestStore({}, Secrets({"SNAFI_SUPABASE_URL": "http://x.supabase.co",
                                       "SNAFI_SUPABASE_SECRET_KEY": "sb_secret_x"}))


def test_store_sends_the_key_only_in_headers():
    calls = []

    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body))
        return 200, b"[]"
    store = SupabaseRestStore({}, Secrets({"SNAFI_SUPABASE_URL": "https://x.supabase.co",
                                           "SNAFI_SUPABASE_SECRET_KEY": "sb_secret_abc123"}), transport)
    store.select("notes", {"user_id": OWNER}, null=("deleted_at",))
    method, url, headers, _ = calls[0]
    assert headers["apikey"] == "sb_secret_abc123" and "Authorization" not in headers
    assert "sb_secret" not in url and f"user_id=eq.{OWNER}" in url and "deleted_at=is.null" in url
    assert "abc123" not in repr(store)
    with pytest.raises(Exception, match="invalid name"):
        store.select("notes; drop table x")


def test_task_script_runs_hidden_at_logon_without_elevation():
    script = (WORKER / "install_task.ps1").read_text(encoding="utf-8")
    for needed in ("-AtLogOn", "pythonw.exe", "-m src.snafi_worker", "-RunLevel Limited", "-LogonType Interactive",
                   "-RestartCount 999", "-MultipleInstances IgnoreNew"):
        assert needed in script
    assert "-RunLevel Highest" not in script and "Password" not in script
