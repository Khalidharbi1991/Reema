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
    assert s.count("pip install") == 1 and '$PythonVersion = "3.12.10"' in s
    assert "--require-hashes --only-binary=:all: --no-deps" in s
    req = text("requirements-worker.txt")
    pinned = sorted(line.split("==")[0] for line in req.splitlines() if "==" in line and not line.startswith("#"))
    # Step 5: cryptography (Web Push) and the two packages it needs; each version and hash is checked
    # against uv.lock in tests/test_snafi_worker_requirements.py.
    assert pinned == ["cffi", "cryptography", "pycparser", "pyyaml", "tzdata"]
    assert "pyyaml==6.0.3" in req and "tzdata==2026.6" in req and req.count("--hash=sha256:") == 6
    assert "Program Files" not in s and "winget" not in s  # no machine-wide Python, no installer


def test_the_worker_gets_its_own_private_hash_checked_python():
    s = text("deploy.ps1")
    assert '$PythonUrl = "https://www.nuget.org/api/v2/package/python/3.12.10"' in s
    assert '$PythonSha256 = "0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8"' in s
    assert "(Get-FileHash -Algorithm SHA256 $package).Hash" in s and "does not match the pinned" in s
    assert "ExtractToDirectory($package, $pythonHome)" in s and 'Join-Path $pythonHome "tools\\python.exe"' in s
    # downloaded only into the locked folder, checked before unpacking, unpacked fresh, then the wheels
    order = [s.index(x) for x in ("icacls $Target /inheritance:r", "Invoke-WebRequest", "$hash -ne $PythonSha256",
                                  "if (Test-Path $pythonHome) { Remove-Item -Recurse -Force $pythonHome }",
                                  "ExtractToDirectory", "pip install")]
    assert order == sorted(order)
    assert '$downloads = Join-Path $Target "downloads"' in s
    assert '& $py -I -m pip install' in s and 'if ($version -ne $PythonVersion)' in s


def test_deploy_runs_no_repo_code_as_admin_and_locks_before_copying():
    s = text("deploy.ps1")
    code = [l for l in s.split("$ErrorActionPreference")[1].splitlines() if not l.strip().startswith(("throw", "#"))]
    assert not [l for l in code if ".venv" in l or "$repoPython" in l]  # REEMA's own Python is never run as admin
    assert "Build Ahmad's prompt text first, as yourself" in s
    assert 'git -c core.fsmonitor= -C $Repo status --porcelain -- "src/snafi_worker"' in s and "uncommitted changes" in s
    lock = s.index("icacls $Target /inheritance:r")
    assert lock < s.index("robocopy $source") < s.index("pip install")
    assert 'icacls (Join-Path $Target "*") /reset /T /Q' in s and "icacls $Target /reset" not in s


def test_deploy_sets_admin_owners_and_unpacks_a_fresh_python():
    s = text("deploy.ps1")
    assert 'icacls $Target /setowner "*S-1-5-32-544" /T /C /Q' in s
    assert 'icacls $Backups /setowner "*S-1-5-32-544" /T /C /Q' in s
    assert s.index("icacls $Backups /setowner") < s.index("icacls $Backups /inheritance:r")
    assert s.index("Remove-Item -Recurse -Force $pythonHome") < s.index("pip install")
    assert s.index("pip install") < s.index('icacls $Target /setowner')  # the fresh Python gets admin owners too
    assert 'Stop-ScheduledTask -TaskName "Snafi Worker"' in s


def test_deploy_runs_the_worker_as_khalid_read_only_and_keeps_the_dormant_user_out():
    s = text("deploy.ps1")
    assert "[string]$RunAs = [Security.Principal.WindowsIdentity]::GetCurrent().Name" in s
    assert '[string]$DormantUser = "worker"' in s  # kept, unused, for a possible return to agy
    assert "Translate([Security.Principal.SecurityIdentifier])" in s  # grants by SID, not by name (SEC-42)
    assert '"S-1-5-18"' in s and '"S-1-5-32-544"' in s and "Run the worker as your own user" in s
    lock = [line for line in s.splitlines() if line.startswith("icacls $Target /inheritance:r")][0]
    assert '"*${runAsSid}:(OI)(CI)RX"' in lock and ":(OI)(CI)M" not in lock and "WorkerUser" not in s
    assert '[string[]]$DenyFolders = @("D:\\Projects", "D:\\Antigravity_Projects")' in s
    assert 'icacls $folder /deny "*$($dormant.SID.Value):(OI)(CI)F"' in s
    backups = [line for line in s.splitlines() if line.startswith("icacls $Backups /inheritance:r")][0]
    assert '"*${runAsSid}:(OI)(CI)M"' in backups
    assert 'icacls $Backups /remove:g "*$($dormant.SID.Value)"' in s
    assert "Remove-LocalUser" not in s and "Disable-LocalUser" not in s  # the dormant user is never deleted
    assert "Run this in an administrator PowerShell" in s


def test_the_task_runs_as_khalid_at_sign_in_unelevated_with_no_stored_password():
    s = text("install_task.ps1")
    for needed in ("-AtLogOn -User $RunAs", "pythonw.exe", '-Argument "-I `"$Launcher`" worker"',
                   "-LogonType Interactive", "-RunLevel Limited", "-RestartCount 999", "-MultipleInstances IgnoreNew",
                   "[string]$RunAs = [Security.Principal.WindowsIdentity]::GetCurrent().Name", "-Principal $Principal"):
        assert needed in s
    assert "Highest" not in s and "Get-Credential" not in s and "-Password" not in s


def test_the_launcher_and_task_use_the_private_python_isolated():
    assert '"%~dp0python\\tools\\python.exe" -I "%~dp0app\\snafi.py" %*' in text("snafi.cmd")
    assert '$Pythonw = Join-Path $Target "python\\tools\\pythonw.exe"' in text("install_task.ps1")
    assert "venv" not in text("snafi.cmd") and "venv" not in text("install_task.ps1")


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
    (r"dir C:\Users\worker\AppData\Roaming\REEMA", True),
    (r'runas /user:worker "cmd"', False),
    (r"python C:/SnafiWorker/app/snafi.py once", False),
    (r"Get-Content C:\Users\worker\.gemini\antigravity-cli\settings.json", True),
])
def test_guard_keeps_sessions_away_from_the_worker_user(command, powershell):
    assert "Snafi" in (_guard().reason(command, powershell=powershell) or "")


def test_sessions_are_denied_the_workers_files_now_that_it_runs_as_khalid():
    import json
    deny = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"]
    for verb in ("Read", "Edit", "Write"):
        for path in ("~/AppData/Roaming/REEMA/**", "./teams/coordination/snafi-backups/**", "//c/SnafiWorker/**"):
            assert f"{verb}({path})" in deny
    guard = _guard()
    for command in ("cmdkey /list", r"type %APPDATA%\REEMA\snafi-worker\logs\worker.log",
                    r"dir C:\SnafiWorker\app", "Get-StoredCredential -Target x"):
        assert "Snafi" in (guard.reason(command, powershell=True) or "")


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
