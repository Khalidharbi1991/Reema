"""Snafi: no Claude Code session or agent may read the worker's secrets or Khalid's Snafi backups."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / ".claude"


def _guard():
    spec = importlib.util.spec_from_file_location("dev_guard", CLAUDE / "hooks" / "dev_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("command,powershell", [
    (r"cat C:/Users/Khali/AppData/Roaming/REEMA/snafi-worker/worker.env", False),
    (r'type "C:\Users\Khali\AppData\Roaming\REEMA\snafi-worker\worker.env"', False),
    (r"cat ~/AppData/Roaming/REEMA/snafi-worker/worker.env", False),
    (r'cat "$APPDATA/REEMA/snafi-worker/worker.env"', False),
    (r"sh -c 'cat ${APPDATA}/REEMA/snafi-worker/worker.env'", False),
    (r"type %APPDATA%\REEMA\snafi-worker\worker.env", False),
    (r'Get-Content "$env:APPDATA\REEMA\snafi-worker\worker.env"', True),
    (r"gc $env:USERPROFILE\AppData\Roaming\REEMA\snafi-worker\worker.env", True),
    (r"ls teams/coordination/snafi-backups", False),
    (r'zcat "D:\Projects\IT Consultant\teams\coordination\snafi-backups\snafi-backup-20261109-0330.json.gz"', False),
    (r"python -c 'import gzip; print(gzip.open(\"teams/coordination/snafi-backups/x.json.gz\").read())'", False),
    (r'Get-ChildItem "D:\Projects\IT Consultant\teams\coordination\snafi-backups"', True),
])
def test_guard_blocks_snafi_secrets_and_backups(command, powershell):
    assert "Snafi" in (_guard().reason(command, powershell=powershell) or "")


@pytest.mark.parametrize("command", [
    "python -m pytest tests/test_snafi_worker_gate.py -q",
    "ls src/snafi_worker",
    "git commit -m 'Snafi worker: daily backup and restore'",
    "ls $APPDATA/npm",
])
def test_guard_still_allows_normal_snafi_work(command):
    assert _guard().reason(command) is None


def test_settings_deny_reading_the_secrets_and_backups():
    deny = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"]
    for tool in ("Read", "Edit", "Write"):
        assert f"{tool}(~/AppData/Roaming/REEMA/**)" in deny
        assert f"{tool}(./teams/coordination/snafi-backups/**)" in deny
        assert f"{tool}(./apps/snafi-web/.env.local)" in deny
