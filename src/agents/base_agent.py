"""BaseAgent - Shared base class for all REEMA agents."""

from typing import Dict, List
from ..knowledge.retrieval import EVIDENCE_POLICY
from ..utils.logger import logger
from ..utils.config import config_manager


class BaseAgent:
    """
    Base class for all REEMA agents.

    Provides shared functionality:
    - Knowledge base loading
    - The reply hook that the file-backed Claude Code workers fill in
    - Section extraction from responses
    - Timestamp generation
    - Config-driven settings

    REEMA makes no model call: the text comes from files a Claude Code session wrote
    (src/agents/file_workers.py).
    """

    # Subclasses should override these
    AGENT_NAME: str = "Agent"
    AGENT_ROLE: str = "Base Agent"
    CONFIG_KEY: str = ""  # Key in agent_config.yaml
    KNOWLEDGE_FILE: str = ""  # Filename in knowledge_dir

    def __init__(self):
        """Initialize the agent from its configuration."""
        self.name = self.AGENT_NAME

        # Load config from agent_config.yaml if available
        self._agent_config = {}
        if self.CONFIG_KEY:
            self._agent_config = config_manager.get_agent_config(self.CONFIG_KEY)

        # Knowledge base
        self.knowledge_base = ""
        if self.KNOWLEDGE_FILE:
            self._load_knowledge_base()

        logger.info(f"{self.AGENT_ROLE} initialized", agent=self.name)

    def _load_knowledge_base(self):
        """Load the agent's knowledge base from file."""
        try:
            knowledge_path = config_manager.system_config.knowledge_dir / self.KNOWLEDGE_FILE
            if knowledge_path.exists():
                with open(knowledge_path, 'r', encoding='utf-8') as f:
                    self.knowledge_base = f.read()
                logger.info(f"{self.name}'s knowledge base loaded", agent=self.name)
            else:
                self.knowledge_base = ""
                logger.warning(f"{self.name}'s knowledge file not found: {self.KNOWLEDGE_FILE}", agent=self.name)
        except Exception as e:
            logger.warning(f"Could not load {self.name}'s knowledge: {e}", agent=self.name)
            self.knowledge_base = ""

    def _inject_knowledge(self, system_prompt: str, knowledge_intro: str = "") -> str:
        """Inject knowledge base into system prompt.

        Args:
            system_prompt: Base system prompt
            knowledge_intro: Optional intro text for the knowledge section

        Returns:
            System prompt with knowledge base appended
        """
        # Source text is deliberately not promoted into the system instructions.
        # Selection occurs at call time using the actual task, not the agent title.
        return system_prompt + "\n\n" + EVIDENCE_POLICY

    async def _reply(self, messages: List[Dict], system: str = "") -> str:
        """The text written for this request in a Claude Code session.

        Only the file-backed workers (src/agents/file_workers.py) supply it; REEMA itself
        never calls a model.
        """
        raise RuntimeError(f"{self.name} has no Claude Code file for this request; REEMA makes no model call")

    async def close(self):
        """Nothing to release; kept so callers can close any worker."""

    def _extract_sections(self, response: str) -> Dict[str, str]:
        """Extract sections from a response with markdown headers.

        Supports both ## headers and **bold** section markers.

        Args:
            response: Text response to parse

        Returns:
            Dictionary of section_name -> section_content
        """
        sections = {}
        current_section = None
        current_content = []

        for line in response.split('\n'):
            stripped = line.strip()

            # Detect ## headers
            if stripped.startswith('##'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = stripped.strip('#').strip()
                current_content = []
            # Detect **bold** section headers
            elif stripped.startswith('**') and stripped.endswith('**') and len(stripped) > 4:
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = stripped.strip('*').strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)

        # Add last section
        if current_section:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _get_timestamp(self) -> str:
        """Get current ISO timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()

    def get_config_value(self, key: str, default=None):
        """Get a value from the agent's config.

        Args:
            key: Config key to look up
            default: Default value if not found

        Returns:
            Config value or default
        """
        return self._agent_config.get(key, default)
