"""BaseAgent - Shared base class for all REEMA agents."""

from typing import Dict, List, Optional
from pathlib import Path
from anthropic import AsyncAnthropic as Anthropic
from ..utils.provider import AnthropicProvider, RunRuntime, current_runtime
from ..knowledge.retrieval import EVIDENCE_POLICY, evidence_block, make_chunks, retrieve
from ..utils.logger import logger
from ..utils.config import config_manager, selected_model


class BaseAgent:
    """
    Base class for all REEMA agents.

    Provides shared functionality:
    - Anthropic client initialization
    - Knowledge base loading
    - Claude API calls
    - Section extraction from responses
    - Timestamp generation
    - Config-driven settings

    The numbered specialist agents and coordinator Ahmad inherit from this class.
    """

    # Subclasses should override these
    AGENT_NAME: str = "Agent"
    AGENT_ROLE: str = "Base Agent"
    CONFIG_KEY: str = ""  # Key in agent_config.yaml
    KNOWLEDGE_FILE: str = ""  # Filename in knowledge_dir
    DEFAULT_MAX_TOKENS: int = 4096
    DEFAULT_TEMPERATURE: float = 0.7

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the agent with API key and configuration."""
        self.api_key = api_key if api_key is not None else config_manager.system_config.anthropic_api_key
        self.name = self.AGENT_NAME

        # Load config from agent_config.yaml if available
        self._agent_config = {}
        if self.CONFIG_KEY:
            self._agent_config = config_manager.get_agent_config(self.CONFIG_KEY)

        # Set model from config or system defaults
        self.model = selected_model(config_manager.system_config, self._agent_config)
        self.max_tokens = self._agent_config.get(
            "max_tokens",
            self.DEFAULT_MAX_TOKENS
        )
        self.temperature = self._agent_config.get(
            "temperature",
            self.DEFAULT_TEMPERATURE
        )

        # Initialize Anthropic client (skip for agents that don't need it, like Bee)
        self.client = None
        if self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key, max_retries=0)
            except Exception:
                pass  # Some agents (FormatAgent) don't need API client

        # Knowledge base
        self.knowledge_base = ""
        self.knowledge_records = []
        self.source_records = []
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
                self.knowledge_records = make_chunks(knowledge_path, self.KNOWLEDGE_FILE, "internal")
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

    async def _call_claude(self, messages: List[Dict], system: str = "", max_tokens: int = None) -> str:
        """Make a call to Claude API.

        Args:
            messages: Conversation messages
            system: System prompt
            max_tokens: Override default max_tokens

        Returns:
            Response text from Claude
        """
        active_runtime = current_runtime.get()
        if not (active_runtime and active_runtime.settings.allow_external_ai) and not config_manager.system_config.allow_external_ai:
            raise PermissionError("External AI is disabled. Authorize this input with --allow-external-ai or ALLOW_EXTERNAL_AI=true.")
        if not self.client:
            raise RuntimeError(f"{self.name} has no Anthropic client configured")

        try:
            runtime = current_runtime.get() or RunRuntime(config_manager.system_config)
            messages = [dict(message) for message in messages]
            query = " ".join(str(message["content"]) for message in messages)
            budget = runtime.settings.knowledge_context_chars
            records = retrieve(self.source_records, query, budget // 2)
            records += retrieve(self.knowledge_records, query, budget // 2)
            if records:
                messages[-1]["content"] += evidence_block(records)
                for record in records:
                    runtime.sources[record["id"]] = {**runtime.sources.get(record["id"], {}), **{key: value for key, value in record.items() if key != "text"}}
            return await runtime.call(
                AnthropicProvider(self.client), agent=self.name, model=self.model,
                max_tokens=max_tokens or self.max_tokens, temperature=self.temperature,
                system=(system + f"\n\nCurrent agent display name: {self.name}. "
                        "Historical names in knowledge sources are not current agent names.\n\n"
                        + EVIDENCE_POLICY), messages=messages,
            )
        except Exception as e:
            logger.error(f"Claude API error: {e}", agent=self.name)
            raise

    async def close(self):
        if self.client is not None:
            await self.client.close()

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
