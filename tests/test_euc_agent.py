"""Agent 10's end-user computing role, routing and advisory-only consultation."""

import json
from unittest.mock import AsyncMock

import pytest

from src.agents import EUCAgent
from src.assistant import AGENT_CLASSES, AssistantSession
from src.utils.config import config_manager
from src.utils.coordination import AGENT_KEYS
from tests.test_coordination_package import ChatAgent, chat


def test_agent_10_is_a_configured_conversational_role():
    settings = config_manager.get_agent_config("euc_agent")
    assert EUCAgent.AGENT_NAME == settings["name"] == "Agent 10"
    assert EUCAgent.AGENT_ROLE == settings["role"]
    assert AGENT_CLASSES["euc_agent"] is EUCAgent and "euc_agent" in AGENT_KEYS
    # No model override: Agent 10 inherits the configured worker default.
    assert settings.get("model") is None


def test_agent_10_prompt_keeps_the_reversible_advisory_protocol():
    system = EUCAgent(api_key="")._build_system_prompt()
    for guard in ("Frame before advising", "Reversibility first", "kill switch", "irreversible",
                  "-WhatIf", "Never fabricate cmdlets", "cannot run scripts", "Asia/Riyadh",
                  "Sunday to Thursday", "Next step:", "Open risks / assumptions:"):
        assert guard in system
    assert "Treat the user as a peer" in system


@pytest.mark.parametrize("message,primary", [
    ("Plan the November Patch Tuesday deployment rings for 5,000 laptops", "euc_agent"),
    ("Package this app with PSADT as an intunewin file", "euc_agent"),
    ("Review our MECM co-management workloads before the Windows 11 upgrade", "euc_agent"),
    ("Draft a change request for the Intune feature update", "euc_agent"),
    ("جهز خطة لإدارة التحديثات الأمنية", "euc_agent"),
    ("كيف نحسن توزيع البرامج على أجهزة المستخدمين؟", "euc_agent"),
])
def test_endpoint_requests_route_to_agent_10(message, primary):
    assert AssistantSession("work").route(message) == primary


@pytest.mark.parametrize("message,selected", [
    ("Draft a change request for the Intune feature update", ["euc_agent", "content_agent"]),
    ("Patch compliance KPI dashboard", ["euc_agent", "standards_agent", "data_agent"]),
    ("No patching advice; prepare an agenda", ["content_agent"]),
    ("Resize this image for the slide", []),
    ("Explain accessibility", []),
])
def test_agent_10_joins_mixed_plans_and_respects_exclusions(chat, message, selected):
    plan = chat.plan(message)
    assert plan.status == "ready"
    assert [s.agent for s in plan.selections] == selected


@pytest.mark.asyncio
async def test_agent_10_consultation_is_advisory_and_uses_its_protocol(chat):
    agent = EUCAgent(api_key="")
    agent._call_claude = AsyncMock(return_value=json.dumps({"advice": "Pilot 2% first. Next step: confirm ring groups."}))
    chat.agents["euc_agent"] = agent
    result = await chat.reply("Plan the Patch Tuesday deployment rings", allow_external_ai=True)
    assert result["consulted_agents"] == ["Agent 10"]
    system = agent._call_claude.await_args.kwargs["system"]
    assert "Reversibility first" in system and "personal contexts separate" in system
    assert "Do not execute actions or claim approvals" in system
    chat.agents["leader_agent"]._call_claude.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_10_never_consults_without_external_ai_consent(chat):
    chat.agents["euc_agent"] = ChatAgent("Agent 10", chat.agents["secretary_agent"].directory)
    with pytest.raises(PermissionError):
        await chat.reply("Plan the Patch Tuesday deployment rings")
    chat.agents["euc_agent"]._call_claude.assert_not_awaited()
