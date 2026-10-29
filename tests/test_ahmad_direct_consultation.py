"""Ahmad consults chat specialists directly; Abdullah leads only the SOP pipeline."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from src.agents import LeaderAgent
from src.assistant import AGENT_CLASSES
from src.utils.config import ConfigManager, SystemConfig
from src.utils.coordination import AGENT_KEYS, IntentResolution, Selection
from tests.test_coordination_package import chat, prompt

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def no_leader(monkeypatch):
    def construct(*args, **kwargs):
        raise AssertionError("Chat must not construct the SOP pipeline leader")

    monkeypatch.setattr(LeaderAgent, "__init__", construct)


def test_leader_is_not_a_chat_capability():
    assert "leader_agent" not in AGENT_KEYS and "leader_agent" not in AGENT_CLASSES
    with pytest.raises(ValueError):
        Selection(agent="leader_agent", reasons=["strategy"])
    with pytest.raises(ValueError):
        IntentResolution(intent="advisory", agents=["leader_agent"], status="ready", questions=[], rationale="Strategy")
    assert not hasattr(LeaderAgent, "coordinate_consultations")


def test_abdullah_keeps_pipeline_strategy_guidance():
    leader = LeaderAgent(api_key="")
    assert leader.name == "Abdullah"
    assert "IT strategy and roadmap development" in leader.strategic_guidance


@pytest.mark.parametrize("message", [
    "Compare our strategy and budget",
    "Build a roadmap and business case",
    "Help me prioritize this decision",
    "ما هي الاستراتيجية والميزانية المناسبة؟",
    "خطة استراتيجية ورتب الاولويات",
])
def test_strategy_requests_stay_with_ahmad(chat, message):
    plan = chat.plan(message)
    assert plan.status == "ready" and plan.selections == []
    assert chat.route(message) == "secretary_agent"


def test_mixed_strategy_request_selects_only_the_matching_specialist(chat):
    plan = chat.plan("Strategy and budget for the MFA rollout")
    assert [s.agent for s in plan.selections] == ["access_agent"]


@pytest.mark.asyncio
async def test_ahmad_answers_strategy_with_governance_framing(chat, no_leader):
    answer = await chat.reply("Compare our strategy and budget", allow_external_ai=True)
    assert answer["consulted_agents"] == [] and answer["coordination"]["coordinator"] == "Ahmad"
    ahmad = chat.agents["secretary_agent"]._call_claude
    ahmad.assert_awaited_once()
    system = ahmad.await_args.kwargs["system"]
    for expected in ("IT strategy, roadmap and prioritization advice", "Business value, cost-benefit",
                     "Governance, risk escalation", "consequential decisions stay with the user"):
        assert expected in system
    assert "Abdullah" not in prompt(chat)


@pytest.mark.asyncio
async def test_specialists_do_not_receive_ahmads_coordinator_framing(chat, no_leader):
    await chat.reply("Explain MFA", allow_external_ai=True)
    system = chat.agents["access_agent"]._call_claude.await_args.kwargs["system"]
    assert "You are Agent 6" in system and "As coordinator" not in system


@pytest.mark.asyncio
async def test_session_rejects_overlapping_consultations(chat):
    chat.consultation_status["status"] = "consulting"
    with pytest.raises(RuntimeError, match="consultation is already running"):
        await chat.reply("Explain MFA", allow_external_ai=True)
    chat.agents["access_agent"]._call_claude.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolved_intent_cannot_route_to_the_pipeline_leader(chat):
    chat.resolve_intent = True
    chat.agents["secretary_agent"]._call_claude.return_value = json.dumps({
        "intent": "advisory", "agents": ["leader_agent"], "excluded_agents": [], "status": "ready",
        "questions": [], "rationale": "Strategy request"})
    with pytest.raises(ValueError, match="IntentResolution"):
        await chat.reply("Compare our strategy and budget", allow_external_ai=True)
    chat.agents["secretary_agent"]._call_claude.assert_awaited_once()  # Only the resolver call.


@pytest.mark.parametrize("change", ["route", "default"])
def test_config_naming_leader_agent_fails_with_file_and_remedy(tmp_path, change):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    path = tmp_path / "config" / "assistant_routes.yaml"
    routing = yaml.safe_load(path.read_text(encoding="utf-8"))
    if change == "route":
        routing["routes"].append({"agent": "leader_agent", "keywords": ["strategy"]})
        entry = f"routes[{len(routing['routes']) - 1}]"
    else:
        routing["default_agent"] = "leader_agent"
        entry = "default_agent"
    path.write_text(yaml.safe_dump(routing, allow_unicode=True), encoding="utf-8")
    settings = SystemConfig(_env_file=None, project_root=tmp_path, config_dir=tmp_path / "config",
                            output_dir=tmp_path / "output")
    with pytest.raises(ValueError) as error:
        ConfigManager(settings)
    message = str(error.value)
    assert str(path) in message and entry in message
    assert "leader_agent" in message and "remove" in message
