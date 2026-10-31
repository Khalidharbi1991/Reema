"""Tests for individual agent implementations."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestLeaderAgent:
    """Test LeaderAgent (Abdullah)."""

    @patch('src.agents.leader_agent.config_manager')
    def test_leader_init(self, mock_cm):
        """Verify LeaderAgent initializes."""
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent()
        assert leader.name == "Abdullah"
        assert leader.worker_agents == {}

    @patch('src.agents.leader_agent.config_manager')
    def test_leader_register_worker(self, mock_cm):
        """Verify worker registration."""
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent()

        mock_worker = MagicMock()
        leader.register_worker("TestAgent", mock_worker)
        assert "TestAgent" in leader.worker_agents

    @patch('src.agents.leader_agent.config_manager')
    def test_leader_get_status(self, mock_cm):
        """Verify status dict structure."""
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent()
        status = leader.get_status()
        assert "leader" in status
        assert "workers" in status
        assert status["leader"] == "Abdullah"

    @patch('src.agents.leader_agent.config_manager')
    def test_leader_get_process_kpis_incident(self, mock_cm):
        """Verify incident-specific KPIs are returned."""
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent()

        kpis = leader._get_process_kpis("Incident Management", {})
        assert "Mean Time to Resolve (MTTR)" in kpis
        assert "First Contact Resolution Rate" in kpis

    @patch('src.agents.leader_agent.config_manager')
    def test_leader_get_process_kpis_access(self, mock_cm):
        """Verify access-specific KPIs are returned."""
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent()

        kpis = leader._get_process_kpis("Access Management", {})
        assert "Access Request Fulfillment Time" in kpis
        assert "MFA Adoption Rate" in kpis

    @pytest.mark.parametrize("process, expected", [
        ("Incident Management", "Mean Time to Resolve (MTTR)"),
        ("Change Management", "Change Success Rate"),
        ("Problem Management", "Known Error Resolution Time"),
        ("Access Management", "Access Request Fulfillment Time"),
        ("Service Request Management", "Request Fulfillment Time"),
        ("service_request_management", "Request Fulfillment Time"),
    ])
    @patch('src.agents.leader_agent.config_manager')
    def test_leader_matches_every_kpi_category_by_display_name(self, mock_cm, process, expected):
        """Multi-word categories such as Service Request match the configured display name."""
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent()

        kpis = leader._get_process_kpis(process, {})
        assert kpis[0] == expected
        assert "Process Cycle Time" not in kpis

    @patch('src.agents.leader_agent.config_manager')
    def test_leader_get_process_kpis_generic(self, mock_cm):
        """Verify generic KPIs for unknown process."""
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent()

        kpis = leader._get_process_kpis("Custom Unknown Process", {})
        assert "Process Cycle Time" in kpis
        assert len(kpis) >= 3

    @patch('src.agents.leader_agent.config_manager')
    def test_leader_get_process_kpis_from_config(self, mock_cm):
        """Verify KPIs from config override defaults."""
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent()

        process_def = {"kpis": ["Custom KPI 1", "Custom KPI 2"]}
        kpis = leader._get_process_kpis("Any Process", process_def)
        assert kpis == ["Custom KPI 1", "Custom KPI 2"]


class TestContentAgent:
    """Test ContentAgent (Saad)."""

    @patch('src.agents.content_agent.config_manager')
    @patch('src.agents.base_agent.config_manager')
    def test_content_agent_init(self, mock_base_cm, mock_cm):
        """Verify ContentAgent initializes."""
        for cm in [mock_cm, mock_base_cm]:
            cm.system_config.knowledge_dir = Path("/tmp/knowledge")
            cm.system_config.templates_dir = Path("/tmp/templates")
            cm.get_agent_config.return_value = {}

        from src.agents.content_agent import ContentAgent
        agent = ContentAgent()
        assert agent.name == "Agent 3"
        assert not hasattr(agent, "max_tokens")  # No model, so no reply limit

    @patch('src.agents.content_agent.config_manager')
    @patch('src.agents.base_agent.config_manager')
    def test_content_research_truncation_limit(self, mock_base_cm, mock_cm):
        """Verify research data truncation uses 8000 chars, not 2000 (Gap 3 fix)."""
        for cm in [mock_cm, mock_base_cm]:
            cm.system_config.knowledge_dir = Path("/tmp/knowledge")
            cm.system_config.templates_dir = Path("/tmp/templates")
            cm.get_agent_config.return_value = {}

        from src.agents.content_agent import ContentAgent
        agent = ContentAgent()

        # Create research data with content > 2000 but < 8000 chars
        long_research = "A" * 5000
        research_data = {
            "research": {"raw_research": long_research}
        }

        summary = agent._extract_research_summary(research_data)
        # Should contain all 5000 chars (was truncated to 2000 before fix)
        assert len(summary) > 4000


class TestAgentInheritance:
    """Test that all agents properly inherit from BaseAgent."""

    def test_all_agents_inherit_base(self):
        """Verify all agent classes inherit from BaseAgent."""
        from src.agents.base_agent import BaseAgent
        from src.agents import (
            ContentAgent, ReviewAgent, FormatAgent,
            SecretaryAgent, BuildingDesignAgent, EUCAgent
        )

        agents = [
            ContentAgent, ReviewAgent, FormatAgent,
            SecretaryAgent, BuildingDesignAgent, EUCAgent
        ]

        for agent_cls in agents:
            assert issubclass(agent_cls, BaseAgent), \
                f"{agent_cls.__name__} must inherit from BaseAgent"

    def test_all_agents_have_required_attributes(self):
        """Verify all agents define required class attributes."""
        from src.agents import (
            ContentAgent, ReviewAgent, FormatAgent,
            SecretaryAgent, BuildingDesignAgent, EUCAgent
        )

        agents = [
            ContentAgent, ReviewAgent, FormatAgent,
            SecretaryAgent, BuildingDesignAgent, EUCAgent
        ]

        for agent_cls in agents:
            assert hasattr(agent_cls, 'AGENT_NAME'), f"{agent_cls.__name__} missing AGENT_NAME"
            assert hasattr(agent_cls, 'AGENT_ROLE'), f"{agent_cls.__name__} missing AGENT_ROLE"
            assert hasattr(agent_cls, 'CONFIG_KEY'), f"{agent_cls.__name__} missing CONFIG_KEY"
            assert agent_cls.AGENT_NAME != "Agent", \
                f"{agent_cls.__name__} must override AGENT_NAME"


class TestFormatAgent:
    """Test FormatAgent (Bee) — special case, no API client."""

    @patch('src.agents.format_agent.config_manager')
    @patch('src.agents.base_agent.config_manager')
    def test_format_agent_has_no_client(self, mock_base_cm, mock_cm):
        """Verify FormatAgent has no model client."""
        for cm in [mock_cm, mock_base_cm]:
            cm.system_config.knowledge_dir = Path("/tmp/knowledge")
            cm.system_config.output_dir = Path("/tmp/output")
            cm.get_agent_config.return_value = {}

        from src.agents.format_agent import FormatAgent
        agent = FormatAgent()
        assert agent.name == "Agent 5"
        assert not hasattr(agent, "client")
