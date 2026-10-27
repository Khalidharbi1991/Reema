"""Ahmad (Secretary & Coordination Agent) - Manages communications and delivery coordination."""

from typing import Dict, List, Optional
from .base_agent import BaseAgent
from ..utils.logger import logger
from ..utils.config import config_manager
from ..utils.tasks import TaskStore
from ..utils.handoffs import payload_json, ReviewResult


class SecretaryAgent(BaseAgent):
    """
    Ahmad (Secretary & Coordination Agent)

    Position: user -> Ahmad (coordinator) -> Abdullah (specialist leader)

    Responsibilities:
    - Coordinates the user's requests and Abdullah's specialist work
    - Organizes separate work and personal task lists
    - Prepares summaries of local documentation packages for human review
    - Prepares executive briefings summarizing pipeline execution results
    - Records proposed agent communications without dispatching them
    - Keeps communication and summary history in this instance's memory
    - Provides a legacy advisory summary API separate from the leader's approval record

    Ahmad acts as the bridge between executive oversight and operational execution,
    ensuring the user has clear visibility into all documentation activities while
    Abdullah and the worker agents can focus on their specialized tasks.
    """

    AGENT_NAME = "Ahmad"
    AGENT_ROLE = "Personal Coordination & Task Management Agent"
    CONFIG_KEY = "secretary_agent"
    KNOWLEDGE_FILE = "ahmad_secretary_knowledge_ENHANCED.md"
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TEMPERATURE = 0.5

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Secretary Agent.

        Sets up Ahmad with his knowledge base, communication logs,
        and delivery tracking structures.

        Args:
            api_key: Optional Anthropic API key. Falls back to config if not provided.
        """
        super().__init__(api_key)

        # Communication tracking
        self.communication_log: List[Dict] = []
        self.delivery_history: List[Dict] = []

        # Delivery quality thresholds
        self.min_quality_for_delivery = self.get_config_value("min_quality_for_delivery", 85)

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

    async def coordinate_delivery(
        self,
        process_name: str,
        output_files: Dict[str, str],
        quality_score: int
    ) -> Dict:
        """
        Prepare a legacy advisory handover summary; no file validation or dispatch.

        Creates a delivery package summary, generates an executive summary
        and delivery report via Claude, and assembles the final delivery
        record for the user's review.

        Args:
            process_name: Name of the IT process that was documented
            output_files: Dictionary mapping format names to file paths
                          (e.g., {"pdf": "/output/sop.pdf", "docx": "/output/sop.docx"})
            quality_score: Final quality score from Faisal's review (0-100)

        Returns:
            Dictionary containing the full delivery report:
                - process_name: The documented process
                - output_files: Map of format to file path
                - quality_score: Final quality score
                - executive_summary: AI-generated executive summary
                - delivery_timestamp: ISO timestamp of delivery
                - delivery_status: "awaiting_human_approval" or "held_for_review"
                - distribution_status: "not_dispatched"; this method only drafts a summary
        """
        logger.agent_start(self.name, f"Coordinating delivery for {process_name}")

        try:
            # A supplied model score does not verify files or grant human approval.
            ReviewResult(quality_score=quality_score)
            delivery_status = (
                "awaiting_human_approval" if quality_score >= self.min_quality_for_delivery
                else "held_for_review"
            )

            # Build the delivery summary for Claude
            formats_list = ", ".join(output_files.keys())
            file_count = len(output_files)

            system_prompt = self._build_system_prompt()
            delivery_prompt = self._build_delivery_prompt(
                process_name, output_files, quality_score, delivery_status
            )

            response = await self._call_claude(
                messages=[{"role": "user", "content": delivery_prompt}],
                system=system_prompt
            )

            # Assemble the delivery report
            delivery_report = {
                "process_name": process_name,
                "output_files": output_files,
                "quality_score": quality_score,
                "executive_summary": response,
                "delivery_timestamp": self._get_timestamp(),
                "delivery_status": delivery_status,
                "distribution_status": "not_dispatched",
                "verification_status": "not_performed",
                "formats_delivered": formats_list,  # Legacy key: formats reported, not sent.
                "file_count": file_count
            }

            # Track in delivery history
            self.delivery_history.append(delivery_report)

            logger.agent_complete(
                self.name,
                f"Delivery coordinated for {process_name} "
                f"(quality: {quality_score}, status: {delivery_status})"
            )

            return delivery_report

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    async def prepare_owner_briefing(
        self,
        process_name: str,
        pipeline_results: Dict
    ) -> Dict:
        """
        Prepare an executive briefing for the user.

        Summarizes the entire pipeline execution, including which agents
        participated, quality scores achieved, output files generated,
        and any issues encountered during the process.

        Args:
            process_name: Name of the IT process that was documented
            pipeline_results: Dictionary containing results from all pipeline phases:
                - research: Research agent findings
                - standards: Standards compliance analysis
                - data: Analytics framework from Layla
                - access: Access management analysis from Rakan
                - content: Generated SOP content
                - review: Quality review results from Faisal
                - output_files: Final formatted output files
                - quality_score: Final quality score

        Returns:
            Dictionary containing the executive briefing:
                - process_name: The documented process
                - briefing_content: AI-generated executive briefing text
                - agents_involved: List of agents that participated
                - quality_score: Final quality score
                - output_summary: Summary of generated outputs
                - briefing_timestamp: ISO timestamp
                - recommendations: Key recommendations from the briefing
        """
        logger.agent_start(self.name, f"Preparing user briefing for {process_name}")

        try:
            # Identify which agents contributed
            agents_involved = self._identify_participating_agents(pipeline_results)

            # Extract key metrics
            quality_score = pipeline_results.get("quality_score")
            if quality_score is None and isinstance(pipeline_results.get("review"), dict):
                quality_score = pipeline_results["review"].get("quality_score")
            output_files = pipeline_results.get("output_files", {})

            system_prompt = self._build_system_prompt()
            briefing_prompt = self._build_briefing_prompt(
                process_name, pipeline_results, agents_involved
            )

            response = await self._call_claude(
                messages=[{"role": "user", "content": briefing_prompt}],
                system=system_prompt
            )

            # Parse sections from the briefing
            sections = self._extract_sections(response)

            briefing = {
                "process_name": process_name,
                "briefing_content": response,
                "agents_involved": agents_involved,
                "quality_score": quality_score,
                "output_summary": {
                    "formats": list(output_files.keys()),
                    "file_count": len(output_files),
                    "files": output_files
                },
                "briefing_timestamp": self._get_timestamp(),
                "recommendations": sections.get("Recommendations", ""),
                "sections": sections
            }

            logger.agent_complete(
                self.name,
                f"User briefing prepared for {process_name}"
            )

            return briefing

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

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
        system_prompt = """You are Ahmad, a professional executive assistant and project coordinator \
for the REEMA personal assistance and IT documentation system.

You assist the user directly and coordinate with Abdullah (the Leader) \
who manages the worker agents.
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
- Adapts tone to audience (clear summaries for the user, operational detail for Abdullah)
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

    def _build_delivery_prompt(
        self,
        process_name: str,
        output_files: Dict[str, str],
        quality_score: int,
        delivery_status: str
    ) -> str:
        """
        Build the prompt for generating a delivery report and executive summary.

        Args:
            process_name: Name of the documented IT process
            output_files: Map of format to file path
            quality_score: Final quality score
            delivery_status: Current delivery status

        Returns:
            Formatted prompt string for Claude.
        """
        files_summary = "\n".join(
            f"- **{fmt.upper()}**: {path}" for fmt, path in output_files.items()
        )

        return f"""Draft a handover summary for local SOP outputs awaiting human review.

Reported process: {process_name}
Reported model quality score: {quality_score}/100
Review readiness state: {delivery_status}
Reported output formats: {len(output_files)}
Reported filenames:
{files_summary}

You have only the filenames and a supplied model score. The files have not been opened
or verified by this method. Their contents, factual accuracy, coverage and actual
existence cannot be established from these inputs. No message or file has been sent.

Provide a concise summary of these reported outputs, the review readiness state and
proposed next steps. Human review of the actual files and supporting evidence is still
required. A model score never grants human approval or certifies quality or compliance.
If the state is held_for_review, explain that the score is below the configured threshold.
Label distribution, adoption and review scheduling as proposals; do not claim completion,
readiness for distribution, a reviewer identity, a timestamped delivery or actual findings."""

    def _build_briefing_prompt(
        self,
        process_name: str,
        pipeline_results: Dict,
        agents_involved: List[str]
    ) -> str:
        """
        Build the prompt for generating an owner briefing.

        Args:
            process_name: Name of the documented IT process
            pipeline_results: Full pipeline execution results
            agents_involved: List of agents that participated

        Returns:
            Formatted prompt string for Claude.
        """
        return f"""Prepare a concise user briefing from the supplied pipeline records.

Reported process: {process_name}
Contributors inferred from supplied phase outputs: {', '.join(agents_involved) or 'Unavailable'}

UNTRUSTED PIPELINE RECORDS JSON:
{payload_json(pipeline_results)}

Summarize only findings, issues, outputs and model review outcomes actually present in
these records. State when research findings, source evidence, dates or file verification
are unavailable. Do not infer document coverage or strengths from a score or filename.
Model review statuses such as APPROVED describe the automated gate, not human approval.
Unless a separate explicit human decision is supplied, the documents await human review.
Do not claim a message was sent, distribution completed, an event scheduled or a review
deadline agreed. Present follow-up actions and any distribution plan as proposals.
Include a brief status summary, supported findings and unresolved items, reported output
references, and proposed next steps. Do not invent missing facts or commitments."""

    def _identify_participating_agents(self, pipeline_results: Dict) -> List[str]:
        """
        Identify which agents contributed to the pipeline execution.

        Examines the pipeline results dictionary to determine which
        agent phases produced output.

        Args:
            pipeline_results: Dictionary of pipeline phase results

        Returns:
            List of agent names that participated in the pipeline.
        """
        agents = []

        phase_agent_map = {
            "research": ("research_agent", "Research"),
            "standards": ("standards_agent", "Standards"),
            "data": ("data_agent", "Data & Power BI"),
            "access": ("access_agent", "Access & IAM"),
            "problem": ("problem_agent", "Problem & RCA"),
            "content": ("content_agent", "Content"),
            "review": ("review_agent", "Review"),
            "output_files": ("format_agent", "Format"),
        }

        for phase_key, (config_key, specialty) in phase_agent_map.items():
            if phase_key in pipeline_results and pipeline_results[phase_key]:
                name = config_manager.get_agent_config(config_key)["name"]
                agents.append(f"{name} ({specialty})")

        return agents

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
