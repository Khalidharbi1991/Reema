"""Offline behavioral baselines; fake completions do not measure model reasoning."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agents import AccessAgent, ContentAgent, DataAgent, ProblemAgent, ReviewAgent, SecretaryAgent
from src.utils.handoffs import (
    AgentHandoff, ComplianceResult, EvidenceReference,
    ReviewResult, adapt_handoff, payload_json,
)
from src.utils.provider import RunRuntime, current_runtime
from tests.test_phase01 import catalog, pipeline


@pytest.mark.parametrize("kind", ["access_analysis", "access_content", "problem_content", "analytics"])
def test_long_specialist_inputs_preserve_tail_and_metadata(kind):
    payload = {"requirement_id": "REQ-TAIL-451", "body": "x" * 12000 + "DISTINCT_TAIL [SRC-tail]",
               "assumptions": ["Platform is not confirmed"], "unresolved_questions": ["Who owns approval?"]}
    if kind == "access_analysis":
        prompt = AccessAgent(api_key="")._build_access_analysis_prompt("Access", ["ISO"], payload)
    elif kind == "access_content":
        prompt = AccessAgent(api_key="")._build_access_content_prompt("Access", payload)
    elif kind == "problem_content":
        prompt = ProblemAgent(api_key="")._build_problem_content_prompt("Problem", payload)
    else:
        prompt = DataAgent(api_key="")._build_analytics_prompt("Incident", ["MTTR"], payload)
    assert "DISTINCT_TAIL [SRC-tail]" in prompt and "REQ-TAIL-451" in prompt
    assert "Who owns approval?" in prompt and "Platform is not confirmed" in prompt


def test_metric_fields_and_standards_extensions_are_not_dropped():
    metrics = [{"name": "MTTR", "description": "Resolution time", "formula": "resolved_minutes / resolved_count",
                "unit": "minutes", "exclusions": ["Open incidents"], "target": None}]
    assert payload_json(metrics) in DataAgent(api_key="")._build_dashboard_prompt("Incident", metrics)
    research = {"research": {"raw_research": "Research", "requirement_ids": ["REQ-99"]},
                "standards": {"compliance_analysis": "Controls", "unresolved_questions": ["Applicable jurisdiction?"]}}
    content = ContentAgent(api_key="")
    assert "REQ-99" in content._extract_research_summary(research)
    assert "Applicable jurisdiction?" in content._extract_compliance_summary(research)


def test_handoff_provenance_is_unverified_and_unknown_citations_remain_open():
    payload = {"process_name": "Access", "access_analysis": "Use [SRC-known] and [SRC-missing]",
               "handoff_metadata": {"assumptions": ["Directory provider to confirm"],
                                    "deliverables": [{"name": "Role matrix", "reference": "proposed appendix"}]}}
    result = adapt_handoff("Access", "access", "research", payload, text_key="access_analysis",
                           sources={"SRC-known": {"source": "synthetic.md", "location": "block 5", "sha256": "a" * 64}})
    assert result.payload == payload
    assert result.verification == result.metadata.evidence[0].verification == "unverified"
    assert result.metadata.unresolved_questions == ["Source provenance not recorded for SRC-missing"]
    assert result.metadata.deliverables[0].status == "proposed"
    assert result.metadata.findings == []  # Narrative was not converted into verified findings.
    assert payload["handoff_metadata"].get("evidence") is None


@pytest.mark.parametrize("payload", [None, [], "Narrative without a research mapping", {"raw_research": 42},
    {"process_name": "Wrong process", "raw_research": "Text"},
    {"raw_research": "Text", "handoff_metadata": {"assumptions": "guess"}},
    {"raw_research": "Text", "handoff_metadata": {"findings": [{"description": "Claim", "source_ids": ["SRC-absent"]}]}},
])
def test_malformed_or_incomplete_handoffs_are_rejected(payload):
    with pytest.raises(ValueError):
        adapt_handoff("Incident", "research", "research", payload, text_key="raw_research")


def test_contracts_reject_claimed_verification_and_non_json_values():
    with pytest.raises(ValueError):
        EvidenceReference(source_id="SRC-x", source="source", location="block 1", verification="verified")
    with pytest.raises(ValueError):
        AgentHandoff(process_name="Incident", producer="research", stage="research", payload="", unexpected=True)
    with pytest.raises(ValueError):
        payload_json({"object": object()})
    with pytest.raises(ValueError):
        payload_json({"value": float("nan")})


def test_structured_evidence_cannot_replace_recorded_source_identity():
    payload = {"raw_research": "Use [SRC-known]", "handoff_metadata": {"evidence": [
        {"source_id": "SRC-known", "source": "different.md", "location": "block 5"}]}}
    with pytest.raises(ValueError, match="identity conflicts"):
        adapt_handoff("Incident", "research", "research", payload,
                      sources={"SRC-known": {"source": "actual.md", "location": "block 5"}})


@pytest.mark.parametrize("review", [
    {"quality_score": "95"}, {"quality_score": True}, {"quality_score": 101},
    {"quality_score": 95, "needs_revision": "false"},
    {"quality_score": 95, "needs_revision": True, "approval_status": "APPROVED"},
    {"quality_score": 95, "approval_status": "APPROVED", "issues": [{"severity": "critical", "description": "Missing evidence"}]},
    {"quality_score": 95, "refined_content": ""},
])
def test_malformed_and_contradictory_reviews_are_rejected(review):
    with pytest.raises(ValueError):
        ReviewResult.from_legacy(review)


def test_contradictory_compliance_gate_is_rejected():
    with pytest.raises(ValueError, match="Contradictory"):
        ComplianceResult.from_legacy({"compliant": True, "findings": ["Missing approval evidence"]})


@pytest.mark.asyncio
async def test_long_handoffs_reach_real_prompt_builders_review_and_export(pipeline, sample_sop_content, section_replies):
    leader, config, workers = pipeline
    source_id = "SRC-tail"
    source = {"source": "synthetic-controls.md", "location": "block 99", "sha256": "a" * 64}

    async def access_research(*args):
        current_runtime.get().sources[source_id] = source
        return {"process_name": "Change Management", "access_analysis": "R" * 12000 + "REQ-END [SRC-tail]",
                "handoff_metadata": {"assumptions": ["Directory vendor unconfirmed"]}}

    workers["AccessAgent"].analyze_access_requirements.side_effect = access_research
    access = AccessAgent(api_key="")
    access._call_claude = AsyncMock(return_value="A" * 9000 + "ACCESS-END [SRC-tail]")
    workers["AccessAgent"].generate_access_content = access.generate_access_content
    problem = ProblemAgent(api_key="")
    problem._call_claude = AsyncMock(return_value="P" * 9000 + "PROBLEM-END [SRC-tail]")
    workers["ProblemAgent"].generate_problem_content = problem.generate_problem_content
    workers["DataAgent"].create_dashboard_design.return_value = {"dashboard_design": "D" * 9000 + "DASHBOARD-END [SRC-tail]"}
    content = ContentAgent(api_key="")
    content._call_claude = AsyncMock(side_effect=section_replies(sample_sop_content))
    workers["ContentAgent"].generate_sop = content.generate_sop
    review = ReviewAgent(api_key="")
    review._call_claude = AsyncMock(return_value=json.dumps({"quality_score": 95, "decision": "acceptable",
        "issues": [], "recommendations": [], "summary": "Synthetic assessment"}))
    workers["ReviewAgent"].review_content = review.review_content
    outputs = await leader.generate_documentation("Change Management", ["markdown"], specialists=["access", "problem", "data"])
    prompt = access._call_claude.await_args.kwargs["messages"][0]["content"]
    assert "REQ-END [SRC-tail]" in prompt and "Directory vendor unconfirmed" in prompt
    assert all("REQ-END [SRC-tail]" in call.args[0][0]["content"] for call in content._call_claude.await_args_list)
    assessment_prompts = "\n".join(call.args[0][0]["content"] for call in review._call_claude.await_args_list)
    exported = Path(outputs["markdown"]).read_text()
    for tail in ("ACCESS-END", "PROBLEM-END", "DASHBOARD-END"):
        assert tail in assessment_prompts and tail in exported
    assert leader.context["handoffs"]["research:access"]["metadata"]["evidence"][0]["source_id"] == source_id
    ready = json.loads((Path(leader.context["run_dir"]) / "ready.json").read_text())
    assert leader.context["last_review"]["coverage"]["characters_reviewed"] == len(ready["content"])
    assert exported.endswith(ready["content"])  # Formatter may add its deterministic title.
    assert "REQ-END" in ready["handoffs"]["research:access"]["payload"]["access_analysis"]


@pytest.mark.asyncio
async def test_full_specialist_input_exceeding_budget_is_rejected_before_provider(catalog, monkeypatch):
    from src.agents import base_agent
    monkeypatch.setattr(base_agent.config_manager, "system_config", catalog.system_config)
    catalog.system_config.max_prompt_chars = 10000
    agent = AccessAgent(api_key="")
    agent.client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    token = current_runtime.set(RunRuntime(catalog.system_config))
    try:
        with pytest.raises(ValueError, match="MAX_PROMPT_CHARS"):
            await agent.generate_access_content("Access", {"requirements": "x" * 12000 + "MANDATORY-TAIL"})
    finally:
        current_runtime.reset(token)
    agent.client.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_communication_record_does_not_claim_dispatch():
    secretary = SecretaryAgent(api_key="")
    secretary._call_claude = AsyncMock()
    result = await secretary.coordinate_team_communication("Check pending evidence", "Abdullah", ["Agent 2"])
    assert result["status"] == "recorded" and result["dispatch_status"] == "not_dispatched"
    assert secretary.communication_log == [result]
    secretary._call_claude.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_phase_status_is_visible_and_persisted(pipeline):
    leader, _, workers = pipeline
    started, release = asyncio.Event(), asyncio.Event()

    async def waiting(*args):
        started.set()
        await release.wait()
        return {"raw_research": "Research"}

    workers["ResearchAgent"].research_process.side_effect = waiting
    run = asyncio.create_task(leader.generate_documentation("Change Management", ["markdown"]))
    try:
        await asyncio.wait_for(started.wait(), 2)
        status = leader.get_status()
        assert status["workflow_status"] == "running" and status["current_phase"] == "research"
        assert status["active_tasks"] == 1 and status["completed_tasks"] == 1 and status["pending_tasks"] == 6
        recorded = json.loads((Path(leader.context["run_dir"]) / "run.json").read_text())
        assert recorded["tasks"] == status["tasks"]
        with pytest.raises(RuntimeError, match="already has a running"):
            await leader.generate_documentation("Change Management", ["markdown"])
    finally:
        release.set()
        await run
    status = leader.get_status()
    assert status["workflow_status"] == "awaiting_human_approval" and status["completed_tasks"] == 8
    assert status["active_tasks"] == status["pending_tasks"] == 0
    assert all(item["started_at"] and item["finished_at"] for item in status["tasks"])
    await leader.generate_documentation("Change Management", ["markdown"])
    assert leader.get_status()["completed_tasks"] == 8  # Latest run, not an accumulated counter.


@pytest.mark.asyncio
@pytest.mark.parametrize("cancelled", [False, True])
async def test_failure_and_cancellation_record_actual_phase_and_skip_future_work(pipeline, cancelled):
    leader, _, workers = pipeline
    started = asyncio.Event()

    async def wait_or_fail(*args):
        started.set()
        if not cancelled:
            raise RuntimeError("Synthetic research outage")
        await asyncio.Event().wait()

    workers["ResearchAgent"].research_process.side_effect = wait_or_fail
    run = asyncio.create_task(leader.generate_documentation("Change Management", ["markdown"]))
    await asyncio.wait_for(started.wait(), 2)
    if cancelled:
        run.cancel()
    with pytest.raises(asyncio.CancelledError if cancelled else RuntimeError):
        await run
    status = leader.get_status()
    expected = "cancelled" if cancelled else "failed"
    assert status["workflow_status"] == expected and status["current_phase"] == "research"
    assert status[expected + "_tasks"] == 1 and status["completed_tasks"] == 1
    assert status["active_tasks"] == 0 and status["skipped_tasks"] == 6
    workers["ContentAgent"].generate_sop.assert_not_awaited()
    state = json.loads((Path(leader.context["run_dir"]) / "run.json").read_text())
    assert state["status"] == expected and state["tasks"] == status["tasks"]


@pytest.mark.asyncio
async def test_malformed_research_and_contradictory_compliance_block_downstream_work(pipeline):
    leader, config, workers = pipeline
    workers["ResearchAgent"].research_process.return_value = {"raw_research": ["Wrong type"]}
    with pytest.raises(ValueError, match="raw_research"):
        await leader.generate_documentation("Change Management", ["markdown"])
    workers["ContentAgent"].generate_sop.assert_not_awaited()
    workers["ResearchAgent"].research_process.return_value = {"raw_research": "Research"}
    workers["AccessAgent"].validate_access_compliance.return_value = {"compliant": True, "findings": ["Evidence absent"]}
    with pytest.raises(ValueError, match="Contradictory"):
        await leader.generate_documentation("Change Management", ["markdown"], specialists=["access"])
    assert not list(config.system_config.output_dir.rglob("approval.json"))
    assert leader.get_status()["failed_tasks"] == 1


@pytest.mark.asyncio
async def test_missing_evidence_model_decision_fails_closed(pipeline, sample_sop_content, monkeypatch):
    leader, catalog, workers = pipeline
    monkeypatch.setattr(catalog.document_profile, "max_review_cycles", 1)
    quote = "Version 1.0 - Initial draft"
    start = sample_sop_content.index(quote)
    review = ReviewAgent(api_key="")
    review._call_claude = AsyncMock(return_value=json.dumps({"quality_score": 98, "decision": "revise",
        "issues": [{"severity": "critical", "description": "Evidence missing for asserted approval", "section_id": "sec-control",
                    "quote": quote, "start": start, "end": start + len(quote), "action": "Obtain the approval record"}],
        "recommendations": ["Obtain the approval record"], "summary": "Synthetic missing-evidence decision"}))
    workers["ReviewAgent"].review_content = review.review_content
    with pytest.raises(ValueError, match="Quality review failed"):
        await leader.generate_documentation("Change Management", ["markdown"])
    assert not (Path(leader.context["run_dir"]) / "approval.json").exists()


@pytest.mark.asyncio
async def test_contradictory_review_is_rejected_at_workflow_boundary(pipeline):
    leader, _, workers = pipeline
    workers["ReviewAgent"].review_content.return_value = {
        "quality_score": 99, "approval_status": "APPROVED", "needs_revision": True}
    with pytest.raises(ValueError, match="Contradictory"):
        await leader.generate_documentation("Change Management", ["markdown"])
    assert leader.get_status()["current_phase"] == "review"
    assert leader.get_status()["failed_tasks"] == 1
    assert not (Path(leader.context["run_dir"]) / "approval.json").exists()


@pytest.mark.asyncio
async def test_unauthorized_specialist_request_never_reaches_provider(catalog, monkeypatch):
    from src.agents import base_agent
    catalog.system_config.allow_external_ai = False
    monkeypatch.setattr(base_agent.config_manager, "system_config", catalog.system_config)
    agent = AccessAgent(api_key="")
    agent.client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    with pytest.raises(PermissionError, match="External AI"):
        await agent.generate_access_content("Access", {"requirements": "x" * 12000 + "TAIL"})
    agent.client.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_resume_cancellation_tracks_only_export_phases(pipeline):
    leader, config, workers = pipeline
    await leader.generate_documentation("Change Management", ["markdown"])
    original = Path(leader.context["run_dir"])
    started = asyncio.Event()

    async def waiting(*args):
        started.set()
        await asyncio.Event().wait()

    workers["FormatAgent"].convert_to_formats = waiting
    config.system_config.allow_external_ai = False
    run = asyncio.create_task(leader.resume_formatting(original, ["markdown"]))
    await asyncio.wait_for(started.wait(), 2)
    assert leader.get_status()["active_tasks"] == 1 and len(leader.current_tasks) == 2
    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run
    status = leader.get_status()
    assert status["workflow_status"] == "cancelled" and status["cancelled_tasks"] == 1
    assert status["skipped_tasks"] == 1 and status["completed_tasks"] == 0
    assert workers["FormatAgent"].output_dir == config.system_config.output_dir
    state = json.loads((Path(leader.context["run_dir"]) / "run.json").read_text())
    assert state["status"] == "cancelled" and state["tasks"] == status["tasks"]


@pytest.mark.asyncio
async def test_source_preparation_failure_is_a_failed_planning_phase(pipeline, monkeypatch):
    from src.agents import leader_agent
    leader, _, workers = pipeline

    def changed_source(settings):
        raise ValueError("Source changed")

    monkeypatch.setattr(leader_agent, "ReferenceIndex", changed_source)
    with pytest.raises(ValueError, match="Source changed"):
        await leader.generate_documentation("Change Management", ["markdown"])
    status = leader.get_status()
    assert status["current_phase"] == "planning" and status["failed_tasks"] == 1
    assert status["skipped_tasks"] == 7 and status["completed_tasks"] == 0
    workers["ResearchAgent"].research_process.assert_not_awaited()
