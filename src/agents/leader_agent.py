"""Abdullah (Leader/Orchestrator Agent) - Coordinates all worker agents.

Pipeline Phases:
  Phase 1: Planning — workflow + standards identification
  Phase 2: Research — Taif + Mohammad + explicitly selected specialists
  Phase 3a: Content Generation — Saad writes SOP (15-30 pages)
  Phase 3b: Enrichment — Layla (dashboards) + Rakan (access) + Abeer (problem) + Agent 10 (endpoint) merge into SOP
  Phase 4a: Review — Faisal quality scoring (max 2 cycles, configured threshold)
  Phase 4b: Compliance Validation — Rakan (access) + Abeer (problem) validate compliance
  Phase 5: Formatting — Bee converts to PDF/DOCX/MD/HTML
  Phase 6: Delivery — hash-verified drafts awaiting a human decision
"""

import asyncio
import hashlib
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from typing import Dict, List, Optional
from ..utils.logger import logger
from ..utils.config import config_manager, normalize_process_name, selected_model
from ..utils.approvals import create_pending_record
from ..utils.validation import validate_formats, validate_sop, validate_output_files
from ..utils.provider import RunRuntime, current_runtime
from ..utils.runs import RunStore, load_ready
from ..utils.quality import validate_quality, UnparsedReplyError
from ..knowledge.retrieval import ReferenceIndex
from ..utils.handoffs import adapt_handoff, ReviewResult, ComplianceResult
from ..utils.documents import (ControlRegister, legacy_register, control_coverage, section_map,
                               validate_located_review, CorrectionAssessment, sha, assert_only_targets_changed,
                               assert_no_new_references)
from ..utils.diagrams import extract_flows
from ..utils.specialists import SpecialistInputs, validate_analytics_result
from ..utils.ownership import RunLease
from ..utils.coordination import DocumentationRequest, WorkflowPlan
from ..utils.capabilities import invoke_pipeline
from ..utils.execution import ExecutionJournal, load_execution, execution_identity, validate_result, digest, FIELDS


class AgentTask:
    """Represents a task assigned to an agent."""
    def __init__(self, agent_name: str, task_type: str, parameters: dict):
        self.agent_name = agent_name
        self.task_type = task_type
        self.parameters = parameters
        self.result = None
        self.status = "pending"
        self.started_at = None
        self.finished_at = None
        self.error_type = None
        self.reused_calls = 0
        self.executed_calls = 0

    def snapshot(self):
        return {"agent": self.agent_name, "phase": self.task_type, "status": self.status,
                "started_at": self.started_at, "finished_at": self.finished_at,
                "error_type": self.error_type, "reused_calls": self.reused_calls,
                "executed_calls": self.executed_calls}


class LeaderAgent:
    """
    Abdullah (Leader/Orchestrator Agent)

    Responsibilities:
    - Receives user requests for process documentation
    - Breaks down tasks and assigns to specialized worker agents
    - Coordinates workflow between agents (8 phases)
    - Performs final quality control and validation
    - Assembles final output in requested format(s)
    - Manages state and context across the agent team
    - Leads the SOP pipeline only; Ahmad consults chat specialists directly
    """

    def __init__(self, api_key: Optional[str] = None):
        # api_key is accepted for compatibility; model calls are made by the workers.
        self.name = "Abdullah"
        self.model = selected_model(config_manager.system_config, config_manager.get_agent_config('leader_agent'), leader=True)
        guidance = config_manager.get_agent_config("leader_agent").get("specialization", [])
        self.strategic_guidance = guidance if isinstance(guidance, list) else []

        # Worker agents registry
        self.worker_agents = {}
        self.current_tasks = []
        self.context = {}
        self.workflow_status = "idle"
        self.current_phase = None
        self._task_store = None
        self._journal = None

        logger.info("Leader Agent initialized", agent=self.name)

    def register_worker(self, agent_name: str, agent_instance):
        """Register a worker agent."""
        self.worker_agents[agent_name] = agent_instance
        logger.info(f"Registered worker: {agent_name}", agent=self.name)

    def _begin_workflow(self, process_name, phases):
        if self.workflow_status == "running":
            raise RuntimeError("This leader already has a running workflow; use a separate instance")
        self.current_tasks = [AgentTask(self.name, phase, {"process_name": process_name}) for phase in phases]
        self.workflow_status = "running"
        self.current_phase = None
        self._task_store = None

    def _save_task_status(self):
        if self._task_store is not None:
            self._task_store.state["tasks"] = [task.snapshot() for task in self.current_tasks]
            self._task_store.flush()

    @asynccontextmanager
    async def _phase(self, name, *, reused=False):
        task = next(task for task in self.current_tasks if task.task_type == name)
        task.status = "in_progress"
        task.started_at = datetime.now(timezone.utc).isoformat()
        self.current_phase = name
        try:
            self._save_task_status()
            yield
        except BaseException as error:
            task.status = "cancelled" if isinstance(error, asyncio.CancelledError) else "failed"
            task.error_type = type(error).__name__
            raise
        else:
            task.status = "reused" if reused or (task.reused_calls and not task.executed_calls) else "completed"
        finally:
            task.finished_at = datetime.now(timezone.utc).isoformat()
            self._save_task_status()

    def _finish_workflow(self, status):
        self.workflow_status = status
        for task in self.current_tasks:
            if task.status == "pending":
                task.status = "skipped"
        self._save_task_status()

    def _record_handoff(self, process_name, producer, stage, payload, *, text_key=None):
        runtime = current_runtime.get()
        try:
            handoff = adapt_handoff(process_name, producer, stage, payload, text_key=text_key,
                                    sources=runtime.sources if runtime else None)
        except ValueError:
            # Validation errors can contain the full private input; expose field guidance only.
            raise ValueError(f"Invalid {stage} handoff from {producer}; check {text_key or 'result fields'}, "
                             "process identity and structured metadata") from None
        self.context.setdefault("handoffs", {})[f"{stage}:{producer}"] = handoff.model_dump()
        return handoff

    def _research_payload(self, key, payload):
        """Add validated metadata to a copy for the next worker; public results stay intact."""
        handoff = self.context.get("handoffs", {}).get(f"research:{key}")
        return dict(payload, handoff_metadata=handoff["metadata"]) if handoff else payload

    async def _invoke(self, capability, arguments):
        """Reuse only authenticated completed calls with identical validated inputs."""
        task = next((t for t in self.current_tasks if t.task_type == self.current_phase), None)
        cached = self._journal.data["completed_calls"].get(capability) if self._journal else None
        runtime = current_runtime.get()
        if cached is not None:
            if cached["arguments_sha256"] != digest(arguments):
                raise ValueError("Recovered capability inputs differ; cached work cannot be reused")
            validate_result(capability, cached["result"], self.context["request"]["process_name"], runtime.sources)
            if capability == "data":
                validate_analytics_result(cached["result"], self.context.get("request", {}).get("specialist_inputs"), config_manager.specialist_policy, runtime.sources)
            if task:
                task.reused_calls += 1
                self._save_task_status()
            return deepcopy(cached["result"])
        if task:
            task.executed_calls += 1
            self._save_task_status()
        result = await invoke_pipeline(self.worker_agents, capability, arguments)
        if capability == "data":
            validate_analytics_result(result, self.context.get("request", {}).get("specialist_inputs"), config_manager.specialist_policy, runtime.sources)
        if self._journal and capability in {*FIELDS, "content"}:
            validate_result(capability, result, self.context["request"]["process_name"], runtime.sources)
            self._journal.record(capability, arguments, result, runtime.sources)
        return result

    async def resume_execution(self, directory, formats=None, *, allow_external_ai=False):
        if allow_external_ai is not True:
            raise PermissionError("Model-phase recovery requires fresh --allow-external-ai authorization")
        with RunLease(directory) as lease:
            record, _ = load_execution(directory, config_manager, lease=lease)
            if record.usage.get('in_flight'):
                logger.warning("Interrupted provider outcomes are unknown; pending reservations remain charged and requests may be repeated", agent=self.name)
            request = record.request
            if formats is not None and validate_formats(formats) != request.formats:
                raise ValueError("Model recovery cannot change requested formats; start a new run")
            return await self.generate_documentation(
                request.process_name, request.formats, custom=request.custom, specialists=request.specialists,
                objective=request.objective, constraints=request.constraints,
                required_deliverables=request.required_deliverables, acceptance_criteria=request.acceptance_criteria,
                specialist_inputs=request.specialist_inputs.model_dump() if request.specialist_inputs else None,
                allow_external_ai=True, _resume_from=directory, _resume_lease=lease)

    async def generate_documentation(
        self,
        process_name: str,
        output_formats: List[str] = None,
        *,
        custom: bool = False,
        specialists: Optional[List[str]] = None,
        objective: Optional[str] = None,
        constraints: Optional[List[str]] = None,
        required_deliverables: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None,
        specialist_inputs: Optional[Dict] = None,
        allow_external_ai: bool = False,
        _resume_from=None,
        _resume_lease=None,
    ) -> Dict[str, str]:
        """
        Main entry point for document generation.

        Executes the full 6-phase pipeline:
          Phase 1 → 2 → 3a → 3b → 4a → 4b → 5 → 6

        Args:
            process_name: Name of the IT process to document
            output_formats: List of desired output formats (pdf, docx, markdown, html)

        Returns:
            Dictionary mapping format to file path
        """
        if self.workflow_status == "running":
            raise RuntimeError("This leader already has a running workflow; use a separate instance")
        logger.agent_start(self.name, f"Generating documentation for {process_name}")

        output_formats = validate_formats(
            config_manager.system_config.default_formats if output_formats is None else output_formats
        )
        process_id, definition = config_manager.resolve_process(process_name, custom=custom)
        process_name = definition["name"]
        inputs = SpecialistInputs.model_validate(specialist_inputs) if specialist_inputs is not None else None
        if inputs:
            inputs.validate_limits(config_manager.specialist_policy)
        selected = set(definition.get("specialists", [])) | set(specialists or []) | (inputs.required_specialists() if inputs else set())
        if selected - {"access", "problem", "data", "euc"}:
            raise ValueError("Specialists must be access, problem, data, or euc")
        required_workers = {"ResearchAgent", "StandardsAgent", "ContentAgent", "ReviewAgent", "FormatAgent"}
        required_workers.update({"access": "AccessAgent", "problem": "ProblemAgent", "data": "DataAgent",
                                 "euc": "EUCAgent"}[key] for key in selected)
        missing = required_workers - self.worker_agents.keys()
        if missing:
            raise ValueError(f"Required agents missing: {', '.join(sorted(missing))}")
        self.worker_agents["FormatAgent"].validate_requested_formats(output_formats)
        if not (allow_external_ai or config_manager.system_config.allow_external_ai):
            raise PermissionError("Authorize external AI input with --allow-external-ai or ALLOW_EXTERNAL_AI=true")
        if config_manager.system_config.enforce_page_target and "pdf" not in output_formats:
            raise ValueError("ENFORCE_PAGE_TARGET requires PDF output for a real rendered page count")
        previous, recovered = (None, {})
        if _resume_from is not None:
            if allow_external_ai is not True:
                raise PermissionError("Model-phase recovery requires fresh explicit authorization")
            if not isinstance(_resume_lease, RunLease):
                raise ValueError("Use resume_execution to hold the parent recovery lease")
            previous, recovered = load_execution(_resume_from, config_manager, lease=_resume_lease)
        request = DocumentationRequest(
            process_name=process_name, custom=custom, formats=output_formats, specialists=sorted(selected),
            objective=objective or f"Document {process_name} as an operational SOP",
            constraints=list(dict.fromkeys(definition.get("constraints", []) + (constraints or []))),
            required_deliverables=required_deliverables or ["SOP", *output_formats],
            acceptance_criteria=list(dict.fromkeys(definition.get("acceptance_criteria", []) + (acceptance_criteria or []))),
            specialist_inputs=specialist_inputs)
        self.context = {"process_id": process_id, "specialists": sorted(selected), "request": request.model_dump()}
        run_dir = config_manager.system_config.output_dir / "runs" / uuid4().hex
        self.context["run_dir"] = str(run_dir)
        formatter = self.worker_agents["FormatAgent"]
        original_output_dir = formatter.output_dir
        formatter.output_dir = run_dir
        runtime = RunRuntime(config_manager.system_config.model_copy(update={"allow_external_ai": True}))
        if previous:
            runtime.inherited_tokens = previous.usage.get("accounted_tokens", 0)
            runtime.tokens = runtime.inherited_tokens
            runtime.sources = previous.sources.copy()
            runtime.lineage = previous.lineage + [{"run": str(Path(_resume_from).resolve()),
                                                   "accounted_tokens": runtime.inherited_tokens,
                                                   "new_calls": len(previous.usage.get("calls", []))}]
        token = current_runtime.set(runtime)
        store = None
        self._begin_workflow(process_name, ["planning", "research", "content", "enrichment",
                                            "review", "compliance", "formatting", "human_review_record"])

        try:
            store = RunStore(run_dir, process_name, output_formats)
            self._task_store = store
            if previous:
                store.state["resumed_from"] = str(Path(_resume_from).resolve())
                store.state["recovery_mode"] = "abandoned_owner" if previous.run_state.get("status") == "running" else "failed_or_cancelled"
                store.state["inherited_uncertain_requests"] = previous.usage.get("in_flight", [])
                store.state["reused_capabilities"] = list(previous.completed_calls)
            def save_usage(summary):
                store.state["usage"] = summary
                store.flush()
            runtime.on_event = save_usage
            async with self._phase("planning"):
                # Phase 1: Plan the workflow
                source_index = ReferenceIndex(config_manager.system_config)
                for worker in self.worker_agents.values():
                    worker.source_records = source_index.search(process_name)
                workflow = await self._plan_workflow(process_name)
                store.save("planned", workflow)
                identity = execution_identity(config_manager, request, source_index)
                if previous:
                    if identity != previous.identity:
                        raise ValueError("Inputs, configuration, source permissions/content or implementation changed; recovery rejected")
                    available = {r["id"]: r for r in source_index.records}
                    for worker in self.worker_agents.values():
                        available.update({r["id"]: r for r in getattr(worker, "knowledge_records", [])})
                    for source_id, source in runtime.sources.items():
                        candidate = available.get(source_id)
                        if not candidate or any(source.get(key) != candidate.get(key) for key in ("source", "sha256", "location", "classification")):
                            raise ValueError("Recovered source provenance is not available under current permissions")
                self._journal = ExecutionJournal(store, config_manager, request, identity,
                                                 previous=previous, parent=Path(_resume_from).resolve() if previous else None)
                runtime.execution_journal = self._journal
                store.state["usage"] = runtime.summary()
                store.flush()

            async with self._phase("research"):
                # Phase 2: Execute research phase (Taif + Mohammad + Layla + Rakan in parallel)
                research_data = await self._coordinate_research(process_name, workflow)
                research_data["strategic_guidance"] = workflow.get("strategic_guidance", self.strategic_guidance)
                research_data["request_context"] = request.model_dump()
                store.save("researched", {**research_data, "handoffs": self.context.get("handoffs", {})})

            async with self._phase("content"):
                # Phase 3a: Generate content (Saad writes main SOP)
                content = await self._coordinate_content_generation(
                    process_name, research_data
                )
                store.save("generated", {"content": content, "sources": runtime.sources,
                                         "handoffs": self.context.get("handoffs", {})})

            async with self._phase("enrichment"):
                # Phase 3b: Enrich content (Layla dashboards + Rakan access sections)
                enriched_content = await self._coordinate_enrichment(
                    process_name, content, research_data
                )
                validate_sop(enriched_content)
                section_map(enriched_content, config_manager.document_profile, require_complete=True)
                extract_flows(enriched_content)
                store.save("drafted", {"content": enriched_content, "sources": runtime.sources,
                                       "handoffs": self.context.get("handoffs", {})})

            async with self._phase("review", reused="reviewed" in recovered):
                # Phase 4a: Review and refine (Faisal — max 2 cycles)
                if "reviewed" in recovered:
                    reviewed_content = recovered["reviewed"]["content"]
                    review = ReviewResult.from_legacy(recovered["reviewed"]["review"])
                    threshold = config_manager.get_agent_config("review_agent")["quality_threshold"]
                    if (review.quality_score < threshold or review.needs_revision
                            or review.approval_status not in {None, "APPROVED"}
                            or any(issue.severity == "critical" or issue.blocking for issue in review.issues)):
                        raise ValueError("Recovered review does not meet the current quality gate")
                    validate_sop(reviewed_content)
                    validate_located_review(recovered["reviewed"]["review"], reviewed_content, config_manager.document_profile)
                    self.context["last_review"] = recovered["reviewed"]["review"]
                    self.context["revision_history"] = recovered["reviewed"].get("revision_history", [])
                    self._record_handoff(process_name, "review", "review", self.context["last_review"])
                else:
                    reviewed_content = await self._coordinate_review(enriched_content)
                store.save("reviewed", {"content": reviewed_content, "review": self.context["last_review"],
                                        "revision_history": self.context.get("revision_history", []),
                                        "handoffs": self.context.get("handoffs", {})})

            async with self._phase("compliance"):
                # Phase 4b: Access compliance validation (Rakan)
                validated_content = await self._coordinate_compliance_validation(
                    process_name, reviewed_content
                )
                validate_sop(validated_content)
                quality = validate_quality(validated_content, workflow["applicable_standards"], runtime.sources)
                controls = control_coverage(validated_content, ControlRegister.model_validate(self.context["control_register"]),
                                            runtime.sources, config_manager.document_profile)
                if controls["errors"]:
                    raise ValueError("Control coverage failed: " + "; ".join(controls["errors"]))
                quality["control_coverage"] = controls
                quality["warnings"].extend(controls["warnings"])
                self.context["quality"] = quality
                store.save("ready", {"content": validated_content, "review": self.context["last_review"],
                                     "sources": runtime.sources, "standards": workflow["applicable_standards"], "quality": quality,
                                     "control_register": self.context["control_register"],
                                     "document_profile": config_manager.document_profile.model_dump(),
                                     "revision_history": self.context.get("revision_history", []),
                                     "handoffs": self.context.get("handoffs", {})})

            async with self._phase("formatting"):
                # Phase 5: Format and export (Bee)
                output_files = await self._coordinate_formatting(
                    validated_content, output_formats, process_name
                )
                validate_output_files(output_files, output_formats)
                self._check_page_count(output_files, quality)
                store.save("exported", {"outputs": output_files, "quality": quality, "sources": runtime.sources,
                                        "export_checks": getattr(formatter, "last_export_checks", {})})

            async with self._phase("human_review_record"):
                # Phase 6: Pending human approval record; no AI can approve.
                delivery_result = await self._coordinate_delivery(
                    process_name, output_files
                )

                self.context["delivery"] = delivery_result
            self._finish_workflow("awaiting_human_approval")
            store.finish("awaiting_human_approval", runtime.summary())

            logger.agent_complete(self.name, f"Documentation for {process_name}")
            return output_files

        except BaseException as e:
            self._finish_workflow("cancelled" if isinstance(e, asyncio.CancelledError) else "failed")
            if store:
                store.finish("cancelled" if isinstance(e, asyncio.CancelledError) else "failed", runtime.summary(), type(e).__name__)
            logger.agent_error(self.name, str(e))
            raise
        finally:
            if store:
                store.close()
            current_runtime.reset(token)
            formatter.output_dir = original_output_dir
            self._task_store = None
            self._journal = None

    def _check_page_count(self, output_files, quality):
        target = config_manager.system_config.page_target
        quality["page_target"] = list(target)
        quality["rendered_pdf_pages"] = None
        if "pdf" in output_files:
            from pypdf import PdfReader
            pages = len(PdfReader(output_files["pdf"]).pages)
            quality["rendered_pdf_pages"] = pages
            if not target[0] <= pages <= target[1]:
                if config_manager.system_config.enforce_page_target:
                    raise ValueError(f"Rendered PDF has {pages} pages; required range is {target}")
                quality["warnings"].append(f"Rendered PDF has {pages} pages, outside target {target}")
        elif config_manager.system_config.enforce_page_target:
            raise ValueError("ENFORCE_PAGE_TARGET requires PDF output")

    async def resume_formatting(self, directory, formats=None):
        """Recover exports from an unchanged ready checkpoint without model calls."""
        with RunLease(directory) as lease:
            return await self._resume_formatting(directory, formats, lease)

    async def _resume_formatting(self, directory, formats, lease):
        if self.workflow_status == "running":
            raise RuntimeError("This leader already has a running workflow; use a separate instance")
        state, ready = load_ready(directory, lease=lease)
        formats = validate_formats(formats or state["formats"])
        formatter = self.worker_agents["FormatAgent"]
        formatter.validate_requested_formats(formats)
        review = ready["review"]
        gate = ReviewResult.from_legacy(review)
        threshold = config_manager.get_agent_config("review_agent")["quality_threshold"]
        if (gate.quality_score < threshold or gate.needs_revision
                or gate.approval_status not in {None, "APPROVED"}
                or any(issue.severity == "critical" or issue.blocking for issue in gate.issues)):
            raise ValueError("Checkpoint review does not meet the current quality gate")
        quality = validate_quality(ready["content"], ready["standards"], ready["sources"])
        validate_located_review(review, ready["content"], config_manager.document_profile)
        if "control_register" in ready:
            if ready.get("document_profile") != config_manager.document_profile.model_dump():
                raise ValueError("Document profile changed; create a new generation")
            controls = control_coverage(ready["content"], ControlRegister.model_validate(ready["control_register"]),
                                        ready["sources"], config_manager.document_profile)
            if controls["errors"]:
                raise ValueError("Checkpoint control coverage failed")
            quality["control_coverage"] = controls
            quality["warnings"].extend(controls["warnings"])
        run_dir = config_manager.system_config.output_dir / "runs" / uuid4().hex
        store = RunStore(run_dir, state["process_name"], formats)
        store.state["resumed_from"] = str(Path(directory).resolve())
        store.save("ready", ready)
        original_dir, formatter.output_dir = formatter.output_dir, run_dir
        self.context = {"run_dir": str(run_dir), "last_review": review}
        self._begin_workflow(state["process_name"], ["formatting", "human_review_record"])
        self._task_store = store
        try:
            async with self._phase("formatting"):
                outputs = await formatter.convert_to_formats(ready["content"], formats, state["process_name"])
                validate_output_files(outputs, formats)
                self._check_page_count(outputs, quality)
                store.save("exported", {"outputs": outputs, "quality": quality, "sources": ready["sources"],
                                        "export_checks": getattr(formatter, "last_export_checks", {})})
            async with self._phase("human_review_record"):
                self.context["delivery"] = await self._coordinate_delivery(state["process_name"], outputs)
            self._finish_workflow("awaiting_human_approval")
            store.finish("awaiting_human_approval", {"calls": [], "accounted_tokens": 0, "estimated_cost_usd": 0})
            return outputs
        except BaseException as error:
            self._finish_workflow("cancelled" if isinstance(error, asyncio.CancelledError) else "failed")
            store.finish(self.workflow_status, {"calls": []}, type(error).__name__)
            raise
        finally:
            store.close()
            formatter.output_dir = original_dir
            self._task_store = None

    async def close(self):
        for worker in self.worker_agents.values():
            if hasattr(worker, "close"):
                await worker.close()

    def _uses_specialist(self, name: str) -> bool:
        return name in self.context.get("specialists", [])

    async def _plan_workflow(self, process_name: str) -> Dict:
        """Phase 1: Plan the workflow for documentation generation."""
        logger.info(f"Phase 1: Planning workflow for {process_name}", agent=self.name)

        # Get process definition from config
        process_def = config_manager.get_process_definition(process_name)
        standards = config_manager.get_standards_for_process(process_name)

        # Get process-specific KPIs from config, with fallback defaults
        kpis = self._get_process_kpis(process_name, process_def)

        workflow = {
            "process_name": process_name,
            "process_definition": process_def,
            "applicable_standards": standards,
            "kpis": kpis,
            "strategic_guidance": self.strategic_guidance,
            "phases": [
                "research",
                "content_generation",
                "enrichment",
                "review",
                "compliance_validation",
                "formatting",
                "delivery"
            ]
        }

        request_data = self.context.get("request")
        if request_data:
            request = DocumentationRequest.model_validate(request_data)
            names = ["planning", "research", "content", "enrichment", "review", "compliance", "formatting", "human_review_record"]
            plan = WorkflowPlan(request=request, dependencies={name: names[i-1:i] for i, name in enumerate(names)})
            workflow["coordination_plan"] = plan.model_dump()
            workflow["acceptance_gates"] = {"required_sections": 11,
                "review_threshold": config_manager.get_agent_config("review_agent")["quality_threshold"],
                "user_criteria_verification": "human_review",
                "human_approval_required": True}
        self.context["workflow"] = workflow
        return workflow

    def _get_process_kpis(self, process_name: str, process_def: Dict) -> List[str]:
        """Get process-specific KPIs from config or generate defaults.

        Args:
            process_name: Name of the IT process
            process_def: Process definition from config

        Returns:
            List of KPI strings
        """
        # Try to get KPIs from process definition config
        if process_def and process_def.get("kpis"):
            return process_def["kpis"]

        # Default KPIs per process category
        kpi_defaults = {
            "incident": [
                "Mean Time to Resolve (MTTR)",
                "First Contact Resolution Rate",
                "Incident Reopening Rate",
                "SLA Compliance Rate",
                "Customer Satisfaction Score"
            ],
            "change": [
                "Change Success Rate",
                "Emergency Change Percentage",
                "Change Lead Time",
                "Failed Change Rate",
                "Change Backlog Size"
            ],
            "problem": [
                "Known Error Resolution Time",
                "Problem Recurrence Rate",
                "Proactive Problem Identification Rate",
                "Root Cause Identification Accuracy",
                "Problem Backlog Aging"
            ],
            "access": [
                "Access Request Fulfillment Time",
                "Unauthorized Access Incidents",
                "Access Review Completion Rate",
                "Orphaned Account Rate",
                "MFA Adoption Rate"
            ],
            "service_request": [
                "Request Fulfillment Time",
                "Self-Service Utilization Rate",
                "Request Automation Rate",
                "Catalog Item Availability",
                "User Satisfaction Score"
            ]
        }

        # Match on the normalized name ("Service Request Management" -> "service_request_management")
        # so multi-word categories such as "service_request" match display names.
        process_key = normalize_process_name(process_name)
        for category, kpis in kpi_defaults.items():
            if category in process_key:
                return kpis

        # Generic fallback
        return [
            "Process Cycle Time",
            "Quality Score",
            "Compliance Rate",
            "Stakeholder Satisfaction",
            "Process Efficiency"
        ]

    async def _coordinate_research(
        self, process_name: str, workflow: Dict
    ) -> Dict:
        """Phase 2: Coordinate research agents (Taif + Mohammad + Layla + Rakan + Abeer in parallel)."""
        logger.info("Phase 2: Coordinating research phase", agent=self.name)

        requests = [("research", {"process_name": process_name, "standards": workflow["applicable_standards"]}),
                    ("standards", {"process_name": process_name, "standards": workflow["applicable_standards"]})]
        supplied = self.context.get("request", {}).get("specialist_inputs")
        if supplied and supplied.get("as_of"):
            requests[0][1]["research_context"] = {"as_of": supplied["as_of"]}
        for name in ("data", "access", "problem", "euc"):
            if self._uses_specialist(name):
                args = {"process_name": process_name}
                args["kpis" if name == "data" else "standards"] = workflow.get("kpis", []) if name == "data" else workflow["applicable_standards"]
                if supplied:
                    if name == "access" and supplied.get("iam_environment") is not None:
                        args["research_data"] = {"iam_environment": supplied["iam_environment"], "iam_previous": supplied.get("iam_previous")}
                    elif name == "problem" and supplied.get("problem_case") is not None:
                        args["incident_data"] = supplied["problem_case"]
                    elif name == "data" and supplied.get("metric_specs"):
                        args["research_data"] = {"metric_specs": supplied["metric_specs"], "metric_rows": supplied.get("metric_rows")}
                requests.append((name, args))
        tasks = [(name, self._invoke(name, args)) for name, args in requests]

        # Execute tasks concurrently
        results = {}
        if tasks:
            # Await every sibling before failing so late calls cannot outlive the
            # run and escape its usage log/checkpoint context.
            task_results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            for (task_name, _), result in zip(tasks, task_results):
                if isinstance(result, asyncio.CancelledError):
                    raise result
                if isinstance(result, ValueError):
                    raise result
                if isinstance(result, BaseException):
                    raise RuntimeError(f"Research phase '{task_name}' failed") from result
                field = {"research": "raw_research", "standards": "compliance_analysis",
                         "data": "analytics_framework", "access": "access_analysis",
                         "problem": "problem_research", "euc": "endpoint_analysis"}[task_name]
                self._record_handoff(process_name, task_name, "research", result, text_key=field)
                results[task_name] = result

        self.context["research_data"] = results
        register = ControlRegister.model_validate(results["standards"]["control_register"]) if "control_register" in results["standards"] else legacy_register(workflow["applicable_standards"])
        if {c.framework.casefold() for c in register.controls} != {s.casefold() for s in workflow["applicable_standards"]}:
            raise ValueError("Control register must account for every configured framework")
        register.validate_sources(current_runtime.get().sources if current_runtime.get() else {}, config_manager.document_profile)
        self.context["control_register"] = register.model_dump()
        return results

    async def _coordinate_content_generation(
        self, process_name: str, research_data: Dict
    ) -> str:
        """Phase 3a: Coordinate content generation (Saad writes main SOP)."""
        logger.info("Phase 3a: Coordinating content generation", agent=self.name)

        if "ContentAgent" in self.worker_agents:
            content = await self._invoke("content", {"process_name": process_name,
                "research_data": {key: self._research_payload(key, value) for key, value in research_data.items()}})
            return content

        raise ValueError("ContentAgent is required")

    async def _coordinate_enrichment(
        self, process_name: str, content: str, research_data: Dict
    ) -> str:
        """Phase 3b: Enrich SOP with Layla's dashboards, Rakan's access content, and Abeer's problem content.

        Runs all enrichment tasks in parallel, then merges results into the SOP.
        """
        logger.info("Phase 3b: Coordinating content enrichment", agent=self.name)

        enrichment_tasks = []
        enriched_content = content

        if self._uses_specialist("data") and "DataAgent" in self.worker_agents:
            kpis = self.context.get("workflow", {}).get("kpis", [])
            enrichment_tasks.append(("dashboard", self._invoke("dashboard", {"process_name": process_name,
                "metrics": [{**spec, "calculation_check": check} for spec, check in zip(
                    research_data.get("data", {}).get("metric_specs", []), research_data.get("data", {}).get("calculation_checks", []))]
                    or [{"name": kpi, "description": "Process KPI"} for kpi in kpis]})))
        if self._uses_specialist("access") and "AccessAgent" in self.worker_agents:
            enrichment_tasks.append(("access_content", self._invoke("access_content", {"process_name": process_name,
                "access_requirements": self._research_payload("access", research_data.get("access", {}))})))
        if self._uses_specialist("problem") and "ProblemAgent" in self.worker_agents:
            enrichment_tasks.append(("problem_content", self._invoke("problem_content", {"process_name": process_name,
                "research_data": self._research_payload("problem", research_data.get("problem", {}))})))
        if self._uses_specialist("euc") and "EUCAgent" in self.worker_agents:
            enrichment_tasks.append(("euc_content", self._invoke("euc_content", {"process_name": process_name,
                "endpoint_requirements": self._research_payload("euc", research_data.get("euc", {}))})))

        if enrichment_tasks:
            results = await asyncio.gather(
                *[task for _, task in enrichment_tasks],
                return_exceptions=True
            )

            for (task_name, _), result in zip(enrichment_tasks, results):
                if isinstance(result, asyncio.CancelledError):
                    raise result
                if isinstance(result, BaseException):
                    raise RuntimeError(f"Required enrichment '{task_name}' failed") from result
                if not result:
                    raise ValueError(f"Required enrichment '{task_name}' returned no content")

                if task_name == "dashboard" and result:
                    # Append dashboard design section to SOP
                    dashboard_section = self._format_dashboard_section(result, process_name)
                    enriched_content += f"\n\n{dashboard_section}"
                    logger.info("Dashboard design appended to SOP", agent=self.name)

                elif task_name == "access_content" and result:
                    # Append access management section to SOP
                    access_section = self._format_access_section(result, process_name)
                    enriched_content += f"\n\n{access_section}"
                    logger.info("Access management content appended to SOP", agent=self.name)

                elif task_name == "problem_content" and result:
                    # Append problem management section to SOP
                    problem_section = self._format_problem_section(result, process_name)
                    enriched_content += f"\n\n{problem_section}"
                    logger.info("Problem management content appended to SOP", agent=self.name)

                elif task_name == "euc_content" and result:
                    enriched_content += f"\n\n{self._format_euc_section(result, process_name)}"
                    logger.info("Endpoint deployment content appended to SOP", agent=self.name)

        return enriched_content

    def _format_dashboard_section(self, dashboard_data, process_name=None) -> str:
        """Format Layla's dashboard design into a SOP section."""
        self._record_handoff(process_name or "Unspecified process", "dashboard", "enrichment",
                             dashboard_data, text_key="dashboard_design")
        design = dashboard_data["dashboard_design"] if isinstance(dashboard_data, dict) else dashboard_data

        return f"""---

## Appendix: Power BI Dashboard Design

*Designed by Agent 8 (Data & Power BI Specialist)*

{design}
"""

    def _format_access_section(self, access_data, process_name=None) -> str:
        """Format Rakan's access content into a SOP section."""
        self._record_handoff(process_name or "Unspecified process", "access_content", "enrichment",
                             access_data, text_key="access_content")
        content = access_data["access_content"] if isinstance(access_data, dict) else access_data

        return f"""---

## Appendix: Access Management & IAM Requirements

*Analyzed by Agent 6 (Access Management Specialist)*

{content}
"""

    def _format_problem_section(self, problem_data, process_name=None) -> str:
        """Format Abeer's problem management content into a SOP section."""
        self._record_handoff(process_name or "Unspecified process", "problem_content", "enrichment",
                             problem_data, text_key="problem_content")
        content = problem_data["problem_content"] if isinstance(problem_data, dict) else problem_data

        return f"""---

## Appendix: Problem Management & Root Cause Analysis

*Analyzed by Agent 7 (Problem Management Specialist)*

{content}
"""

    def _format_euc_section(self, euc_data, process_name=None) -> str:
        """Format Agent 10's endpoint deployment content into a SOP section."""
        self._record_handoff(process_name or "Unspecified process", "euc_content", "enrichment",
                             euc_data, text_key="endpoint_content")
        content = euc_data["endpoint_content"] if isinstance(euc_data, dict) else euc_data

        return f"""---

## Appendix: Endpoint Deployment & Rollback Plan

*Analyzed by Agent 10 (End-User Computing Specialist)*

{content}
"""

    async def _coordinate_review(self, content: str) -> str:
        """Phase 4a: Coordinate review and quality assurance with max 2 revision cycles.

        Fixes:
        - Now runs up to 2 review cycles (was 1)
        - Properly handles None refined_content (was silently returning None)
        - Re-reviews after refinement to confirm quality improvement
        """
        logger.info("Phase 4a: Coordinating review phase", agent=self.name)

        if "ReviewAgent" not in self.worker_agents:
            raise ValueError("ReviewAgent is required")

        max_review_cycles = config_manager.document_profile.max_review_cycles
        threshold = config_manager.get_agent_config("review_agent").get("quality_threshold", 85)
        current_content = content

        for cycle in range(1, max_review_cycles + 1):
            logger.info(f"Review cycle {cycle}/{max_review_cycles}", agent=self.name)

            review_result = await self._invoke("review", {"content": current_content})

            validated_review = ReviewResult.from_legacy(review_result)
            validate_located_review(review_result, current_content, config_manager.document_profile)
            self.context.setdefault("document_reviews", []).append({"cycle": cycle, "review": review_result})
            if self._task_store is not None:
                self._task_store.state["document_reviews"] = self.context["document_reviews"]
                self._task_store.flush()
            self._record_handoff(self.context.get("workflow", {}).get("process_name", "Unspecified process"),
                                 "review", "review", review_result)

            quality_score = validated_review.quality_score
            if type(quality_score) is not int or not 0 <= quality_score <= 100:
                raise ValueError("Review did not return a valid quality score")
            logger.info(f"Quality score: {quality_score}/100", agent=self.name)

            # Store review results in context for delivery phase
            self.context["last_review"] = review_result

            # If quality meets threshold, return the content
            blocking_issues = any(issue.get("severity") == "critical" or issue.get("blocking") for issue in review_result.get("issues", []))
            revision_requested = review_result.get("approval_status") in {
                "REQUIRES_REVISION", "REVISION_REQUESTED", "PENDING_REVIEW", "APPROVED_WITH_CHANGES"
            }
            if quality_score >= threshold and not review_result.get("needs_revision", False) and not blocking_issues and not revision_requested:
                logger.info(
                    f"Quality threshold met ({quality_score}/100) on cycle {cycle}",
                    agent=self.name
                )
                # Never accept a reviewer's unreviewed rewrite as approved content.
                refined = review_result.get("refined_content")
                if refined is not None and refined != current_content:
                    if review_result.get("review_contract"):
                        raise ValueError("Located reviews cannot supply an untracked document rewrite")
                    current_content = refined
                    continue
                return current_content

            # Quality below threshold — request revision
            logger.warning(
                f"Quality criteria not met (score {quality_score}, threshold {threshold}) on cycle {cycle}",
                agent=self.name
            )

            if "ContentAgent" in self.worker_agents and cycle < max_review_cycles:
                feedback = review_result.get("feedback", [])
                findings = review_result.get("issues", [])
                if review_result.get("review_contract") == "located_v1":
                    before = current_content
                    current_content = await self._invoke("revise_sections", {"content": before, "findings": findings})
                    # Enforce preservation even for a custom registered content worker.
                    targets = {f["section_id"] for f in findings}
                    assert_only_targets_changed(before, current_content, targets, config_manager.document_profile)
                    recheck = await self._invoke("recheck", {"content": current_content, "findings": findings})
                    checked = CorrectionAssessment.model_validate({"corrections": recheck.get("corrections")}).validate_against(
                        current_content, findings, config_manager.document_profile)
                    if recheck.get("document_sha256") != sha(current_content):
                        raise ValueError("Correction recheck does not bind the revised document")
                    history = {"before_sha256": sha(before), "after_sha256": sha(current_content),
                               "target_sections": sorted(targets), "findings": findings, "recheck": recheck}
                    self.context.setdefault("revision_history", []).append(history)
                    if self._task_store is not None:
                        self._task_store.state["revision_history"] = self.context["revision_history"]
                        self._task_store.flush()
                    blocking = {f["finding_id"] for f in findings if f["blocking"]}
                    if any(c.status != "resolved" and c.finding_id in blocking for c in checked.corrections):
                        raise ValueError("Blocking review findings remain open after correction")
                else:
                    current_content = await self._invoke("refine", {"content": current_content, "feedback": feedback})
                logger.info(
                    f"Content refined based on {len(feedback)} feedback items, re-reviewing...",
                    agent=self.name
                )
            else:
                raise ValueError("Quality review failed; document cannot enter human approval")

        raise ValueError("Quality review failed")

    async def _coordinate_compliance_validation(
        self, process_name: str, content: str
    ) -> str:
        """Phase 4b: Rakan (access) + Abeer (problem) validate compliance of the final SOP."""
        logger.info("Phase 4b: Coordinating compliance validation", agent=self.name)

        validation_tasks = []

        # Rakan: Access compliance validation
        if self._uses_specialist("access") and "AccessAgent" in self.worker_agents:
            access_agent = self.worker_agents["AccessAgent"]
            if hasattr(access_agent, 'validate_access_compliance'):
                access_validation = self._invoke("access_compliance", {"content": content,
                    "regulations": self.context.get("workflow", {}).get("applicable_standards", [])})
                validation_tasks.append(("access_compliance", access_validation))

        # Abeer: Problem Management compliance validation
        if self._uses_specialist("problem") and "ProblemAgent" in self.worker_agents:
            problem_agent = self.worker_agents["ProblemAgent"]
            if hasattr(problem_agent, 'validate_problem_compliance'):
                problem_validation = self._invoke("problem_compliance", {"process_name": process_name, "content": content})
                validation_tasks.append(("problem_compliance", problem_validation))

        if validation_tasks:
            results = await asyncio.gather(
                *[task for _, task in validation_tasks],
                return_exceptions=True
            )

            for (task_name, _), result in zip(validation_tasks, results):
                if isinstance(result, asyncio.CancelledError):
                    raise result
                if isinstance(result, BaseException):
                    raise RuntimeError(f"Compliance validation '{task_name}' failed") from result
                gate = ComplianceResult.from_legacy(result)
                if not gate.compliant:
                    raise ValueError(f"Compliance check '{task_name}' did not pass; human approval is unavailable")

                if task_name == "access_compliance" and isinstance(result, dict):
                    self.context["access_compliance_validation"] = result
                    findings = result.get("findings", [])
                    if findings:
                        logger.info(
                            f"Access compliance validation: {len(findings)} findings",
                            agent=self.name
                        )

                elif task_name == "problem_compliance" and isinstance(result, dict):
                    self.context["problem_compliance_validation"] = result
                    is_compliant = result.get("compliant", False)
                    logger.info(
                        f"Problem compliance validation: {'compliant' if is_compliant else 'findings detected'}",
                        agent=self.name
                    )

        return content

    async def _coordinate_formatting(
        self, content: str, output_formats: List[str], process_name: str = "document"
    ) -> Dict[str, str]:
        """Phase 5: Coordinate formatting and export (Bee)."""
        logger.info(f"Phase 5: Coordinating formatting for {output_formats}", agent=self.name)

        output_files = {}

        if "FormatAgent" in self.worker_agents:
            output_files = await self._invoke("format", {"content": content, "output_formats": output_formats, "process_name": process_name})

        self.context["output_files"] = output_files
        return output_files

    async def _coordinate_delivery(
        self, process_name: str, output_files: Dict[str, str]
    ) -> Dict:
        """Prepare local drafts and a record for an explicit human decision."""
        record_path = Path(self.context["run_dir"]) / "approval.json"
        record = create_pending_record(
            record_path, process_name, output_files,
            self.context["last_review"]["quality_score"],
            supporting_records={phase: str(record_path.parent / f"{phase}.json")
                                for phase in ("ready", "exported") if (record_path.parent / f"{phase}.json").is_file()},
        )
        return {
            "process_name": process_name,
            "output_files": output_files,
            "delivery_status": record.status,
            "quality_score": record.quality_score,
            "approval_record": str(record_path),
        }

    async def review_existing(self, source, *, local_only=False, allow_external_ai=False, local_author=False) -> Dict:
        """Read-only review of a finished SOP into a NEW run folder; the source file is never written.

        local_author=True takes the assessments from files written in a Claude Code session
        (src/agents/file_workers.py); it makes no provider call and needs no --allow-external-ai.
        """
        from ..utils.existing_sops import template_gaps, findings_markdown, require_unique_sections, duplicate_sections
        if self.workflow_status == "running":
            raise RuntimeError("This leader already has a running workflow; use a separate instance")
        profile = config_manager.document_profile
        if local_author:
            from .file_workers import FileReviewWorker
            worker = self.worker_agents.get("ReviewAgent")
            if local_only or not isinstance(worker, FileReviewWorker) or worker.excerpts_only:
                raise ValueError("local_author needs the file-backed ReviewAgent worker with every assessment written")
        if not local_only:
            if not (local_author or allow_external_ai or config_manager.system_config.allow_external_ai):
                raise PermissionError("Authorize sending this SOP to Anthropic with --allow-external-ai, or use --local-only")
            if "ReviewAgent" not in self.worker_agents:
                raise ValueError("Required agents missing: ReviewAgent")
            require_unique_sections(source.content, profile)
        run_dir = config_manager.system_config.output_dir / "runs" / uuid4().hex
        self.context = {"run_dir": str(run_dir), "job": "review", "source_path": str(source.path)}
        self._begin_workflow(source.path.name, ["template_check", *([] if local_only else ["review"]), "findings_record"])
        # A local-author run keeps external AI off, so any provider call would be refused.
        runtime = None if local_only else RunRuntime(config_manager.system_config.model_copy(update={"allow_external_ai": not local_author}))
        token = current_runtime.set(runtime)
        store = None
        summary = lambda: runtime.summary() if runtime else {"calls": [], "accounted_tokens": 0}
        try:
            store = RunStore(run_dir, source.path.name, [])
            self._task_store = store
            store.state.update(job="review", mode="local_only" if local_only else "model")
            if local_author:
                store.state["authoring"] = "claude_code_session"
            store.save("source", source.record())
            async with self._phase("template_check"):
                gaps = template_gaps(source.content, profile)
            review = {"issues": [], "summaries": [],
                      "section_locations": {} if duplicate_sections(source.content, profile) else section_map(source.content, profile)}
            if not local_only:
                async with self._phase("review"):
                    review = await self._invoke("review_existing", {"content": source.content})
                    if review.get("document_sha256") != sha(source.content):
                        raise ValueError("Review does not bind the SOP that was read")
            async with self._phase("findings_record"):
                findings = {"job": "review", "mode": store.state["mode"], "source_path": str(source.path),
                            "source_kind": source.kind, "source_sha256": source.sha256,
                            "document_sha256": sha(source.content), "template_gaps": gaps,
                            "findings": review["issues"], "summaries": review["summaries"],
                            "section_locations": review["section_locations"], "verification": "unverified"}
                store.save("findings", findings)
                (run_dir / "findings.md").write_text(findings_markdown(findings), encoding="utf-8")
            self._finish_workflow("review_complete")
            store.finish("review_complete", summary())
            self.context["findings"] = findings
            return findings
        except BaseException as e:
            self._finish_workflow("cancelled" if isinstance(e, asyncio.CancelledError) else "failed")
            if store:
                store.finish("cancelled" if isinstance(e, asyncio.CancelledError) else "failed", summary(), type(e).__name__)
            raise
        finally:
            if store:
                store.close()
            current_runtime.reset(token)
            self._task_store = None

    async def revise_existing(self, source, findings, *, allow_external_ai=False, origin=None,
                              local_author=False) -> Dict[str, str]:
        """Targeted revision of a finished SOP into a NEW run, ending at awaiting_human_approval.

        Only the sections named by the findings may change; the source file is never written.
        local_author=True takes the patch and recheck from files written in a Claude Code session
        (src/agents/file_workers.py); it makes no provider call and needs no --allow-external-ai.
        """
        from ..utils.existing_sops import require_unique_sections, splice_docx, load_sop, changes_markdown
        from ..utils.validation import missing_sections, safe_filename
        if self.workflow_status == "running":
            raise RuntimeError("This leader already has a running workflow; use a separate instance")
        if local_author:
            from .file_workers import FilePatchWorker, FileRecheckWorker
            if not (isinstance(self.worker_agents.get("ContentAgent"), FilePatchWorker)
                    and isinstance(self.worker_agents.get("ReviewAgent"), FileRecheckWorker)):
                raise ValueError("local_author needs the file-backed ContentAgent and ReviewAgent workers")
        elif not (allow_external_ai or config_manager.system_config.allow_external_ai):
            raise PermissionError("Authorize sending this SOP to Anthropic with --allow-external-ai")
        missing = {"ContentAgent", "ReviewAgent"} - self.worker_agents.keys()
        if missing:
            raise ValueError(f"Required agents missing: {', '.join(sorted(missing))}")
        profile = config_manager.document_profile
        content = source.content
        require_unique_sections(content, profile)
        # A conforming SOP keeps the full 11-section checks used by generate.
        complete = not missing_sections(content, profile)
        targets = {f["section_id"] for f in findings}
        run_dir = config_manager.system_config.output_dir / "runs" / uuid4().hex
        self.context = {"run_dir": str(run_dir), "job": "revise", "source_path": str(source.path)}
        self._begin_workflow(source.path.name, ["revision", "recheck", "formatting", "human_review_record"])
        # A local-author run keeps external AI off, so any provider call would be refused.
        runtime = RunRuntime(config_manager.system_config.model_copy(update={"allow_external_ai": not local_author}))
        token = current_runtime.set(runtime)
        store = None
        try:
            formats = ["markdown", "docx"] if source.kind == "docx" else ["markdown"]
            store = RunStore(run_dir, source.path.name, formats)
            self._task_store = store
            store.state.update(job="revise", origin=origin or {}, full_profile_checks=complete)
            if local_author:
                store.state["authoring"] = "claude_code_session"
            store.save("source", source.record())
            async with self._phase("revision"):
                revised = await self._invoke("revise_finished", {"content": content, "findings": findings,
                                                                 "require_complete": complete, "finished_sop": True})
                assert_only_targets_changed(content, revised, targets, profile, require_complete=complete)
                assert_no_new_references(content, revised, targets, profile, require_complete=complete)
            async with self._phase("recheck"):
                recheck = await self._invoke("recheck_finished", {"content": revised, "findings": findings,
                                                                  "require_complete": complete, "finished_sop": True})
                checked = CorrectionAssessment.model_validate({"corrections": recheck.get("corrections")}).validate_against(
                    revised, findings, profile, complete)
                if recheck.get("document_sha256") != sha(revised):
                    raise ValueError("Correction recheck does not bind the revised document")
                blocking = {f["finding_id"] for f in findings if f.get("blocking")}
                if any(c.status != "resolved" and c.finding_id in blocking for c in checked.corrections):
                    raise ValueError("Blocking findings remain open after revision; nothing was delivered")
                resolved = sum(c.status == "resolved" for c in checked.corrections)
                store.save("revised", {"content": revised, "before_sha256": sha(content), "after_sha256": sha(revised),
                                       "target_sections": sorted(targets), "findings": findings, "recheck": recheck})
            async with self._phase("formatting"):
                stem = safe_filename(source.path.stem) + "_revised"
                outputs = {"markdown": str(run_dir / f"{stem}.md")}
                Path(outputs["markdown"]).write_text(revised, encoding="utf-8")
                if source.kind == "docx":
                    new = section_map(revised, profile)
                    bodies = {key: revised[new[key]["body_start"]:new[key]["end"]].strip() for key in targets}
                    outputs["docx"] = str(splice_docx(source, bodies, profile, run_dir / f"{stem}.docx"))
                    # Re-read the spliced file: every other Word section must still read the same.
                    assert_only_targets_changed(content, load_sop(outputs["docx"]).content, targets, profile,
                                                require_complete=complete)
                validate_output_files(outputs, formats)
                (run_dir / "changes.md").write_text(changes_markdown(content, revised, source.path.name), encoding="utf-8")
            async with self._phase("human_review_record"):
                record_path = run_dir / "approval.json"
                # The record's score field holds the share of findings the model recheck marked resolved.
                score = round(100 * resolved / len(checked.corrections))
                store.state["quality_score_basis"] = "percentage of findings the model recheck marked resolved"
                create_pending_record(record_path, source.path.name, outputs, score,
                                      supporting_records={"revised": str(run_dir / "revised.json"),
                                                          "changes": str(run_dir / "changes.md")})
                self.context["delivery"] = {"output_files": outputs, "approval_record": str(record_path),
                                            "delivery_status": "awaiting_human_approval", "quality_score": score}
            self._finish_workflow("awaiting_human_approval")
            store.finish("awaiting_human_approval", runtime.summary())
            if source.sha256 != hashlib.sha256(source.path.read_bytes()).hexdigest():
                logger.warning("The original SOP changed on disk during the revision", agent=self.name)
            return outputs
        except BaseException as e:
            self._finish_workflow("cancelled" if isinstance(e, asyncio.CancelledError) else "failed")
            if store and isinstance(e, UnparsedReplyError):
                # Local diagnostic beside source.json in the git-ignored run folder; never logged or sent.
                path = run_dir / "unparsed_reply.txt"
                with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as stream:
                    stream.write(e.reply)
                store.state["unparsed_reply"] = path.name
                self.context["unparsed_reply"] = str(path)
            if store:
                store.finish("cancelled" if isinstance(e, asyncio.CancelledError) else "failed", runtime.summary(), type(e).__name__)
            raise
        finally:
            if store:
                store.close()
            current_runtime.reset(token)
            self._task_store = None

    def get_status(self) -> Dict:
        """Actual phase counters for the latest started workflow on this instance."""
        return {
            "leader": self.name,
            "workers": list(self.worker_agents.keys()),
            "active_tasks": len([t for t in self.current_tasks if t.status == "in_progress"]),
            "completed_tasks": len([t for t in self.current_tasks if t.status == "completed"]),
            "reused_tasks": len([t for t in self.current_tasks if t.status == "reused"]),
            "pending_tasks": len([t for t in self.current_tasks if t.status == "pending"]),
            "failed_tasks": len([t for t in self.current_tasks if t.status == "failed"]),
            "cancelled_tasks": len([t for t in self.current_tasks if t.status == "cancelled"]),
            "skipped_tasks": len([t for t in self.current_tasks if t.status == "skipped"]),
            "workflow_status": self.workflow_status,
            "current_phase": self.current_phase,
            "tasks": [task.snapshot() for task in self.current_tasks],
            "context_keys": list(self.context.keys())
        }
