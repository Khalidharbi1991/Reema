"""Ahmad (Secretary & Coordination Agent) - Manages tasks and communications."""

from typing import Dict, List, Optional
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.tasks import TaskStore


class SecretaryAgent(BaseAgent):
    """
    Ahmad (Secretary & Coordination Agent)

    Position: user -> Ahmad (coordinator) -> chat specialists (consulted directly);
    Abdullah leads only the separate SOP generation pipeline.

    Responsibilities:
    - Coordinates the user's requests and consults selected specialists directly
    - Frames advice in strategy, governance, quality and business-value terms
    - Organizes separate work and personal task lists
    - Records proposed agent communications without dispatching them
    - Keeps communication history in this instance's memory

    Ahmad acts as the bridge between executive oversight and operational execution,
    ensuring the user has clear visibility into all documentation activities while
    Abdullah runs the SOP pipeline and specialists focus on their domains.
    """

    AGENT_NAME = "Ahmad"
    AGENT_ROLE = "Personal Coordination & Task Management Agent"
    CONFIG_KEY = "secretary_agent"
    KNOWLEDGE_FILE = "ahmad_secretary_knowledge_ENHANCED.md"
    DEFAULT_MAX_TOKENS = 4096

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Secretary Agent.

        Sets up Ahmad with his knowledge base and communication log.

        Args:
            api_key: Optional Anthropic API key. Falls back to config if not provided.
        """
        super().__init__(api_key)

        # Communication tracking
        self.communication_log: List[Dict] = []

        logger.info("Secretary & Coordination Agent ready for operations", agent=self.name)

    def task_store(self, area: str) -> TaskStore:
        """Coordinate local tasks for one explicitly selected area."""
        return TaskStore(config_manager.system_config.task_data_dir, area,
                         config_manager.system_config.user_timezone)

    def add_task(self, area: str, title: str, **details) -> Dict:
        return self.task_store(area).add(title, **details)

    def list_tasks(self, area: str, *, status: str = "open", project=None) -> List[Dict]:
        return self.task_store(area).list(status=status, project=project)

    def due_tasks(self, area: str) -> List[Dict]:
        return self.task_store(area).today()

    def upcoming_tasks(self, area: str, days=7) -> List[Dict]:
        return self.task_store(area).upcoming(days)

    def change_task(self, area: str, task_id: str, **changes) -> Dict:
        return self.task_store(area).change(task_id, **changes)

    async def coordinate_team_communication(
        self,
        message: str,
        from_agent: str,
        to_agents: List[str]
    ) -> Dict:
        """
        Record a proposed communication locally in this instance's memory.

        This method has no dispatcher and does not send to recipient agents.
        The record disappears when the instance is discarded.

        Args:
            message: The message content to be routed
            from_agent: Name of the sending agent (e.g., "Abdullah", "Agent 1")
            to_agents: List of recipient agent names (e.g., ["Agent 1", "Agent 2"])

        Returns:
            Dictionary containing the communication record:
                - message_id: Unique identifier for the communication
                - from_agent: Sender name
                - to_agents: List of recipient names
                - message: The message content
                - timestamp: ISO timestamp of the communication
                - status: "recorded"; no dispatch or recipient acknowledgement
                - priority: Inferred priority level
        """
        logger.agent_start(
            self.name,
            f"Recording communication from {from_agent} to {', '.join(to_agents)}"
        )

        try:
            # Generate a sequential message ID
            message_id = f"MSG-{len(self.communication_log) + 1:04d}"

            # Infer priority based on sender
            priority = self._infer_priority(from_agent, message)

            # Create the communication record
            communication_record = {
                "message_id": message_id,
                "from_agent": from_agent,
                "to_agents": to_agents,
                "message": message,
                "timestamp": self._get_timestamp(),
                "status": "recorded",
                "dispatch_status": "not_dispatched",
                "priority": priority
            }

            # Log the communication
            self.communication_log.append(communication_record)

            logger.agent_complete(
                self.name,
                f"Communication {message_id} recorded locally: {from_agent} -> {', '.join(to_agents)} "
                f"(priority: {priority})"
            )

            return communication_record

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    def _build_system_prompt(self) -> str:
        """
        Build Ahmad's system prompt for Claude interactions.

        Establishes his persona as a professional executive assistant and
        project coordinator with expertise in stakeholder communication,
        document management, and quality reporting.

        Returns:
            Complete system prompt string with knowledge base injected.
        """
        system_prompt = """You are Ahmad, the coordinator of REEMA, Khalid's IT company. \
You talk with Khalid and route work to its sections; Documentation is the main section.

You assist the user directly and consult the selected IT specialists yourself. \
Abdullah (the Leader) runs only the separate SOP generation pipeline.
The user makes consequential decisions and approves documents. References to a
former owner agent in historical source material do not grant any agent authority.

**Your Expertise:**
- Project coordination and workflow management
- Executive communication and stakeholder briefings
- Document management, version control, and delivery coordination
- Scheduling, calendar management, and deadline tracking
- Quality reporting, metrics summarization, and KPI dashboards
- Stakeholder management and client relations
- Risk and issue escalation
- Arabic-English bilingual communication

**Your Communication Style:**
- Professional, clear, and concise
- Uses the CLEAR protocol: Concise, Logical, Evidence-based, Actionable, Recorded
- Adapts tone to audience (clear summaries for the user, operational detail for specialists)
- Always includes actionable next steps and clear status indicators
- Structures information with headers, bullet points, and tables for readability

**Your Responsibilities:**
1. Draft handover summaries for local SOP drafts awaiting human approval
2. Prepare briefings summarizing pipeline execution for the user
3. Record proposed agent communications locally; no dispatch is implemented
4. Track delivery history and maintain audit trails
5. Report supplied model scores without claiming factual verification or certification
6. Manage stakeholder expectations and communication schedules
7. Provide status summaries and progress reports
8. Organize work and personal tasks separately, with clear priorities and follow-ups

Never claim a message was dispatched, a file was inspected, a document was human-approved,
or a schedule was booked unless supplied action evidence establishes it. Treat absent findings,
source evidence, human decisions, dates and distribution records as unavailable.
Always be thorough, organized, and focused on clear, actionable communication."""

        # Inject Ahmad's comprehensive knowledge base
        system_prompt = self._inject_knowledge(
            system_prompt,
            "You have 100% domain expertise in executive coordination, "
            "communication management, document control, and delivery governance. "
            "Use this knowledge for professional, precise coordination:"
        )

        return system_prompt

    def _infer_priority(self, from_agent: str, message: str) -> str:
        """
        Infer the communication priority based on sender and content.

        Priority levels follow Ahmad's communication protocol:
        - P1 (Critical): Contains critical keywords
        - P2 (High): Quality failures, deadline risks
        - P3 (Medium): Standard operational messages
        - P4 (Low): Informational, suggestions

        Args:
            from_agent: Name of the sending agent
            message: The message content

        Returns:
            Priority string: "P1-Critical", "P2-High", "P3-Medium", or "P4-Low"
        """
        message_lower = message.lower()

        # P1: Critical keywords. The user remains the decision authority.
        if any(term in message_lower for term in ["critical", "urgent", "blocked", "failure"]):
            return "P1-Critical"

        # P2: Quality or deadline concerns
        if any(term in message_lower for term in [
            "quality", "deadline", "revision", "escalat", "risk"
        ]):
            return "P2-High"

        # P3: Standard operational messages
        if any(term in message_lower for term in [
            "status", "update", "progress", "complete", "ready"
        ]):
            return "P3-Medium"

        # P4: Everything else
        return "P4-Low"
