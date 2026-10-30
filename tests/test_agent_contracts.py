"""Exercise real agent orchestration/prompt code with a fake model boundary."""
from unittest.mock import AsyncMock
import pytest
from src import agents


CASES = [
    ("ResearchAgent", "research_process", ["Incident Management", ["ITIL v4"]]),
    ("StandardsAgent", "analyze_compliance", ["Incident Management", ["ITIL v4"]]),
    ("ContentAgent", "generate_sop", ["Incident Management", {"research": {"raw_research": "Evidence"}, "standards": {"compliance_analysis": "Controls"}}]),
    ("ContentAgent", "refine_content", ["Draft", ["Add controls"]]),
    ("ContentAgent", "generate_drawio_flowchart", ["Incident Management", {"Detect": ["Log", "Triage"]}]),
    ("AccessAgent", "analyze_access_requirements", ["Access Management", ["ISO 27001"]]),
    ("AccessAgent", "generate_access_content", ["Access Management", {"roles": ["Owner"]}]),
    ("AccessAgent", "generate_access_management_sop", []),
    ("ProblemAgent", "research_problem_management", ["Problem Management", ["ITIL v4"]]),
    ("ProblemAgent", "generate_problem_content", ["Problem Management", {"problem_research": "RCA"}]),
    ("ProblemAgent", "generate_problem_management_sop", []),
    ("DataAgent", "design_analytics_framework", ["Incident Management", ["MTTR"], {"evidence": "data"}]),
    ("DataAgent", "create_dashboard_design", ["Incident Management", [{"name": "MTTR", "description": "Time to resolution"}]]),
]


def test_content_research_tail_is_not_silently_cut():
    agent = agents.ContentAgent(api_key="")
    research = {"research": {"raw_research": "x" * 9000 + "TAIL"}, "data": {"analytics_framework": "data"}, "access": {"access_analysis": "access"}, "problem": {"problem_research": "problem"}}
    summary = agent._extract_research_summary(research)
    assert "TAIL" in summary and "access" in summary and "problem" in summary and "data" in summary


def test_secretary_priorities():
    secretary = agents.SecretaryAgent(api_key="")
    for message, expected in [("urgent", "P1-Critical"), ("deadline", "P2-High"), ("status", "P3-Medium"), ("idea", "P4-Low")]:
        assert secretary._infer_priority("Agent 1", message) == expected


def test_strategic_guidance_transferred_to_leader():
    leader = agents.LeaderAgent(api_key="")
    assert "Business value, cost benefit, and return on investment analysis" in leader.strategic_guidance
    summary = agents.ContentAgent(api_key="")._extract_research_summary({"strategic_guidance": leader.strategic_guidance})
    assert "Business value, cost benefit, and return on investment analysis" in summary
    assert "owner_agent" not in __import__("src.utils.config", fromlist=["config_manager"]).config_manager.agents_config


@pytest.mark.asyncio
async def test_secretary_routing_is_local_not_a_model_call():
    secretary = agents.SecretaryAgent(api_key="")
    secretary._call_claude = AsyncMock(side_effect=AssertionError("No model needed"))
    result = await secretary.coordinate_team_communication("Status ready", "Abdullah", ["Agent 1"])
    assert result["priority"] == "P3-Medium"
    secretary._call_claude.assert_not_awaited()
