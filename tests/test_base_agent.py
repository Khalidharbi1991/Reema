"""Tests for BaseAgent shared functionality."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestBaseAgent:
    """Test BaseAgent class."""

    def test_base_agent_class_exists(self):
        """Verify BaseAgent can be imported."""
        from src.agents.base_agent import BaseAgent
        assert BaseAgent is not None

    def test_base_agent_class_attributes(self):
        """Verify default class attributes."""
        from src.agents.base_agent import BaseAgent
        assert BaseAgent.AGENT_NAME == "Agent"
        assert BaseAgent.AGENT_ROLE == "Base Agent"
        assert BaseAgent.CONFIG_KEY == ""
        assert BaseAgent.KNOWLEDGE_FILE == ""
        assert BaseAgent.DEFAULT_MAX_TOKENS == 4096
        assert BaseAgent.DEFAULT_TEMPERATURE == 0.7

    @patch('src.agents.base_agent.config_manager')
    @patch('src.agents.base_agent.Anthropic')
    def test_base_agent_init(self, mock_anthropic, mock_cm):
        """Verify BaseAgent initializes correctly."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.worker_model = "claude-sonnet-4-6"
        mock_cm.system_config.knowledge_dir = Path("/tmp/knowledge")
        mock_cm.get_agent_config.return_value = {}

        from src.agents.base_agent import BaseAgent
        agent = BaseAgent(api_key="test-key")
        assert agent.name == "Agent"
        assert agent.api_key == "test-key"
        assert agent.knowledge_base == ""

    @patch('src.agents.base_agent.config_manager')
    @patch('src.agents.base_agent.Anthropic')
    def test_inject_knowledge(self, mock_anthropic, mock_cm):
        """Verify _inject_knowledge appends knowledge to prompt."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.worker_model = "claude-sonnet-4-6"
        mock_cm.system_config.knowledge_dir = Path("/tmp/knowledge")
        mock_cm.get_agent_config.return_value = {}

        from src.agents.base_agent import BaseAgent
        agent = BaseAgent(api_key="test-key")
        agent.knowledge_base = "Sample knowledge content"

        result = agent._inject_knowledge("Base prompt")
        assert "Base prompt" in result
        assert "Sample knowledge content" not in result
        assert "untrusted data" in result

    @patch('src.agents.base_agent.config_manager')
    @patch('src.agents.base_agent.Anthropic')
    def test_inject_knowledge_empty(self, mock_anthropic, mock_cm):
        """Verify _inject_knowledge returns base prompt when no knowledge."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.worker_model = "claude-sonnet-4-6"
        mock_cm.system_config.knowledge_dir = Path("/tmp/knowledge")
        mock_cm.get_agent_config.return_value = {}

        from src.agents.base_agent import BaseAgent
        agent = BaseAgent(api_key="test-key")
        agent.knowledge_base = ""

        result = agent._inject_knowledge("Base prompt only")
        assert result.startswith("Base prompt only")
        assert "untrusted data" in result

    @patch('src.agents.base_agent.config_manager')
    @patch('src.agents.base_agent.Anthropic')
    def test_extract_sections(self, mock_anthropic, mock_cm):
        """Verify _extract_sections parses markdown headers."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.worker_model = "claude-sonnet-4-6"
        mock_cm.system_config.knowledge_dir = Path("/tmp/knowledge")
        mock_cm.get_agent_config.return_value = {}

        from src.agents.base_agent import BaseAgent
        agent = BaseAgent(api_key="test-key")

        response = """## Introduction
This is the intro.

## Procedures
Step 1: Do this.
Step 2: Do that.

## Conclusion
Final thoughts."""

        sections = agent._extract_sections(response)
        assert "Introduction" in sections
        assert "Procedures" in sections
        assert "Conclusion" in sections
        assert "Step 1" in sections["Procedures"]

    @patch('src.agents.base_agent.config_manager')
    @patch('src.agents.base_agent.Anthropic')
    def test_get_timestamp(self, mock_anthropic, mock_cm):
        """Verify _get_timestamp returns ISO format."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.worker_model = "claude-sonnet-4-6"
        mock_cm.system_config.knowledge_dir = Path("/tmp/knowledge")
        mock_cm.get_agent_config.return_value = {}

        from src.agents.base_agent import BaseAgent
        agent = BaseAgent(api_key="test-key")
        ts = agent._get_timestamp()
        assert "T" in ts  # ISO format includes T separator
        assert len(ts) > 10

    @patch('src.agents.base_agent.config_manager')
    @patch('src.agents.base_agent.Anthropic')
    def test_get_config_value(self, mock_anthropic, mock_cm):
        """Verify get_config_value reads from agent config."""
        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.worker_model = "claude-sonnet-4-6"
        mock_cm.system_config.knowledge_dir = Path("/tmp/knowledge")
        mock_cm.get_agent_config.return_value = {"quality_threshold": 85}

        from src.agents.base_agent import BaseAgent

        class TestAgent(BaseAgent):
            CONFIG_KEY = "test_agent"

        agent = TestAgent(api_key="test-key")
        assert agent.get_config_value("quality_threshold") == 85
        assert agent.get_config_value("missing_key", "default") == "default"

    @patch('src.agents.base_agent.config_manager')
    @patch('src.agents.base_agent.Anthropic')
    def test_knowledge_base_loading(self, mock_anthropic, mock_cm, tmp_path):
        """Verify knowledge base loads from file."""
        # Create a temp knowledge file
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        kb_file = knowledge_dir / "test_knowledge.md"
        kb_file.write_text("# Test Knowledge\nThis is test content.")

        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.worker_model = "claude-sonnet-4-6"
        mock_cm.system_config.knowledge_dir = knowledge_dir
        mock_cm.get_agent_config.return_value = {}

        from src.agents.base_agent import BaseAgent

        class TestAgent(BaseAgent):
            KNOWLEDGE_FILE = "test_knowledge.md"

        agent = TestAgent(api_key="test-key")
        assert "Test Knowledge" in agent.knowledge_base

    @patch('src.agents.base_agent.config_manager')
    @patch('src.agents.base_agent.Anthropic')
    def test_knowledge_base_missing_graceful(self, mock_anthropic, mock_cm, tmp_path):
        """Verify missing knowledge file is handled gracefully."""
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()

        mock_cm.system_config.anthropic_api_key = "test-key"
        mock_cm.system_config.worker_model = "claude-sonnet-4-6"
        mock_cm.system_config.knowledge_dir = knowledge_dir
        mock_cm.get_agent_config.return_value = {}

        from src.agents.base_agent import BaseAgent

        class TestAgent(BaseAgent):
            KNOWLEDGE_FILE = "nonexistent_file.md"

        agent = TestAgent(api_key="test-key")
        assert agent.knowledge_base == ""
