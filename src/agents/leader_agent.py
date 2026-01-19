"""Abdullah (Leader/Orchestrator Agent) - Coordinates all worker agents."""

import asyncio
from typing import Dict, List, Optional
from anthropic import Anthropic
from ..utils.logger import logger
from ..utils.config import config_manager


class AgentTask:
    """Represents a task assigned to an agent."""
    def __init__(self, agent_name: str, task_type: str, parameters: dict):
        self.agent_name = agent_name
        self.task_type = task_type
        self.parameters = parameters
        self.result = None
        self.status = "pending"  # pending, in_progress, completed, failed


class LeaderAgent:
    """
    Abdullah (Leader/Orchestrator Agent)

    Responsibilities:
    - Receives user requests for process documentation
    - Breaks down tasks and assigns to specialized worker agents
    - Coordinates workflow between agents
    - Performs final quality control and validation
    - Assembles final output in requested format(s)
    - Manages state and context across the agent team
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config_manager.system_config.anthropic_api_key
        self.client = Anthropic(api_key=self.api_key)
        self.name = "Abdullah"
        self.model = config_manager.system_config.leader_model

        # Worker agents registry
        self.worker_agents = {}
        self.current_tasks = []
        self.context = {}

        logger.info("Leader Agent initialized", agent=self.name)

    def register_worker(self, agent_name: str, agent_instance):
        """Register a worker agent."""
        self.worker_agents[agent_name] = agent_instance
        logger.info(f"Registered worker: {agent_name}", agent=self.name)

    async def generate_documentation(
        self,
        process_name: str,
        output_formats: List[str] = None
    ) -> Dict[str, str]:
        """
        Main entry point for document generation.

        Args:
            process_name: Name of the IT process to document
            output_formats: List of desired output formats (pdf, docx, markdown, html)

        Returns:
            Dictionary mapping format to file path
        """
        logger.agent_start(self.name, f"Generating documentation for {process_name}")

        output_formats = output_formats or config_manager.system_config.default_formats

        try:
            # Step 1: Plan the workflow
            workflow = await self._plan_workflow(process_name)

            # Step 2: Execute research phase
            research_data = await self._coordinate_research(process_name, workflow)

            # Step 3: Generate content
            content = await self._coordinate_content_generation(
                process_name, research_data
            )

            # Step 4: Review and refine
            reviewed_content = await self._coordinate_review(content)

            # Step 5: Format and export
            output_files = await self._coordinate_formatting(
                reviewed_content, output_formats
            )

            logger.agent_complete(self.name, f"Documentation for {process_name}")
            return output_files

        except Exception as e:
            logger.agent_error(self.name, str(e))
            raise

    async def _plan_workflow(self, process_name: str) -> Dict:
        """Plan the workflow for documentation generation."""
        logger.info(f"Planning workflow for {process_name}", agent=self.name)

        # Get process definition from config
        process_def = config_manager.get_process_definition(process_name)
        standards = config_manager.get_standards_for_process(process_name)

        workflow = {
            "process_name": process_name,
            "process_definition": process_def,
            "applicable_standards": standards,
            "phases": [
                "research",
                "content_generation",
                "review",
                "formatting"
            ]
        }

        return workflow

    async def _coordinate_research(
        self, process_name: str, workflow: Dict
    ) -> Dict:
        """Coordinate research agents to gather information."""
        logger.info("Coordinating research phase", agent=self.name)

        tasks = []

        # Assign to Research Agent
        if "ResearchAgent" in self.worker_agents:
            research_task = self.worker_agents["ResearchAgent"].research_process(
                process_name,
                workflow["applicable_standards"]
            )
            tasks.append(("research", research_task))

        # Assign to Standards Agent
        if "StandardsAgent" in self.worker_agents:
            standards_task = self.worker_agents["StandardsAgent"].analyze_compliance(
                process_name,
                workflow["applicable_standards"]
            )
            tasks.append(("standards", standards_task))

        # Execute tasks concurrently
        results = {}
        if tasks:
            task_results = await asyncio.gather(*[task for _, task in tasks])
            for (task_name, _), result in zip(tasks, task_results):
                results[task_name] = result

        return results

    async def _coordinate_content_generation(
        self, process_name: str, research_data: Dict
    ) -> str:
        """Coordinate content generation."""
        logger.info("Coordinating content generation phase", agent=self.name)

        if "ContentAgent" in self.worker_agents:
            content = await self.worker_agents["ContentAgent"].generate_sop(
                process_name,
                research_data
            )
            return content

        return ""

    async def _coordinate_review(self, content: str) -> str:
        """Coordinate review and quality assurance."""
        logger.info("Coordinating review phase", agent=self.name)

        if "ReviewAgent" in self.worker_agents:
            review_result = await self.worker_agents["ReviewAgent"].review_content(
                content
            )

            # If quality is not sufficient, request revision
            if review_result.get("quality_score", 0) < 85:
                logger.warning(
                    f"Quality score {review_result['quality_score']} below threshold",
                    agent=self.name
                )
                # Request content refinement
                if "ContentAgent" in self.worker_agents:
                    content = await self.worker_agents["ContentAgent"].refine_content(
                        content,
                        review_result.get("feedback", [])
                    )

            return review_result.get("refined_content", content)

        return content

    async def _coordinate_formatting(
        self, content: str, output_formats: List[str]
    ) -> Dict[str, str]:
        """Coordinate formatting and export."""
        logger.info(f"Coordinating formatting for {output_formats}", agent=self.name)

        output_files = {}

        if "FormatAgent" in self.worker_agents:
            output_files = await self.worker_agents["FormatAgent"].convert_to_formats(
                content,
                output_formats
            )

        return output_files

    async def _call_claude(self, messages: List[Dict], system: str = "") -> str:
        """Make a call to Claude API."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}", agent=self.name)
            raise

    def get_status(self) -> Dict:
        """Get current status of all tasks."""
        return {
            "leader": self.name,
            "workers": list(self.worker_agents.keys()),
            "active_tasks": len([t for t in self.current_tasks if t.status == "in_progress"]),
            "completed_tasks": len([t for t in self.current_tasks if t.status == "completed"])
        }
