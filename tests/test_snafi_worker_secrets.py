"""SEC-14 and SEC-17: secrets in Windows Credential Manager, the one-time setup script,
and signed, neutralised restores."""

import gzip
import json
import sys
import uuid

import pytest

from src.snafi_worker import backup, restore
from src.snafi_worker.config import ConfigError, Secrets
from src.snafi_worker.secret_store import NAMES, MemoryCredentials, WindowsCredentials, load_all
from src.snafi_worker.set_secrets import check_gemini, check_owner, check_secret_key, check_url, run
from src.snafi_worker.store.memory import MemoryStore

OWNER = "11111111-1111-4111-8111-111111111111"
KEY = "k" * 64


# ---------- the store ----------
def test_secrets_load_from_the_credential_store_without_showing_values():
    creds = MemoryCredentials({"GEMINI_API_KEY": "AIzaFAKEFAKEFAKEFAKEFAKE", "SNAFI_OWNER_USER_ID": OWNER})
    secrets = Secrets.load(creds)
    assert secrets.get("GEMINI_API_KEY").startswith("AIza")
    assert "AIza" not in repr(secrets) and secrets.names() == ["GEMINI_API_KEY", "SNAFI_OWNER_USER_ID"]


def test_there_is_no_plain_text_secrets_file_any_more():
    from src.snafi_worker import config
    assert not hasattr(config, "default_env_path")
    source = "".join(p.read_text(encoding="utf-8") for p in (config.HERE).rglob("*.py"))
    assert "worker.env" not in source


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Credential Manager")
def test_windows_credential_manager_round_trip_with_a_test_only_name():
    store = WindowsCredentials(prefix=f"REEMA-Snafi-TEST-{uuid.uuid4().hex}:")
    try:
        assert store.read("GEMINI_API_KEY") is None
        store.write("GEMINI_API_KEY", "test-value-مرحبا")
        assert store.read("GEMINI_API_KEY") == "test-value-مرحبا"
        assert load_all(store) == {"GEMINI_API_KEY": "test-value-مرحبا"}
    finally:
        store.delete("GEMINI_API_KEY")
    assert store.read("GEMINI_API_KEY") is None


# ---------- the one-time setup script ----------
def answers(*values):
    queue = list(values)
    return lambda prompt="": queue.pop(0)


def test_setup_stores_each_value_hidden_and_never_prints_keys():
    creds, printed, hidden_prompts = MemoryCredentials(), [], []
    secret = "sb_secret_" + "x" * 30
    gemini = "AIza" + "y" * 35

    def hidden(prompt):
        hidden_prompts.append(prompt)
        return {0: secret, 1: gemini}[len(hidden_prompts) - 1]
    code = run(creds, prompt=hidden, plain=answers("https://abcd.supabase.co/", OWNER.upper()), out=printed.append,
               brain_provider="gemini_api")
    assert code == 0
    assert creds.values["SNAFI_SUPABASE_URL"] == "https://abcd.supabase.co"
    assert creds.values["SNAFI_SUPABASE_SECRET_KEY"] == secret and creds.values["GEMINI_API_KEY"] == gemini
    assert creds.values["SNAFI_OWNER_USER_ID"] == OWNER
    assert len(creds.values["SNAFI_BACKUP_SIGNING_KEY"]) == 64
    assert len(hidden_prompts) == 2 and all("key" in p.lower() for p in hidden_prompts)
    everything = "\n".join(printed)
    assert secret not in everything and gemini not in everything and creds.values["SNAFI_BACKUP_SIGNING_KEY"] not in everything


def test_setup_keeps_stored_values_on_enter_and_keeps_the_signing_key():
    creds = MemoryCredentials({n: "old" for n in NAMES})
    assert run(creds, prompt=answers("", ""), plain=answers("", ""), out=lambda *_: None, brain_provider="gemini_api") == 0
    assert all(creds.values[n] == "old" for n in NAMES)


def test_setup_refuses_the_publishable_key_and_bad_values():
    with pytest.raises(ValueError, match="publishable"):
        check_secret_key("sb_publishable_abc")
    with pytest.raises(ValueError):
        check_secret_key("hello")
    with pytest.raises(ValueError):
        check_url("http://abcd.supabase.co")
    with pytest.raises(ValueError):
        check_url("https://abcd.supabase.co/rest/v1")
    with pytest.raises(ValueError):
        check_owner("me")
    with pytest.raises(ValueError, match="space"):
        check_gemini("has spaces in it but is long")
    creds, printed = MemoryCredentials(), []
    run(creds, prompt=answers("sb_publishable_x", "sb_publishable_x", "sb_publishable_x", "AIza" + "y" * 35),
        plain=answers("https://a.supabase.co", OWNER), out=printed.append, brain_provider="gemini_api")
    assert "SNAFI_SUPABASE_SECRET_KEY" not in creds.values and printed[-1].startswith("Some values were not stored")


def test_missing_values_stop_the_worker_with_the_setup_command():
    with pytest.raises(ConfigError, match="snafi.cmd set-secrets"):
        Secrets.load(MemoryCredentials()).get("SNAFI_SUPABASE_SECRET_KEY")


# ---------- SEC-17: signed, neutralised restores ----------
def live_store():
    store = MemoryStore()
    job = store.insert("jobs", {"user_id": OWNER, "kind": "approval.resume", "status": "queued", "payload": {}})
    store.insert("approvals", {"user_id": OWNER, "conversation_id": "c", "tool": "send_test_message",
                               "args": {"text": "x"}, "summary": "x", "status": "approved", "job_id": job["id"]})
    store.insert("action_log", {"user_id": OWNER, "tool": "add_note", "level": 2, "summary": "s", "status": "done",
                                "undoable": True, "undo_requested_at": "2026-11-09T00:00:00+00:00"})
    return store


def test_restore_refuses_an_unsigned_or_wrongly_signed_backup(tmp_path):
    out = backup.run_backup(live_store(), tmp_path, OWNER, "pc", "Asia/Riyadh", 30, signing_key=KEY)
    path = tmp_path / out["file"]
    with pytest.raises(restore.RestoreError, match="signature does not match"):
        restore.load(path, "another-key")
    with pytest.raises(restore.RestoreError, match="no signing key"):
        restore.load(path, None)
    assert restore.load(path, None, accept_unsigned=True)


def test_a_planted_backup_with_recomputed_checksums_is_refused(tmp_path):
    out = backup.run_backup(live_store(), tmp_path, OWNER, "pc", "Asia/Riyadh", 30, signing_key=KEY)
    path = tmp_path / out["file"]
    with gzip.open(path) as f:
        data = json.loads(f.read())
    data["tables"]["approvals"][0]["args"] = {"text": "planted"}
    data["manifest"]["tables"]["approvals"]["sha256"] = backup.digest(data["tables"]["approvals"])
    with gzip.open(path, "wb") as f:
        f.write(json.dumps(data).encode())
    with pytest.raises(restore.RestoreError, match="signature"):
        restore.load(path, KEY)


def test_nothing_restored_can_act_by_itself(tmp_path):
    out = backup.run_backup(live_store(), tmp_path, OWNER, "pc", "Asia/Riyadh", 30, signing_key=KEY)
    target = MemoryStore()
    restore.to_database(restore.load(tmp_path / out["file"], KEY), target)
    assert target.tables["jobs"][0]["status"] == "cancelled"
    assert target.tables["approvals"][0]["status"] == "expired"
    assert target.tables["action_log"][0]["undo_requested_at"] is None
    sql = restore.to_sql(restore.load(tmp_path / out["file"], KEY))
    assert "'queued'" not in sql and "'approved'" not in sql and "'cancelled'" in sql


def test_backups_need_a_signing_key_and_at_least_one_day(tmp_path):
    assert backup.run_backup(MemoryStore(), tmp_path, OWNER, "pc", "Asia/Riyadh", 30, signing_key="")["ok"] is False
    with pytest.raises(ValueError):
        backup.run_backup(MemoryStore(), tmp_path, OWNER, "pc", "Asia/Riyadh", 0, signing_key=KEY)


def test_with_the_agy_brain_no_gemini_key_is_ever_asked_for():
    creds, hidden_prompts = MemoryCredentials(), []

    def hidden(prompt):
        hidden_prompts.append(prompt)
        return "sb_secret_" + "x" * 30
    assert run(creds, prompt=hidden, plain=answers("https://abcd.supabase.co", OWNER), out=lambda *_: None,
               brain_provider="agy") == 0
    assert len(hidden_prompts) == 1 and "Supabase" in hidden_prompts[0]
    assert "GEMINI_API_KEY" not in creds.values


@pytest.mark.parametrize("key", ["AIza" + "y" * 35, "AQ.Ab8RN6" + "x" * 40, "  AIza" + "Z9_-" * 9 + "  "])
def test_any_printable_gemini_key_format_is_accepted(key):
    assert check_gemini(key) == key.strip()


@pytest.mark.parametrize("bad,why", [("\x16", "control character"), ("AIza" + "y" * 35 + "\x16", "control character"),
                                     ("AIza" + "y" * 20 + " " + "y" * 14, "space"), ("AIza" + "y" * 30 + "é", "non-English"),
                                     ("short", "characters long"), ("", "characters long"),
                                     ("y" * 600, "20 to 512"),
                                     ("sb_secret_" + "y" * 30, "Supabase"), ("sb_publishable_" + "y" * 30, "Supabase"),
                                     ("https://abcd.supabase.co", "Supabase"),
                                     ("eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.yyyy", "Supabase")])
def test_a_broken_paste_or_a_wrong_value_is_refused_without_showing_it(bad, why):
    with pytest.raises(ValueError, match=why) as caught:
        check_gemini(bad)
    assert "yyyy" not in str(caught.value)


@pytest.mark.parametrize("payload", ["MTIz", "WzFd", "InMi"])  # 123, [1], "s": JSON that is not an object
def test_a_key_whose_middle_part_decodes_to_non_object_json_does_not_crash(payload):
    key = "AQ" + "x" * 20 + "." + payload + "." + "y" * 10
    assert check_gemini(key) == key
