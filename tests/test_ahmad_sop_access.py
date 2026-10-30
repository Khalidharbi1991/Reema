"""Ahmad finds, confirms and hands finished-SOP review/revise jobs to Abdullah. Mocked provider only."""

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.agents.content_agent import ContentAgent
from src.agents.leader_agent import LeaderAgent
from src.agents.review_agent import ReviewAgent
from src.assistant import AssistantSession
from src.utils import approvals
from src.utils.config import config_manager
from src.utils.documents import section_map, sha
from tests.existing_sop_helpers import template_sop, assessment, issue

PROFILE = config_manager.document_profile


@pytest.fixture
def library(tmp_path, monkeypatch):
    out = tmp_path / "output"
    out.mkdir()
    monkeypatch.setattr(config_manager.system_config, "output_dir", out)
    monkeypatch.setattr(config_manager.system_config, "task_data_dir", tmp_path / "assistant")
    monkeypatch.setattr(config_manager.system_config, "allow_external_ai", False)
    (out / "SOP_Change_Management_V1.md").write_text(template_sop())
    for number, name in enumerate(["SOP_User_Incident_Management_V1.md", "SOP_User_Incident_Management_V2.md"]):
        path = out / name
        path.write_text(template_sop())
        os.utime(path, (1_700_000_000 + number, 1_700_000_000 + number))
    return out


@pytest.fixture
def session(library):
    return AssistantSession("work", api_key="synthetic")


class Workers:
    """Records the agents Ahmad hands to Abdullah, with mocked model replies."""

    def __init__(self, monkeypatch, review_reply=None, content_reply=None, recheck=None):
        self.leaders = []
        original = AssistantSession._sop_leader

        def build(session, action, local_only):
            leader = original(session, action, local_only)
            if "ReviewAgent" in leader.worker_agents:
                replies = recheck if callable(recheck) else [r for r in (review_reply, recheck) if r is not None]
                leader.worker_agents["ReviewAgent"]._call_claude = AsyncMock(side_effect=replies)
            if "ContentAgent" in leader.worker_agents:
                leader.worker_agents["ContentAgent"]._call_claude = AsyncMock(side_effect=content_reply)
            self.leaders.append(leader)
            return leader
        monkeypatch.setattr(AssistantSession, "_sop_leader", build)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.mark.asyncio
async def test_one_match_is_confirmed_before_anything_runs(session, library, monkeypatch):
    workers = Workers(monkeypatch)
    reply = await session.reply("Please review my change management SOP")
    assert "SOP_Change_Management_V1.md" in reply["reply"] and "Anthropic" in reply["reply"]
    assert session.pending_sop["stage"] == "confirm" and workers.leaders == []
    cancelled = await session.reply("no")
    assert "Cancelled" in cancelled["reply"] and session.pending_sop is None and workers.leaders == []


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
async def test_yes_without_chat_consent_sends_nothing(session, library, monkeypatch):
    workers = Workers(monkeypatch)
    await session.reply("review my change management SOP")
    reply = await session.reply("yes")
    assert "without permission" in reply["reply"] and "--allow-external-ai" in reply["reply"]
    assert workers.leaders == [] and not (library / "runs").exists()


@pytest.mark.asyncio
async def test_local_template_check_needs_no_consent(session, library, monkeypatch):
    workers = Workers(monkeypatch)
    await session.reply("review my change management SOP")
    reply = await session.reply("local")
    assert "template check only" in reply["reply"] and "0 template gap(s)" in reply["reply"]
    assert workers.leaders[0].worker_agents == {}


@pytest.mark.asyncio
async def test_confirmed_review_runs_through_abdullah(session, library, monkeypatch):
    path = library / "SOP_Change_Management_V1.md"
    before = digest(path)
    workers = Workers(monkeypatch, review_reply=assessment(issue("sec-tools", "ServiceNow version 2019.", category="outdated",
                                                                 description="Old tool version")))
    await session.reply("review my change management SOP", allow_external_ai=True)
    reply = await session.reply("yes", allow_external_ai=True)
    assert "1 other finding(s)" in reply["reply"] and "Old tool version" in reply["reply"]
    assert workers.leaders[0].name == "Abdullah"
    assert workers.leaders[0].worker_agents["ReviewAgent"]._call_claude.await_count == 1
    assert digest(path) == before


@pytest.mark.asyncio
async def test_confirmed_revision_ends_awaiting_human_approval(session, library, monkeypatch):
    path = library / "SOP_Change_Management_V1.md"
    before = digest(path)
    content = template_sop()
    locations = section_map(content, PROFILE)
    new_body = "### 5.1 Logging\nLog every incident in the tool.\n\n### 5.2 Escalation\nEscalate P1 within 15 minutes."
    patch = json.dumps({"base_document_sha256": sha(content), "patches": [
        {"section_id": "sec-procedures", "body": new_body, "base_section_sha256": locations["sec-procedures"]["sha256"]}]})

    def recheck(messages, **kwargs):
        data = json.loads(messages[0]["content"].split("CORRECTION DATA:\n", 1)[1])
        return json.dumps({"corrections": [{"finding_id": f["finding_id"], "status": "resolved", "rationale": "Done",
                                            "section_id": f["section_id"], "quote": "within 15 minutes"}
                                           for f in data["original_findings"]]})
    workers = Workers(monkeypatch, content_reply=[patch], recheck=recheck)
    decided = AsyncMock(side_effect=AssertionError("Ahmad must never record a decision"))
    monkeypatch.setattr(approvals, "record_decision", decided)
    confirm = await session.reply("fix the escalation part in my change management SOP", allow_external_ai=True)
    assert "'5. Detailed Procedures'" in confirm["reply"]
    reply = await session.reply("yes", allow_external_ai=True)
    assert "awaiting your approval" in reply["reply"] and "I can't approve it" in reply["reply"]
    record = json.loads(Path(workers.leaders[0].context["delivery"]["approval_record"]).read_text())
    assert record["status"] == "awaiting_human_approval" and record["reviewer"] is None
    assert digest(path) == before
    decided.assert_not_called()


@pytest.mark.asyncio
async def test_unclear_section_is_asked_before_confirming(session, library, monkeypatch):
    workers = Workers(monkeypatch)
    reply = await session.reply("improve my change management SOP")
    assert "Which section" in reply["reply"] and "Detailed Procedures" in reply["reply"]
    confirm = await session.reply("Tools & Systems")
    assert "'8. Tools & Systems'" in confirm["reply"] and workers.leaders == []


@pytest.mark.asyncio
async def test_file_changed_after_confirmation_stops(session, library, monkeypatch):
    workers = Workers(monkeypatch)
    await session.reply("review my change management SOP", allow_external_ai=True)
    (library / "SOP_Change_Management_V1.md").write_text(template_sop() + "\nEdited.\n")
    reply = await session.reply("yes", allow_external_ai=True)
    assert "changed after you confirmed" in reply["reply"] and workers.leaders == []


@pytest.mark.asyncio
async def test_arabic_request_is_recognised(session, library):
    reply = await session.reply("راجع الاجراء change management")
    assert "SOP_Change_Management_V1.md" in reply["reply"]


@pytest.mark.parametrize("message", ["How should I review an SOP?", "Draft an SOP for MFA", "review my budget"])
def test_advice_and_other_requests_are_not_intercepted(session, message):
    import asyncio
    assert asyncio.run(session._sop_request(message, False)) is None
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
    assert "reema chat --area work --allow-external-ai" in choose.output.splitlines()
    for name in ("SOP_User_Incident_Management_V2.md", "SOP_User_Incident_Management_V1.md"):
        assert f"reema review {library / name} --allow-external-ai" in choose.output.splitlines()
    revise = runner.invoke(app, ["chat", "revise my change management SOP: escalation paths must name the duty manager",
                                 "--area", "work"])
    assert revise.exit_code == 0, revise.output
    assert "Reply yes" not in revise.output
    command = next(line for line in revise.output.splitlines() if line.startswith("reema revise"))
    assert str(library / "SOP_Change_Management_V1.md") in command and "--instruction 'revise my change management" in command
    assert "--section '5. Detailed Procedures'" in command and command.endswith("--allow-external-ai")
