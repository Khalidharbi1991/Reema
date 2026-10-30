"""scripts/dev.py reports setup failures, but passes a command's own exit code through."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("dev_launcher", Path(__file__).resolve().parents[1] / "scripts" / "dev.py")
dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dev)


def test_a_failing_command_exits_with_its_own_code_and_no_setup_message(monkeypatch, capsys):
    def failing(arguments, **kwargs):
        raise subprocess.CalledProcessError(2, arguments)
    monkeypatch.setattr(dev, "run", failing)
    with pytest.raises(SystemExit) as exit_info:
        dev.forward(["-m", "src.main", "revise"])
    assert exit_info.value.code == 2
    assert "Development setup failed" not in capsys.readouterr().err


def test_a_successful_command_returns_normally(monkeypatch):
    calls = []
    monkeypatch.setattr(dev, "run", lambda arguments, **kwargs: calls.append(arguments))
    dev.forward(["-m", "pytest"])
    assert calls == [["-m", "pytest"]]
