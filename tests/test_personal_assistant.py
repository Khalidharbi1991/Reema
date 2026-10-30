"""Task isolation and one-entry-point behavior use only synthetic local data."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from typer.testing import CliRunner

from src.main import app
from src.utils.config import config_manager
from src.utils.tasks import TaskStore


def test_tasks_are_separate_and_support_daily_workflow(tmp_path):
    work = TaskStore(tmp_path, "work")
    personal = TaskStore(tmp_path, "personal")
    first = work.add("Prepare meeting", priority="high", due=datetime.now(ZoneInfo("Asia/Riyadh")).date().isoformat(), project="Alpha")
    personal.add("Book appointment", priority="normal")
    assert [item["title"] for item in work.today()] == ["Prepare meeting"]
    assert [item["title"] for item in work.upcoming()] == ["Prepare meeting"]
    assert [item["title"] for item in work.list(project="Alpha")] == ["Prepare meeting"]
    assert work.list(project="Other") == []
    assert [item["title"] for item in personal.list()] == ["Book appointment"]
    with pytest.raises(ValueError, match="not found"):
        personal.get(first["id"])
    assert work.change(first["id"], status="done")["status"] == "done"
    assert work.today() == []
    assert work.change(first["id"], status="open", due=None)["due"] is None
    assert work.change(first["id"], status="archived")["status"] == "archived"
    assert work.list() == []
    assert work.list(status="all")[0]["title"] == "Prepare meeting"
    work.remember("style", "Brief")
    personal.remember("style", "Warm")
    assert work.preferences() == {"style": "Brief"}
    assert personal.preferences() == {"style": "Warm"}
    work.forget("style")
    assert work.preferences() == {} and personal.preferences() == {"style": "Warm"}
    if os.name == "posix":
        assert tmp_path.stat().st_mode & 0o077 == 0
        assert (tmp_path / "work.sqlite3").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("kwargs", [
    {"title": ""}, {"title": "a" * 241}, {"title": "Task", "due": "2026-02-30"},
    {"title": "Task", "priority": "unknown"},
])
def test_invalid_tasks_fail_closed(tmp_path, kwargs):
    with pytest.raises(ValueError):
        TaskStore(tmp_path, "work").add(**kwargs)


def test_cli_tasks_and_memory_do_not_need_model(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "task_data_dir", tmp_path / "assistant")
    runner = CliRunner()
    added = runner.invoke(app, ["task", "add", "Review plan", "--area", "work", "--priority", "high"])
    assert added.exit_code == 0, added.output
    listed = runner.invoke(app, ["task", "list", "--area", "work"])
    assert listed.exit_code == 0 and "Review plan" in listed.output
    assert runner.invoke(app, ["task", "list", "--area", "personal"]).exit_code == 0
    assert runner.invoke(app, ["task", "add", "Call friend", "--area", "personal"]).exit_code == 0
    assert "Call friend" in runner.invoke(app, ["task", "list", "--area", "personal"]).output
    assert "Call friend" not in listed.output
    saved = runner.invoke(app, ["memory", "set", "tone", "Concise", "--area", "work"])
    assert saved.exit_code == 0, saved.output
    assert "Concise" in runner.invoke(app, ["memory", "list", "--area", "work"]).output
    assert "Concise" not in runner.invoke(app, ["memory", "list", "--area", "personal"]).output
    retired = runner.invoke(app, ["chat", "Plan my day", "--area", "work"])
    assert retired.exit_code == 2 and "Claude Code" in retired.output
    assert "chat" not in runner.invoke(app, ["--help"]).output




def test_find_sop_lists_matching_file_names_newest_first_without_reading_them(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    for number, name in enumerate(["SOP_User_Incident_Management_V1.md", "SOP_User_Incident_Management_V2.docx",
                                   "SOP_Change_Management_V1.md"]):
        (out / name).write_bytes(b"not read")
        os.utime(out / name, (1_700_000_000 + number, 1_700_000_000 + number))
    runner = CliRunner()
    found = runner.invoke(app, ["find-sop", "incident", "SOP", "-o", str(out)], terminal_width=1000)
    assert found.exit_code == 0, found.output
    lines = found.output.splitlines()
    assert lines[0].startswith("1. ") and lines[0].split(" (")[0].endswith("SOP_User_Incident_Management_V2.docx")
    assert lines[1].split(" (")[0].endswith("SOP_User_Incident_Management_V1.md") and len(lines) == 2
    missing = runner.invoke(app, ["find-sop", "payroll", "-o", str(out)])
    assert missing.exit_code == 1 and "No SOP file name" in missing.output
