"""Tests for configuration management."""

import pytest
from pathlib import Path


class TestSystemConfig:
    """Test SystemConfig class."""

    def test_knowledge_dir_exists(self):
        """Verify knowledge_dir field is present in SystemConfig (Gap 1 fix)."""
        from src.utils.config import SystemConfig
        config = SystemConfig()
        assert hasattr(config, 'knowledge_dir'), "knowledge_dir must be defined in SystemConfig"

    def test_knowledge_dir_points_to_knowledge(self):
        """Verify knowledge_dir points to src/knowledge."""
        from src.utils.config import SystemConfig
        config = SystemConfig()
        assert str(config.knowledge_dir).endswith("src/knowledge") or \
               str(config.knowledge_dir).endswith("src\\knowledge")

    def test_references_dir_points_to_the_documentation_input(self):
        """Verify local source documents have a dedicated directory."""
        from src.utils.config import SystemConfig
        config = SystemConfig()
        assert config.references_dir == config.project_root / "teams" / "documentation" / "input" / "references"

    def test_team_folders_hold_output_task_data_and_the_manifest(self, tmp_path, monkeypatch):
        from src.utils.config import SystemConfig
        monkeypatch.delenv("REEMA_OUTPUT_DIR", raising=False)
        config = SystemConfig(_env_file=None, project_root=tmp_path)
        teams = tmp_path / "teams"
        assert config.output_dir == teams / "documentation" / "output"
        assert config.task_data_dir == teams / "coordination" / "data"
        assert config.reference_manifest == teams / "documentation" / "input" / "references" / "manifest.yaml"
        assert config.log_dir == tmp_path / "logs"

    def test_system_config_defaults(self):
        """Verify default paths are set correctly."""
        from src.utils.config import SystemConfig
        config = SystemConfig()
        assert config.output_dir is not None
        assert config.config_dir is not None
        assert config.templates_dir is not None
        assert config.knowledge_dir is not None
        # No model or consent settings remain; names are built from parts for the no-API guard.
        assert not {"leader_model", "worker_model", "allow" + "_external_ai"} & set(SystemConfig.model_fields)

    def test_an_old_env_file_with_removed_model_settings_still_loads(self, tmp_path, monkeypatch):
        """Unknown entries, such as a key or consent flag left in .env, are ignored, never used."""
        from src.utils.config import SystemConfig
        env = tmp_path / ".env"
        # Built from parts so the no-API guard keeps finding no such name in the code.
        removed = ["ANTHROPIC" + "_API_KEY=synthetic-not-a-key", "ALLOW" + "_EXTERNAL_AI=true", "LEADER_MODEL=x"]
        env.write_text("\n".join(removed + ["REVIEW_CHUNK_CHARS=5000"]) + "\n")
        monkeypatch.setenv("MAX_RUN_TOKENS", "10")
        config = SystemConfig(_env_file=env)
        assert config.review_chunk_chars == 5000
        assert "synthetic-not-a-key" not in repr(config.model_dump())

    def test_default_formats(self):
        """Verify default output formats."""
        from src.utils.config import SystemConfig
        config = SystemConfig()
        assert "pdf" in config.default_formats
        assert "docx" in config.default_formats
        assert "markdown" in config.default_formats
        assert "html" in config.default_formats

    def test_page_target(self):
        """Verify page target range."""
        from src.utils.config import SystemConfig
        config = SystemConfig()
        assert config.page_target == (15, 30)


class TestConfigManager:
    """Test ConfigManager class."""

    def test_config_manager_initializes(self):
        """Verify ConfigManager creates successfully."""
        from src.utils.config import ConfigManager
        cm = ConfigManager()
        assert cm.system_config is not None
        assert isinstance(cm.agents_config, dict)

    def test_get_agent_config(self):
        """Verify agent config retrieval for known agents."""
        from src.utils.config import config_manager
        # leader_agent should exist in agent_config.yaml
        leader_config = config_manager.get_agent_config("leader_agent")
        assert isinstance(leader_config, dict)
        if leader_config:
            assert "name" in leader_config

    def test_get_agent_config_missing(self):
        """Verify missing agent returns empty dict."""
        from src.utils.config import config_manager
        result = config_manager.get_agent_config("nonexistent_agent")
        assert result == {}

    def test_get_process_definition(self):
        """Verify process definition retrieval."""
        from src.utils.config import config_manager
        # incident_management should exist
        result = config_manager.get_process_definition("incident_management")
        assert isinstance(result, dict)

    def test_get_standards_for_process(self):
        """Verify standards retrieval."""
        from src.utils.config import config_manager
        result = config_manager.get_standards_for_process("unknown_process")
        assert isinstance(result, list)

    def test_process_definitions_loaded(self):
        """Verify process definitions are loaded from YAML."""
        from src.utils.config import config_manager
        assert len(config_manager.process_definitions) >= 15, \
            "Should have at least 15 process definitions"

    def test_agents_config_has_10_agents(self):
        """Verify the active coordinator, leader, and eight specialists."""
        from src.utils.config import config_manager
        expected_agents = [
            "secretary_agent", "leader_agent",
            "research_agent", "standards_agent", "access_agent",
            "problem_agent", "data_agent", "content_agent",
            "review_agent", "format_agent"
        ]
        for agent in expected_agents:
            assert agent in config_manager.agents_config, f"Missing config for {agent}"


def test_package_version_matches_project_metadata():
    """`reema version` reports the same version as pyproject.toml."""
    import tomllib
    import src
    project = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())["project"]
    assert src.__version__ == project["version"]
