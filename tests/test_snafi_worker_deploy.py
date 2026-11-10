"""Snafi worker under its own Windows user: the deploy script, the scheduled task, the
launcher, and the guard around them. The scripts are checked as text; they are run by Khalid."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "src" / "snafi_worker" / "deploy"


def _guard():
    spec = importlib.util.spec_from_file_location("dev_guard", ROOT / ".claude" / "hooks" / "dev_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def text(name):
    return (DEPLOY / name).read_text(encoding="utf-8")


def test_deploy_copies_only_the_worker_and_installs_exactly_the_approved_packages():
    s = text("deploy.ps1")
    assert "robocopy $source" in s and "/XD __pycache__ deploy" in s
    assert s.count("pip install") == 1 and 'if ($version -ne "3.12.10")' in s
    assert "--require-hashes --only-binary=:all: --no-deps" in s
    req = text("requirements-worker.txt")
    assert "pyyaml==6.0.3" in req and "tzdata==2026.6" in req and req.count("--hash=sha256:") == 2
    assert 'C:\\Program Files\\Python312\\python.exe' in s


def test_deploy_runs_no_repo_code_as_admin_and_locks_before_copying():
    s = text("deploy.ps1")
    code = [l for l in s.split("$ErrorActionPreference")[1].splitlines() if not l.strip().startswith(("throw", "#"))]
    assert not [l for l in code if ".venv" in l or "$repoPython" in l]  # REEMA's own Python is never run as admin
    assert "Build Ahmad's prompt text first, as yourself" in s
    assert 'git -c core.fsmonitor= -C $Repo status --porcelain -- "src/snafi_worker"' in s and "uncommitted changes" in s
    lock = s.index("icacls $Target /inheritance:r")
    assert lock < s.index("robocopy $source") < s.index("pip install")
    assert 'icacls (Join-Path $Target "*") /reset /T /Q' in s and "icacls $Target /reset" not in s


def test_deploy_keeps_the_worker_out_of_khalids_folders():
    s = text("deploy.ps1")
    assert '[string[]]$DenyFolders = @("D:\\Projects", "D:\\Antigravity_Projects")' in s
    assert 'icacls $folder /deny "${WorkerUser}:(OI)(CI)F"' in s
    backups = [line for line in s.splitlines() if line.startswith("icacls $Backups")][0]
    assert "/inheritance:r" in backups and '"${WorkerUser}:(OI)(CI)M"' in backups and "${me}" not in backups
    assert '/inheritance:r /grant:r' in s and '"${WorkerUser}:(OI)(CI)RX"' in s  # cannot change its own code
    assert "must NOT be an administrator" in s and "Run this in an administrator PowerShell" in s


def test_the_task_runs_as_snafi_worker_isolated_and_unelevated():
    s = text("install_task.ps1")
    for needed in ("-AtStartup", "pythonw.exe", '-Argument "-I `"$Launcher`" worker"', "-RunLevel Limited",
                   "Get-Credential", "-RestartCount 999", "-MultipleInstances IgnoreNew", '[string]$WorkerUser = "snafi-worker"'):
        assert needed in s
    assert "Highest" not in s and "-AtLogOn" not in s


def test_the_launcher_runs_python_isolated():
    assert '"%~dp0venv\\Scripts\\python.exe" -I "%~dp0app\\snafi.py" %*' in text("snafi.cmd")


def test_the_launcher_dispatches_only_known_commands(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("snafi_launcher", DEPLOY / "snafi.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    assert launcher.main(["format-c"]) == 2
    seen = []
    import src.snafi_worker.__main__ as worker_main
    monkeypatch.setattr(worker_main, "main", lambda argv: seen.append(argv) or 0)
    assert launcher.main(["check"]) == 0 and launcher.main(["reset-brain"]) == 0 and launcher.main([]) == 0
    assert seen == [["--check"], ["--reset-brain"], []]


@pytest.mark.parametrize("command,powershell", [
    (r"powershell -ExecutionPolicy Bypass -File src\snafi_worker\deploy\deploy.ps1", True),
    (r"powershell -File src\snafi_worker\deploy\install_task.ps1", True),
    (r"C:\SnafiWorker\snafi.cmd prove", False),
    (r"type C:\SnafiWorker\app\src\snafi_worker\worker.yaml", False),
    (r"dir C:\Users\snafi-worker\AppData\Roaming\REEMA", True),
    (r'runas /user:snafi-worker "cmd"', False),
    (r"python C:/SnafiWorker/app/snafi.py once", False),
    (r"Get-Content C:\Users\snafi-worker\.gemini\antigravity-cli\settings.json", True),
])
def test_guard_keeps_sessions_away_from_the_worker_user(command, powershell):
    assert "Snafi" in (_guard().reason(command, powershell=powershell) or "")


@pytest.mark.parametrize("command,powershell", [
    ("agy --version", False), ("agy -p hello", False), (r"C:\Users\Khali\AppData\Local\agy\bin\agy.exe models", True),
    ("& 'agy.exe' mcp list", True), ("cd x && agy", False), ("echo $(agy --version)", False),
])
def test_guard_stops_sessions_running_agy(command, powershell):
    assert "agy" in (_guard().reason(command, powershell=powershell) or "")


@pytest.mark.parametrize("command", [
    "python -m pytest tests/test_snafi_worker_deploy.py -q", "ls src/snafi_worker", "git status",
    "grep -rn agy src", "git log --grep agy",
])
def test_guard_still_allows_normal_work(command):
    assert _guard().reason(command) is None
