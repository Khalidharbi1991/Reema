"""Agent 10's end-user computing role and SOP enrichment."""

from pathlib import Path

import pytest

from src.agents import EUCAgent
from src.utils.config import config_manager
from tests.test_phase01 import catalog


def test_agent_10_is_a_configured_role():
    settings = config_manager.get_agent_config("euc_agent")
    assert EUCAgent.AGENT_NAME == settings["name"] == "Agent 10"
    assert EUCAgent.AGENT_ROLE == settings["role"]
    # No model override: Agent 10 inherits the configured worker default.
    assert settings.get("model") is None


def test_agent_10_subagent_keeps_the_pipeline_protocol_and_adds_the_closing():
    system = EUCAgent()._build_system_prompt()
    subagent = (Path(__file__).resolve().parents[1] / ".claude" / "agents" / "reema-agent10-euc.md").read_text(encoding="utf-8")
    assert system in subagent
    for guard in ("Frame before advising", "Reversibility first", "kill switch", "irreversible",
                  "-WhatIf", "Never fabricate cmdlets", "cannot run scripts", "Asia/Riyadh",
                  "Sunday to Thursday", "Treat the user as a peer"):
        assert guard in system
    assert "Next step:" not in system
    assert "Next step:" in subagent and "Open risks / assumptions:" in subagent
    assert "output/claude_code/advice/" in subagent and "Khalid's yes" in subagent


@pytest.mark.parametrize("process", ["Workstation Security Patches", "Devices Batch Management"])
def test_endpoint_processes_select_agent_10(catalog, process):
    assert catalog.resolve_process(process)[1]["specialists"] == ["euc"]


