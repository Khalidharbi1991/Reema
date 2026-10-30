"""Integration tests for the REEMA pipeline."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path


class TestPipelineStructure:
    """Test the full pipeline structure."""

    @patch('src.agents.leader_agent.config_manager')
    @pytest.mark.asyncio
    async def test_full_pipeline_calls_all_phases(self, mock_cm, tmp_path, sample_sop_content):
        """Verify generate_documentation calls all 6+ phases."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"
        mock_cm.system_config.default_formats = ["markdown"]
        mock_cm.get_process_definition.return_value = {}
        mock_cm.get_standards_for_process.return_value = []
        mock_cm.resolve_process.return_value = ("test", {"name": "Test", "specialists": []})
        mock_cm.system_config.output_dir = tmp_path
        mock_cm.system_config.allow_external_ai = True
        from src.utils.config import SystemConfig
        mock_cm.system_config = SystemConfig(_env_file=None, project_root=tmp_path, output_dir=tmp_path, allow_external_ai=True)
        # Recovery identity needs real serializable catalog snapshots.
        from src.utils.config import config_manager
        for field in ("agents_config", "process_definitions", "standards_mapping", "assistant_routing", "document_profile", "specialist_policy"):
            setattr(mock_cm, field, getattr(config_manager, field))

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")
        for name in ("ResearchAgent", "StandardsAgent", "ContentAgent", "ReviewAgent", "FormatAgent"):
            leader.register_worker(name, MagicMock())
        output = tmp_path / "test.md"
        output.write_text(sample_sop_content)

        # Patch all coordination methods
        leader._plan_workflow = AsyncMock(return_value={
            "process_name": "Test", "applicable_standards": [], "kpis": [],
            "phases": [], "process_definition": {}
        })
        async def research(name, workflow):
            leader.context["control_register"] = {"controls": []}
            return {}
        leader._coordinate_research = AsyncMock(side_effect=research)
        leader.worker_agents["FormatAgent"].last_export_checks = {}
        leader._coordinate_content_generation = AsyncMock(return_value="SOP content")
        leader._coordinate_enrichment = AsyncMock(return_value=sample_sop_content)
        async def reviewed(content):
            leader.context["last_review"] = {"quality_score": 90}
            return content
        leader._coordinate_review = AsyncMock(side_effect=reviewed)
        leader._coordinate_compliance_validation = AsyncMock(return_value=sample_sop_content)
        leader._coordinate_formatting = AsyncMock(return_value={"markdown": str(output)})
        leader._coordinate_delivery = AsyncMock(return_value={"status": "awaiting_human_approval"})

        result = await leader.generate_documentation("Test Process", ["markdown"])

        # Verify all phases were called
        leader._plan_workflow.assert_called_once()
        leader._coordinate_research.assert_called_once()
        leader._coordinate_content_generation.assert_called_once()
        leader._coordinate_enrichment.assert_called_once()        # Phase 3b
        leader._coordinate_review.assert_called_once()             # Phase 4a
        leader._coordinate_compliance_validation.assert_called_once()  # Phase 4b
        leader._coordinate_formatting.assert_called_once()         # Phase 5
        leader._coordinate_delivery.assert_called_once()           # Phase 6

    @patch('src.agents.leader_agent.config_manager')
    @pytest.mark.asyncio
    async def test_enrichment_phase_calls_layla_and_rakan(self, mock_cm):
        """Verify Phase 3b calls Layla's dashboard design and Rakan's access content."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")
        leader.context = {"workflow": {"kpis": ["KPI1"]}, "specialists": ["data", "access"]}

        # Mock DataAgent (Layla) with create_dashboard_design
        mock_data = MagicMock()
        mock_data.create_dashboard_design = AsyncMock(return_value={
            "dashboard_design": "Power BI Dashboard layout..."
        })
        leader.worker_agents["DataAgent"] = mock_data

        # Mock AccessAgent (Rakan) with generate_access_content
        mock_access = MagicMock()
        mock_access.generate_access_content = AsyncMock(return_value={
            "access_content": "IAM requirements..."
        })
        leader.worker_agents["AccessAgent"] = mock_access

        result = await leader._coordinate_enrichment(
            "Incident Management",
            "Original SOP content",
            {"access": {"analysis": "test"}}
        )

        # Both should be called
        mock_data.create_dashboard_design.assert_called_once()
        mock_access.generate_access_content.assert_called_once()

        # Result should include both appendices
        assert "Power BI Dashboard" in result
        assert "Access Management" in result

    @patch('src.agents.leader_agent.config_manager')
    @pytest.mark.asyncio
    async def test_delivery_phase_requires_human(self, mock_cm, tmp_path):
        """Phase 6 never grants AI approval, even when legacy roles are registered."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")
        leader.context = {"last_review": {"quality_score": 90}, "run_dir": str(tmp_path)}
        output = tmp_path / "test.md"
        output.write_text("Draft document")

        # Ahmad as a spec'd fake: any call to a real SecretaryAgent method is recorded
        from src.agents.secretary_agent import SecretaryAgent
        mock_secretary = MagicMock(spec=SecretaryAgent)
        leader.register_worker("SecretaryAgent", mock_secretary)

        result = await leader._coordinate_delivery(
            "Incident Management",
            {"markdown": str(output)}
        )

        assert mock_secretary.mock_calls == []
        assert result["delivery_status"] == "awaiting_human_approval"
        assert Path(result["approval_record"]).is_file()


class TestAllAgentsImportable:
    """Test all agents can be imported."""

    def test_all_agents_importable(self):
        """Verify active classes can be imported from src.agents."""
        from src.agents import (
            BaseAgent,
            LeaderAgent,
            SecretaryAgent,
            ResearchAgent,
            StandardsAgent,
            ContentAgent,
            ReviewAgent,
            FormatAgent,
            DataAgent,
            AccessAgent,
            ProblemAgent,
            BuildingDesignAgent,
            EUCAgent,
        )

        classes = [
            BaseAgent, LeaderAgent, SecretaryAgent,
            ResearchAgent, StandardsAgent, ContentAgent,
            ReviewAgent, FormatAgent, DataAgent, AccessAgent, ProblemAgent,
            BuildingDesignAgent, EUCAgent
        ]

        assert len(classes) == 13  # BaseAgent plus the twelve active roles.
        for cls in classes:
            assert cls is not None
            assert hasattr(cls, '__name__')

    def test_agents_have_correct_names(self):
        """Verify agent names match expected team members."""
        from src.agents import (
            LeaderAgent, SecretaryAgent,
            ResearchAgent, StandardsAgent, ContentAgent,
            ReviewAgent, FormatAgent, DataAgent, AccessAgent,
            ProblemAgent, BuildingDesignAgent, EUCAgent,
        )

        expected = {
            SecretaryAgent: "Ahmad",
            LeaderAgent: None,  # LeaderAgent doesn't use AGENT_NAME
            ResearchAgent: "Agent 1",
            StandardsAgent: "Agent 2",
            ContentAgent: "Agent 3",
            ReviewAgent: "Agent 4",
            FormatAgent: "Agent 5",
            AccessAgent: "Agent 6",
            ProblemAgent: "Agent 7",
            DataAgent: "Agent 8",
            BuildingDesignAgent: "Agent 9",
            EUCAgent: "Agent 10",
        }

        for agent_cls, expected_name in expected.items():
            if expected_name is not None:
                assert agent_cls.AGENT_NAME == expected_name, \
                    f"{agent_cls.__name__}.AGENT_NAME should be '{expected_name}'"


class TestPipelinePhaseOrder:
    """Test that phases execute in correct order."""

    @patch('src.agents.leader_agent.config_manager')
    @pytest.mark.asyncio
    async def test_content_receives_research_data(self, mock_cm, tmp_path, sample_sop_content):
        """Verify Phase 3a receives Phase 2 research data."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.leader_model = "claude-sonnet-4-6"
        mock_cm.system_config.default_formats = ["markdown"]
        mock_cm.get_process_definition.return_value = {}
        mock_cm.get_standards_for_process.return_value = []
        mock_cm.resolve_process.return_value = ("test", {"name": "Test", "specialists": []})
        mock_cm.system_config.output_dir = tmp_path
        mock_cm.system_config.allow_external_ai = True
        from src.utils.config import SystemConfig
        mock_cm.system_config = SystemConfig(_env_file=None, project_root=tmp_path, output_dir=tmp_path, allow_external_ai=True)
        # Recovery identity needs real serializable catalog snapshots.
        from src.utils.config import config_manager
        for field in ("agents_config", "process_definitions", "standards_mapping", "assistant_routing", "document_profile", "specialist_policy"):
            setattr(mock_cm, field, getattr(config_manager, field))

        from src.agents.leader_agent import LeaderAgent
        leader = LeaderAgent(api_key="test-key")
        for name in ("ResearchAgent", "StandardsAgent", "ContentAgent", "ReviewAgent", "FormatAgent"):
            leader.register_worker(name, MagicMock())
        output = tmp_path / "test.md"
        output.write_text(sample_sop_content)

        # Track data flow
        phase_data = {}

        async def mock_research(name, workflow):
            leader.context["control_register"] = {"controls": []}
            phase_data["research"] = {"research": {"raw_research": "test"}}
            return phase_data["research"]

        async def mock_content(name, research_data):
            phase_data["content_received"] = research_data
            return "SOP content"

        leader._plan_workflow = AsyncMock(return_value={
            "process_name": "Test", "applicable_standards": [], "kpis": [],
            "phases": [], "process_definition": {}
        })
        leader._coordinate_research = mock_research
        leader._coordinate_content_generation = mock_content
        leader._coordinate_enrichment = AsyncMock(return_value=sample_sop_content)
        async def reviewed(content):
            leader.context["last_review"] = {"quality_score": 90}
            return content
        leader._coordinate_review = AsyncMock(side_effect=reviewed)
        leader._coordinate_compliance_validation = AsyncMock(return_value=sample_sop_content)
        leader._coordinate_formatting = AsyncMock(return_value={"markdown": str(output)})
        leader.worker_agents["FormatAgent"].last_export_checks = {}
        leader._coordinate_delivery = AsyncMock(return_value={})

        await leader.generate_documentation("Test", ["markdown"])

        # Content generation should have received research data
        assert "content_received" in phase_data
        assert "research" in phase_data["content_received"]
