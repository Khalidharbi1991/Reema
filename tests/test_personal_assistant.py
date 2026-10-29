"""Task isolation and one-entry-point behavior use only synthetic local data."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock

import pytest
from typer.testing import CliRunner

from src.assistant import AssistantSession
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


def test_cli_tasks_and_local_chat_do_not_need_model(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "task_data_dir", tmp_path / "assistant")
    runner = CliRunner()
    added = runner.invoke(app, ["task", "add", "Review plan", "--area", "work", "--priority", "high"])
    assert added.exit_code == 0, added.output
    listed = runner.invoke(app, ["task", "list", "--area", "work"])
    assert listed.exit_code == 0 and "Review plan" in listed.output
    assert runner.invoke(app, ["task", "list", "--area", "personal"]).exit_code == 0
    local_chat = runner.invoke(app, ["chat", "/task add Call friend", "--area", "personal"])
    assert local_chat.exit_code == 0, local_chat.output
    natural_chat = runner.invoke(app, ["chat", "Add a task to buy groceries", "--area", "personal"])
    assert natural_chat.exit_code == 0 and "buy groceries" in natural_chat.output
    assert "Call friend" in runner.invoke(app, ["task", "list", "--area", "personal"]).output
    assert "buy groceries" in runner.invoke(app, ["task", "list", "--area", "personal"]).output
    assert "Call friend" not in listed.output
    saved = runner.invoke(app, ["memory", "set", "tone", "Concise", "--area", "work"])
    assert saved.exit_code == 0, saved.output
    assert "Concise" in runner.invoke(app, ["memory", "list", "--area", "work"]).output
    assert "Concise" not in runner.invoke(app, ["memory", "list", "--area", "personal"]).output
    denied = runner.invoke(app, ["chat", "Plan my day", "--area", "work"])
    assert denied.exit_code == 2 and "Authorize" in denied.output


@pytest.mark.asyncio
async def test_ahmad_routes_specialist_and_sends_only_selected_area(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "task_data_dir", tmp_path)
    TaskStore(tmp_path, "work").add("Confidential work task")
    TaskStore(tmp_path, "personal").add("Private personal task")
    TaskStore(tmp_path, "personal").remember("tone", "Warm")

    class FakeAgent:
        def __init__(self, name):
            self.name = name
            self._call_claude = AsyncMock(return_value=f"Advice from {name}")

        def task_store(self, area):
            return TaskStore(tmp_path, area)

        async def close(self):
            pass

    personal = AssistantSession("personal", api_key="synthetic")
    personal.agents["secretary_agent"] = FakeAgent("Ahmad")
    assert personal.route("How should I configure MFA?") == "access_agent"
    answer = await personal.reply("Help me plan today", allow_external_ai=True)
    prompt = personal.agents["secretary_agent"]._call_claude.await_args.args[0][-1]["content"]
    assert answer["consulted"] is None
    assert "Private personal task" in prompt and "Confidential work task" not in prompt
    assert "tone: Warm" in prompt

    work = AssistantSession("work", api_key="synthetic")
    work.agents["secretary_agent"] = FakeAgent("Ahmad")
    work.agents["access_agent"] = FakeAgent("Agent 6")
    assert work.route("How should I configure MFA?") == "access_agent"
    answer = await work.reply("How should I configure MFA?", allow_external_ai=True)
    assert answer["consulted"] == "Agent 6"
    assert work.agents["access_agent"]._call_claude.await_count == 1
    prompt = work.agents["secretary_agent"]._call_claude.await_args.args[0][-1]["content"]
    assert "Confidential work task" not in prompt and "Private personal task" not in prompt

    # Strategy advice is Ahmad's own; Abdullah leads only the SOP pipeline.
    assert work.route("Help me compare strategy options") == "secretary_agent"
    strategic = await work.reply("Help me compare strategy options", allow_external_ai=True)
    assert strategic["consulted"] is None and strategic["consulted_agents"] == []
    assert "leader_agent" not in work.agents
