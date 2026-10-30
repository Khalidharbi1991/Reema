"""Abdullah (Leader Agent) - runs the local SOP jobs whose text a Claude Code session wrote.

Generate (generate_local), the phases:
  planning — request, standards, KPIs and the unassessed control register
  content — the section files through ContentAgent.generate_sop, plus Agent 10's patch appendix
  checks — template, RACI, standards, citations, flows and control coverage
  formatting — Agent 5 exports PDF/DOCX/MD/HTML
  human_review_record — hash-verified drafts awaiting a human decision
Review (review_existing) and revise (revise_existing) use the file-backed workers the same way.
No method here calls a model.
"""

import asyncio
import hashlib
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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
from ..utils.handoffs import adapt_handoff, ReviewResult
from ..utils.documents import (ControlRegister, legacy_register, control_coverage, section_map,
                               validate_located_review, CorrectionAssessment, sha, assert_only_targets_changed,
                               assert_no_new_references)
from ..utils.diagrams import extract_flows
from ..utils.specialists import SpecialistInputs, specialist_checks
from ..utils.ownership import RunLease
from ..utils.coordination import DocumentationRequest, WorkflowPlan
from ..utils.capabilities import invoke_pipeline


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
        self.executed_calls = 0

    def snapshot(self):
        return {"agent": self.agent_name, "phase": self.task_type, "status": self.status,
                "started_at": self.started_at, "finished_at": self.finished_at,
                "error_type": self.error_type, "executed_calls": self.executed_calls}


class LeaderAgent:
    """
    Abdullah (Leader/Orchestrator Agent)

    Responsibilities:
    - Receives user requests for process documentation
    - Breaks down tasks and assigns to specialized worker agents
    - Coordinates the local generate, review and revise jobs
    - Performs final quality control and validation
    - Assembles final output in requested format(s)
    - Manages state and context across the agent team
    - Leads the SOP jobs only; Ahmad is the main Claude Code session
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
    async def _phase(self, name):
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
            task.status = "completed"
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

    async def _invoke(self, capability, arguments):
        task = next((t for t in self.current_tasks if t.task_type == self.current_phase), None)
        if task:
            task.executed_calls += 1
            self._save_task_status()
        return await invoke_pipeline(self.worker_agents, capability, arguments)

    @staticmethod
    def documentation_request(process_name, output_formats=None, *, custom=False, specialists=None, objective=None,
                              constraints=None, required_deliverables=None, acceptance_criteria=None,
                              specialist_inputs=None):
        """Resolve the process and build the validated request; local, no model call."""
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
        return process_id, DocumentationRequest(
            process_name=process_name, custom=custom, formats=output_formats, specialists=sorted(selected),
            objective=objective or f"Document {process_name} as an operational SOP",
            constraints=list(dict.fromkeys(definition.get("constraints", []) + (constraints or []))),
            required_deliverables=required_deliverables or ["SOP", *output_formats],
            acceptance_criteria=list(dict.fromkeys(definition.get("acceptance_criteria", []) + (acceptance_criteria or []))),
            specialist_inputs=specialist_inputs)

    @staticmethod
    def check_draft(content, standards, sources, register):
        """Every local check a generated SOP must pass before export; returns the quality report."""
        profile = config_manager.document_profile
        validate_sop(content)
        section_map(content, profile, require_complete=True)
        extract_flows(content)
        quality = validate_quality(content, standards, sources)
        controls = control_coverage(content, register, sources, profile)
        if controls["errors"]:
            raise ValueError("Control coverage failed: " + "; ".join(controls["errors"]))
        quality["control_coverage"] = controls
        quality["warnings"].extend(controls["warnings"])
        return quality

    async def generate_local(self, process_name, output_formats=None, *, custom=False, specialists=None, objective=None,
                             constraints=None, acceptance_criteria=None, specialist_inputs=None, evidence=None,
                             endpoint_appendix=None, origin=None) -> Dict[str, str]:
        """Generate an SOP whose section text was written in a Claude Code session; no model call.

        The ContentAgent must be the file-backed FileSectionWriter (src/agents/file_workers.py), so each
        section runs through the unchanged per-section loop and checks in ContentAgent.generate_sop.
        REEMA plans, checks, exports and writes the pending approval record. No model reviews the draft,
        so the record's quality_score is None. evidence is the list of manifest-allowed reference
        excerpts the writer was given; [SRC-...] citations must name one of them.

        Specialists: euc adds Agent 10's patch appendix, written in Claude Code (endpoint_appendix).
        access, problem and data add no appendix; the local checks on any supplied specialist data are
        recorded with the plan as data.
        """
        from .euc_agent import EUCAgent
        from .file_workers import FileSectionWriter
        if self.workflow_status == "running":
            raise RuntimeError("This leader already has a running workflow; use a separate instance")
        if not isinstance(self.worker_agents.get("ContentAgent"), FileSectionWriter) or "FormatAgent" not in self.worker_agents:
            raise ValueError("A Claude Code generate run needs the file-backed ContentAgent and the FormatAgent")
        process_id, request = self.documentation_request(
            process_name, output_formats, custom=custom, specialists=specialists, objective=objective,
            constraints=constraints, acceptance_criteria=acceptance_criteria, specialist_inputs=specialist_inputs)
        if ("euc" in request.specialists) != (endpoint_appendix is not None):
            raise ValueError("The euc specialist needs Agent 10's patch appendix, and only it takes one")
        if endpoint_appendix is not None:
            EUCAgent.check_appendix(endpoint_appendix)
        process_name, output_formats = request.process_name, request.formats
        formatter = self.worker_agents["FormatAgent"]
        formatter.validate_requested_formats(output_formats)
        if config_manager.system_config.enforce_page_target and "pdf" not in output_formats:
            raise ValueError("ENFORCE_PAGE_TARGET requires PDF output for a real rendered page count")
        self.context = {"process_id": process_id, "specialists": request.specialists, "request": request.model_dump(),
                        "last_review": None}
        run_dir = config_manager.system_config.output_dir / "runs" / uuid4().hex
        self.context["run_dir"] = str(run_dir)
        original_output_dir = formatter.output_dir
        formatter.output_dir = run_dir
        # External AI stays off, so any provider call would be refused.
        runtime = RunRuntime(config_manager.system_config.model_copy(update={"allow_external_ai": False}))
        runtime.sources = {record["id"]: {key: value for key, value in record.items() if key != "text"}
                           for record in evidence or []}
        token = current_runtime.set(runtime)
        store = None
        self._begin_workflow(process_name, ["planning", "content", "checks", "formatting", "human_review_record"])
        try:
            store = RunStore(run_dir, process_name, output_formats)
            self._task_store = store
            store.state.update(job="generate", authoring="claude_code_session", origin=origin or {})
            async with self._phase("planning"):
                workflow = await self._plan_workflow(process_name)
                register = legacy_register(workflow["applicable_standards"])
                self.context["control_register"] = register.model_dump()
                if request.specialist_inputs:
                    workflow["specialist_checks"] = specialist_checks(
                        request.specialist_inputs, runtime.sources, config_manager.specialist_policy)
                store.save("planned", workflow)
            async with self._phase("content"):
                content = await self._invoke("content", {"process_name": process_name, "research_data": {
                    "standards": {"control_register": self.context["control_register"]}}})
                if endpoint_appendix is not None:
                    content += "\n\n" + self._format_euc_section(endpoint_appendix, process_name)
                store.save("generated", {"content": content, "sources": runtime.sources})
            async with self._phase("checks"):
                quality = self.check_draft(content, workflow["applicable_standards"], runtime.sources, register)
                self.context["quality"] = quality
                store.save("ready", {"content": content, "review": None, "sources": runtime.sources,
                                     "standards": workflow["applicable_standards"], "quality": quality,
                                     "control_register": self.context["control_register"],
                                     "document_profile": config_manager.document_profile.model_dump()})
            async with self._phase("formatting"):
                output_files = await self._coordinate_formatting(content, output_formats, process_name)
                validate_output_files(output_files, output_formats)
                self._check_page_count(output_files, quality)
                store.save("exported", {"outputs": output_files, "quality": quality, "sources": runtime.sources,
                                        "export_checks": getattr(formatter, "last_export_checks", {})})
            async with self._phase("human_review_record"):
                self.context["delivery"] = await self._coordinate_delivery(process_name, output_files)
            self._finish_workflow("awaiting_human_approval")
            store.finish("awaiting_human_approval", runtime.summary())
            return output_files
        except BaseException as error:
            self._finish_workflow("cancelled" if isinstance(error, asyncio.CancelledError) else "failed")
            if store:
                store.finish(self.workflow_status, runtime.summary(), type(error).__name__)
            raise
        finally:
            if store:
                store.close()
            current_runtime.reset(token)
            formatter.output_dir = original_output_dir
            self._task_store = None

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

    async def export_run(self, directory, formats=None):
        """Export a run's unchanged ready checkpoint again, into a NEW run awaiting approval; no model call.

        A Claude Code generate run has no model review: its draft runs through every local check again.
        An older API run keeps its review gate. Either way the new run needs a fresh human decision.
        """
        with RunLease(directory) as lease:
            return await self._export_run(directory, formats, lease)

    async def _export_run(self, directory, formats, lease):
        if self.workflow_status == "running":
            raise RuntimeError("This leader already has a running workflow; use a separate instance")
        state, ready = load_ready(directory, lease=lease)
        formats = validate_formats(formats or state["formats"])
        formatter = self.worker_agents["FormatAgent"]
        formatter.validate_requested_formats(formats)
        review = ready["review"]
        if "control_register" in ready and ready.get("document_profile") != config_manager.document_profile.model_dump():
            raise ValueError("Document profile changed; create a new generation")
        if review is None:
            quality = self.check_draft(ready["content"], ready["standards"], ready["sources"],
                                       ControlRegister.model_validate(ready["control_register"]))
        else:
            gate = ReviewResult.from_legacy(review)
            threshold = config_manager.get_agent_config("review_agent")["quality_threshold"]
            if (gate.quality_score < threshold or gate.needs_revision
                    or gate.approval_status not in {None, "APPROVED"}
                    or any(issue.severity == "critical" or issue.blocking for issue in gate.issues)):
                raise ValueError("Checkpoint review does not meet the current quality gate")
            quality = validate_quality(ready["content"], ready["standards"], ready["sources"])
            validate_located_review(review, ready["content"], config_manager.document_profile)
            if "control_register" in ready:
                controls = control_coverage(ready["content"], ControlRegister.model_validate(ready["control_register"]),
                                            ready["sources"], config_manager.document_profile)
                if controls["errors"]:
                    raise ValueError("Checkpoint control coverage failed")
                quality["control_coverage"] = controls
                quality["warnings"].extend(controls["warnings"])
        run_dir = config_manager.system_config.output_dir / "runs" / uuid4().hex
        store = RunStore(run_dir, state["process_name"], formats)
        store.state.update(job="export", exported_from=str(Path(directory).resolve()),
                           **({"authoring": state["authoring"]} if "authoring" in state else {}))
        store.save("ready", ready)
        original_dir, formatter.output_dir = formatter.output_dir, run_dir
        self.context = {"run_dir": str(run_dir), "last_review": review, "quality": quality}
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
            store.finish("awaiting_human_approval", {"calls": [], "accounted_tokens": 0})
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
            "phases": ["content", "checks", "formatting", "human_review_record"]
        }

        request_data = self.context.get("request")
        if request_data:
            request = DocumentationRequest.model_validate(request_data)
            names = ["planning", "content", "checks", "formatting", "human_review_record"]
            plan = WorkflowPlan(request=request, dependencies={name: names[i-1:i] for i, name in enumerate(names)})
            workflow["coordination_plan"] = plan.model_dump()
            workflow["acceptance_gates"] = {"required_sections": 11, "model_review": "none",
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
            (self.context.get("last_review") or {}).get("quality_score"),
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

    async def review_existing(self, source, *, local_only=False, local_author=False) -> Dict:
        """Read-only review of a finished SOP into a NEW run folder; the source file is never written.

        local_only=True runs the template-gap check alone. Otherwise local_author=True is required:
        the assessments come from files written in a Claude Code session (src/agents/file_workers.py),
        and no provider call is made.
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
            if not local_author:
                raise ValueError("A model review runs in Claude Code (reema-review skill); here use the local template check")
            require_unique_sections(source.content, profile)
        run_dir = config_manager.system_config.output_dir / "runs" / uuid4().hex
        self.context = {"run_dir": str(run_dir), "job": "review", "source_path": str(source.path)}
        self._begin_workflow(source.path.name, ["template_check", *([] if local_only else ["review"]), "findings_record"])
        # External AI stays off, so any provider call would be refused.
        runtime = None if local_only else RunRuntime(config_manager.system_config.model_copy(update={"allow_external_ai": False}))
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

    async def revise_existing(self, source, findings, *, origin=None, local_author=False, major=False) -> Dict[str, str]:
        """Targeted revision of a finished SOP into a NEW run, ending at awaiting_human_approval.

        Only the sections named by the findings may change; the source file is never written.
        local_author=True is required: the patch and recheck come from files written in a Claude Code
        session (src/agents/file_workers.py), and no provider call is made.
        The draft is named with the next version (X_V2 -> X_V2.1; major=True -> X_V3.0). Only the
        file name carries it: Document Control inside the document is left for the reviewer.
        """
        from ..utils.existing_sops import (require_unique_sections, splice_docx, load_sop, changes_markdown,
                                           file_version, next_revision_stem)
        from ..utils.validation import missing_sections
        if self.workflow_status == "running":
            raise RuntimeError("This leader already has a running workflow; use a separate instance")
        if not local_author:
            raise ValueError("Revisions run in Claude Code (reema-revise skill)")
        from .file_workers import FilePatchWorker, FileRecheckWorker
        if not (isinstance(self.worker_agents.get("ContentAgent"), FilePatchWorker)
                and isinstance(self.worker_agents.get("ReviewAgent"), FileRecheckWorker)):
            raise ValueError("local_author needs the file-backed ContentAgent and ReviewAgent workers")
        profile = config_manager.document_profile
        content = source.content
        require_unique_sections(content, profile)
        # A conforming SOP keeps the full 11-section checks used by generate.
        complete = not missing_sections(content, profile)
        targets = {f["section_id"] for f in findings}
        run_dir = config_manager.system_config.output_dir / "runs" / uuid4().hex
        self.context = {"run_dir": str(run_dir), "job": "revise", "source_path": str(source.path)}
        self._begin_workflow(source.path.name, ["revision", "recheck", "formatting", "human_review_record"])
        # External AI stays off, so any provider call would be refused.
        runtime = RunRuntime(config_manager.system_config.model_copy(update={"allow_external_ai": False}))
        token = current_runtime.set(runtime)
        store = None
        try:
            formats = ["markdown", "docx"] if source.kind == "docx" else ["markdown"]
            store = RunStore(run_dir, source.path.name, formats)
            self._task_store = store
            store.state.update(job="revise", origin=origin or {}, full_profile_checks=complete,
                               authoring="claude_code_session")
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
                stem = next_revision_stem(source.path, config_manager.system_config.output_dir, major=major)
                _, old_major, old_minor = file_version(source.path.stem)
                version = {"from": f"V{old_major}" + (f".{old_minor}" if old_minor else ""),
                           "to": stem.rsplit("_", 1)[-1], "major": bool(major), "document_control": "not updated"}
                store.state["file_version"] = version
                # The run folder is new (RunStore refuses an existing one), so no file is ever overwritten.
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
                (run_dir / "changes.md").write_text(
                    f"File version: {version['to']} (from {version['from']}). The version in Document Control "
                    "inside the document was not changed; update it before approval if needed.\n\n"
                    + changes_markdown(content, revised, source.path.name), encoding="utf-8")
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
