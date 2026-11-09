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
    # SEC-14: the tricky paths Agent 16 found, and Credential Manager
    (r"Get-Content (Join-Path $env:APPDATA 'REEMA\snafi-worker\logs\worker.log')", True),
    (r'Select-String -Path "$env:APPDATA\*\*\*.log" -Pattern key', True),
    (r"ls teams/coordination/snafi-back*", False),
    (r"ls teams/coordination/*", False),
    (r"dir teams\coordination\snafi?backups", False),
    (r"cd teams/coordination && ls snafi*", False),
    (r"cmdkey /list", False),
    (r"vaultcmd /listcreds:\"Windows Credentials\"", True),
    (r"[Windows.Security.Credentials.PasswordVault,Windows.Security.Credentials,ContentType=WindowsRuntime]", True),
    (r"Get-StoredCredential -Target 'REEMA-Snafi:GEMINI_API_KEY'", True),
    (r"python -c \"import keyring; print(keyring.get_password('x','y'))\"", False),
    (r"python -c \"import ctypes; ctypes.windll.advapi32.CredReadW\"", False),
    (r"python -c \"from src.snafi_worker.secret_store import WindowsCredentials as W; print(W().read('GEMINI_API_KEY'))\"", False),
    (r"python -m src.snafi_worker --once", False),
    (r".venv\Scripts\python.exe -m src.snafi_worker.restore x --verify", False),
    (r"python -m src.snafi_worker.set_secrets --status", False),
    (r"powershell -File src\snafi_worker\install_task.ps1", True),
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
    assert "Read(**/snafi-backups/**)" in deny and "Read(**/snafi-backup-*)" in deny
