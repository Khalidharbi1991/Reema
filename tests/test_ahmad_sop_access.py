"""Ahmad finds and confirms finished SOPs in chat: the local template check runs here, review and revise
run in Claude Code. No provider calls."""

import hashlib
import os
from pathlib import Path

import pytest

from src.agents.leader_agent import LeaderAgent
from src.assistant import AssistantSession
from src.utils.config import config_manager
from tests.existing_sop_helpers import template_sop


@pytest.fixture
def library(tmp_path, monkeypatch):
    out = tmp_path / "output"
    out.mkdir()
    monkeypatch.setattr(config_manager.system_config, "output_dir", out)
    monkeypatch.setattr(config_manager.system_config, "task_data_dir", tmp_path / "assistant")
    (out / "SOP_Change_Management_V1.md").write_text(template_sop())
    for number, name in enumerate(["SOP_User_Incident_Management_V1.md", "SOP_User_Incident_Management_V2.md"]):
        path = out / name
        path.write_text(template_sop())
        os.utime(path, (1_700_000_000 + number, 1_700_000_000 + number))
    return out


@pytest.fixture
def session(library):
    return AssistantSession("work", api_key="synthetic")


@pytest.fixture
def leaders(monkeypatch):
    """Every review job Ahmad starts; each must be local only."""
    started = []
    original = LeaderAgent.review_existing

    async def record(leader, source, **kwargs):
        started.append(kwargs)
        return await original(leader, source, **kwargs)
    monkeypatch.setattr(LeaderAgent, "review_existing", record)
    return started


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.mark.asyncio
async def test_one_match_is_confirmed_before_anything_runs(session, library, leaders):
    reply = await session.reply("Please review my change management SOP")
    assert "SOP_Change_Management_V1.md" in reply["reply"] and "Nothing leaves this computer" in reply["reply"]
    assert "Claude Code" in reply["reply"]
    assert session.pending_sop["stage"] == "confirm" and leaders == []
    cancelled = await session.reply("no")
    assert "Cancelled" in cancelled["reply"] and session.pending_sop is None and leaders == []


@pytest.mark.asyncio
async def test_several_matches_are_listed_newest_first_and_chosen_by_number(session, library):
    reply = await session.reply("check my incident SOP")
    lines = reply["reply"].splitlines()
    assert lines[1].startswith("1. SOP_User_Incident_Management_V2.md") and lines[2].startswith("2. SOP_User_Incident_Management_V1.md")
    assert "SOP_Change_Management" not in reply["reply"]
    wrong = await session.reply("7")
    assert "from 1 to 2" in wrong["reply"]
    chosen = await session.reply("2")
    assert "SOP_User_Incident_Management_V1.md" in chosen["reply"] and session.pending_sop["stage"] == "confirm"


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["yes", "local"])
async def test_confirmed_review_is_the_local_template_check(session, library, leaders, answer):
    path = library / "SOP_Change_Management_V1.md"
    before = digest(path)
    await session.reply("review my change management SOP")
    reply = await session.reply(answer)
    assert "Template check of SOP_Change_Management_V1.md finished: 0 template gap(s)" in reply["reply"]
    assert "Claude Code" in reply["reply"] and leaders == [{"local_only": True}]
    assert digest(path) == before


@pytest.mark.asyncio
async def test_revision_requests_point_to_claude_code(session, library, leaders):
    reply = await session.reply("fix the escalation part in my change management SOP")
    assert "SOP_Change_Management_V1.md" in reply["reply"] and "Claude Code" in reply["reply"]
    assert session.pending_sop is None and leaders == [] and not (library / "runs").exists()


@pytest.mark.asyncio
async def test_file_changed_after_confirmation_stops(session, library, leaders):
    await session.reply("review my change management SOP")
    (library / "SOP_Change_Management_V1.md").write_text(template_sop() + "\nEdited.\n")
    reply = await session.reply("yes")
    assert "changed after you confirmed" in reply["reply"] and leaders == []


@pytest.mark.asyncio
async def test_arabic_request_is_recognised(session, library):
    reply = await session.reply("راجع الاجراء change management")
    assert "SOP_Change_Management_V1.md" in reply["reply"]


@pytest.mark.parametrize("message", ["How should I review an SOP?", "Draft an SOP for MFA", "review my budget"])
def test_advice_and_other_requests_are_not_intercepted(session, message):
    import asyncio
    assert asyncio.run(session._sop_request(message)) is None
    assert session.pending_sop is None


@pytest.mark.asyncio
async def test_unknown_file_asks_for_a_name(session):
    reply = await session.reply("review my payroll SOP")
    assert "could not find" in reply["reply"]


def test_one_message_chat_prints_commands_instead_of_asking(library):
    from typer.testing import CliRunner
    from src.main import app
    runner = CliRunner()
    choose = runner.invoke(app, ["chat", "check my incident SOP", "--area", "work"])
    assert choose.exit_code == 0, choose.output
    assert "Reply with its number" not in choose.output
    for name in ("SOP_User_Incident_Management_V2.md", "SOP_User_Incident_Management_V1.md"):
        assert f"reema review {library / name}" in choose.output.splitlines()
    revise = runner.invoke(app, ["chat", "revise my change management SOP: escalation paths must name the duty manager",
                                 "--area", "work"])
    assert revise.exit_code == 0, revise.output
    assert "Claude Code" in revise.output and "reema revise" not in revise.output
