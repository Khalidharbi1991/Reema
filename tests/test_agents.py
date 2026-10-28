"""Tests for individual agent implementations."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path


class TestLeaderAgent:
    """Test LeaderAgent (Abdullah)."""

    @patch('src.agents.leader_agent.config_manager')
    @patch('src.agents.leader_agent.Anthropic')
    def test_leader_init(self, mock_anthropic, mock_cm):
        """Verify LeaderAgent initializes."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")
        assert leader.name == "Abdullah"
        assert leader.worker_agents == {}

    @patch('src.agents.leader_agent.config_manager')
    @patch('src.agents.leader_agent.Anthropic')
    def test_leader_register_worker(self, mock_anthropic, mock_cm):
        """Verify worker registration."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")

        mock_worker = MagicMock()
        leader.register_worker("TestAgent", mock_worker)
        assert "TestAgent" in leader.worker_agents

    @patch('src.agents.leader_agent.config_manager')
    @patch('src.agents.leader_agent.Anthropic')
    def test_leader_get_status(self, mock_anthropic, mock_cm):
        """Verify status dict structure."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")
        status = leader.get_status()
        assert "leader" in status
        assert "workers" in status
        assert status["leader"] == "Abdullah"

    @patch('src.agents.leader_agent.config_manager')
    @patch('src.agents.leader_agent.Anthropic')
    def test_leader_get_process_kpis_incident(self, mock_anthropic, mock_cm):
        """Verify incident-specific KPIs are returned."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")

        kpis = leader._get_process_kpis("Incident Management", {})
        assert "Mean Time to Resolve (MTTR)" in kpis
        assert "First Contact Resolution Rate" in kpis

    @patch('src.agents.leader_agent.config_manager')
    @patch('src.agents.leader_agent.Anthropic')
    def test_leader_get_process_kpis_access(self, mock_anthropic, mock_cm):
        """Verify access-specific KPIs are returned."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")

        kpis = leader._get_process_kpis("Access Management", {})
        assert "Access Request Fulfillment Time" in kpis
        assert "MFA Adoption Rate" in kpis

    @patch('src.agents.leader_agent.config_manager')
    @patch('src.agents.leader_agent.Anthropic')
    def test_leader_get_process_kpis_generic(self, mock_anthropic, mock_cm):
        """Verify generic KPIs for unknown process."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")

        kpis = leader._get_process_kpis("Custom Unknown Process", {})
        assert "Process Cycle Time" in kpis
        assert len(kpis) >= 3

    @patch('src.agents.leader_agent.config_manager')
    @patch('src.agents.leader_agent.Anthropic')
    def test_leader_get_process_kpis_from_config(self, mock_anthropic, mock_cm):
        """Verify KPIs from config override defaults."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")

        process_def = {"kpis": ["Custom KPI 1", "Custom KPI 2"]}
        kpis = leader._get_process_kpis("Any Process", process_def)
        assert kpis == ["Custom KPI 1", "Custom KPI 2"]


class TestReviewLoopFixes:
    """Test the review loop bug fixes (Gap 2)."""

    @patch('src.agents.leader_agent.config_manager')
    @patch('src.agents.leader_agent.Anthropic')
    @pytest.mark.asyncio
    async def test_review_none_handling(self, mock_anthropic, mock_cm):
        """Verify content is NOT None when refined_content is None (Gap 2 fix)."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"
        mock_cm.get_agent_config.return_value = {"quality_threshold": 85}
        mock_cm.document_profile.max_review_cycles = 2

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")

        # Mock ReviewAgent that returns quality_score=90 but refined_content=None
        mock_review = MagicMock()
        mock_review.review_content = AsyncMock(return_value={
            "quality_score": 90,
            "refined_content": None,
            "feedback": [],
            "needs_revision": False
        })
        leader.worker_agents["ReviewAgent"] = mock_review

        result = await leader._coordinate_review("Original SOP content here")
        assert result is not None
        assert result == "Original SOP content here"

    @patch('src.agents.leader_agent.config_manager')
    @patch('src.agents.leader_agent.Anthropic')
    @pytest.mark.asyncio
    async def test_review_max_two_cycles(self, mock_anthropic, mock_cm):
        """Verify max 2 review cycles."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"
        mock_cm.get_agent_config.return_value = {"quality_threshold": 85}
        mock_cm.document_profile.max_review_cycles = 2

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")

        # Mock ReviewAgent that always fails
        mock_review = MagicMock()
        mock_review.review_content = AsyncMock(return_value={
            "quality_score": 50,
            "refined_content": None,
            "feedback": ["Needs work"],
            "needs_revision": True
        })
        leader.worker_agents["ReviewAgent"] = mock_review

        # Mock ContentAgent for refinement
        mock_content = MagicMock()
        mock_content.refine_content = AsyncMock(return_value="Refined content")
        leader.worker_agents["ContentAgent"] = mock_content

        with pytest.raises(ValueError, match="Quality review failed"):
            await leader._coordinate_review("Initial content")

        # Should call review_content exactly 2 times (2 cycles max)
        assert mock_review.review_content.call_count == 2

    @patch('src.agents.leader_agent.config_manager')
    @patch('src.agents.leader_agent.Anthropic')
    @pytest.mark.asyncio
    async def test_review_passes_first_cycle(self, mock_anthropic, mock_cm):
        """Verify early return when quality passes on first cycle."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"
        mock_cm.get_agent_config.return_value = {"quality_threshold": 85}
        mock_cm.document_profile.max_review_cycles = 2

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")

        mock_review = MagicMock()
        mock_review.review_content = AsyncMock(return_value={
            "quality_score": 92,
            "refined_content": "Polished content",
            "feedback": [],
            "needs_revision": False
        })
        leader.worker_agents["ReviewAgent"] = mock_review

        result = await leader._coordinate_review("Content")
        assert mock_review.review_content.call_count == 2  # A reviewer rewrite requires its own review.
        assert result == "Polished content"


class TestContentAgent:
    """Test ContentAgent (Saad)."""

    @patch('src.agents.content_agent.config_manager')
    @patch('src.agents.base_agent.config_manager')
    @patch('src.agents.base_agent.Anthropic')
    def test_content_agent_init(self, mock_anthropic, mock_base_cm, mock_cm):
        """Verify ContentAgent initializes."""
        for cm in [mock_cm, mock_base_cm]:
            cm.system_config.anthropic_api_key = "test-key"
            cm.system_config.worker_model = "claude-sonnet-4-6"
            cm.system_config.knowledge_dir = Path("/tmp/knowledge")
            cm.system_config.templates_dir = Path("/tmp/templates")
            cm.get_agent_config.return_value = {}

        from src.agents.content_agent import ContentAgent
        agent = ContentAgent(api_key="test-key")
        assert agent.name == "Agent 3"
        assert agent.max_tokens == 16000  # Per-section reply limit

    @patch('src.agents.content_agent.config_manager')
    @patch('src.agents.base_agent.config_manager')
    @patch('src.agents.base_agent.Anthropic')
    def test_content_research_truncation_limit(self, mock_anthropic, mock_base_cm, mock_cm):
        """Verify research data truncation uses 8000 chars, not 2000 (Gap 3 fix)."""
        for cm in [mock_cm, mock_base_cm]:
            cm.system_config.anthropic_api_key = "test-key"
            cm.system_config.worker_model = "claude-sonnet-4-6"
            cm.system_config.knowledge_dir = Path("/tmp/knowledge")
            cm.system_config.templates_dir = Path("/tmp/templates")
            cm.get_agent_config.return_value = {}

        from src.agents.content_agent import ContentAgent
        agent = ContentAgent(api_key="test-key")

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
            DataAgent, AccessAgent, ResearchAgent,
            StandardsAgent, SecretaryAgent
        )

        agents = [
            ContentAgent, ReviewAgent, FormatAgent,
            DataAgent, AccessAgent, ResearchAgent,
            StandardsAgent, SecretaryAgent
        ]

        for agent_cls in agents:
            assert issubclass(agent_cls, BaseAgent), \
                f"{agent_cls.__name__} must inherit from BaseAgent"

    def test_all_agents_have_required_attributes(self):
        """Verify all agents define required class attributes."""
        from src.agents import (
            ContentAgent, ReviewAgent, FormatAgent,
            DataAgent, AccessAgent, ResearchAgent,
            StandardsAgent, SecretaryAgent
        )

        agents = [
            ContentAgent, ReviewAgent, FormatAgent,
            DataAgent, AccessAgent, ResearchAgent,
            StandardsAgent, SecretaryAgent
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
    @patch('src.agents.base_agent.Anthropic')
    def test_format_agent_no_api(self, mock_anthropic, mock_base_cm, mock_cm):
        """Verify FormatAgent works without API key."""
        for cm in [mock_cm, mock_base_cm]:
            cm.system_config.anthropic_api_key = ""
            cm.system_config.worker_model = "claude-sonnet-4-6"
            cm.system_config.knowledge_dir = Path("/tmp/knowledge")
            cm.system_config.output_dir = Path("/tmp/output")
            cm.get_agent_config.return_value = {}

        from src.agents.format_agent import FormatAgent
        agent = FormatAgent()
        assert agent.name == "Agent 5"
        # Should not have a usable Anthropic client
        assert agent.client is None or not agent.api_key
