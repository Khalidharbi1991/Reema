"""Configuration management for the multi-agent system."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import yaml


class AgentConfig(BaseModel):
    """Configuration for individual agents."""
    name: str
    role: str
    model: str = "claude-sonnet-4"
    max_tokens: int = 4096
    temperature: float = 0.7


class SystemConfig(BaseSettings):
    """Main system configuration."""
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    project_root: Path = Path(__file__).parent.parent.parent
    output_dir: Path = project_root / "output"
    config_dir: Path = project_root / "config"
    templates_dir: Path = project_root / "src" / "templates"

    # Agent settings
    leader_model: str = "claude-sonnet-4"
    worker_model: str = "claude-sonnet-4"
    max_concurrent_agents: int = 5

    # Document settings
    default_formats: list[str] = ["pdf", "docx", "markdown", "html"]
    page_target: tuple[int, int] = (15, 30)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class ConfigManager:
    """Manages configuration loading and access."""

    def __init__(self):
        self.system_config = SystemConfig()
        self.agents_config = {}
        self.process_definitions = {}
        self.standards_mapping = {}
        self._load_configs()

    def _load_configs(self):
        """Load all configuration files."""
        config_dir = self.system_config.config_dir

        # Load agent configurations
        agent_config_path = config_dir / "agent_config.yaml"
        if agent_config_path.exists():
            with open(agent_config_path, 'r') as f:
                self.agents_config = yaml.safe_load(f)

        # Load process definitions
        process_def_path = config_dir / "process_definitions.yaml"
        if process_def_path.exists():
            with open(process_def_path, 'r') as f:
                self.process_definitions = yaml.safe_load(f)

        # Load standards mapping
        standards_path = config_dir / "standards_mapping.yaml"
        if standards_path.exists():
            with open(standards_path, 'r') as f:
                self.standards_mapping = yaml.safe_load(f)

    def get_agent_config(self, agent_name: str) -> dict:
        """Get configuration for a specific agent."""
        return self.agents_config.get(agent_name, {})

    def get_process_definition(self, process_name: str) -> dict:
        """Get definition for a specific IT process."""
        return self.process_definitions.get(process_name, {})

    def get_standards_for_process(self, process_name: str) -> list:
        """Get applicable standards for a process."""
        return self.standards_mapping.get(process_name, [])


# Global configuration instance
config_manager = ConfigManager()
