"""Offline setup, evidence, environment, hypothesis, metric and CAD regressions."""

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock

import ezdxf
import pytest
import yaml
from typer.testing import CliRunner

from scripts.dev import native_environment
from src.agents import ResearchAgent, AccessAgent, ProblemAgent, DataAgent, BuildingDesignAgent
from src.utils.config import config_manager
from src.utils.specialists import (SpecialistPolicy, ResearchClaim, assess_claims, check_iam, IAMSnapshot,
    ProblemCase, Hypothesis, assess_problem, MetricSpec, calculate_metric)
from src.knowledge.retrieval import ReferenceIndex, SourcePermission
from src.utils.provider import current_runtime
from tests.test_phase01 import catalog, pipeline

POLICY = SpecialistPolicy()


def source():
    return {"id": "SRC-fixture", "source": "policy.md", "location": "text, characters 1-60", "sha256": "a" * 64,
            "classification": "public", "text": "Retain the decision record.", "published_on": "2026-10-14"}


def evidence(record=None):
    record = record or source()
    return {"source_id": record["id"], **{k: record[k] for k in ("source", "location", "sha256")}, "quote": record["text"]}


def snapshot(record=None):
    return {"snapshot_id": "synthetic-iam", "observed_at": "2026-10-15T10:00:00+03:00", "roles": ["operator"],
            "identities": [{"id": "account-1", "active": True, "privileged": True, "mfa_enabled": True, "roles": ["operator"]}],
            "approvals": [{"subject_id": "account-1", "role": "operator", "approved": True,
                           "approved_at": "2026-10-14T09:00:00+03:00", "evidence": [evidence(record)]}]}


def case(record=None):
    return {"case_id": "synthetic-case", "observations": [
        {"id": "OBS-recovery", "observed_at": "2026-10-15T10:30:00+03:00", "description": "Service recovered", "evidence": []},
        {"id": "OBS-start", "observed_at": "2026-10-15T07:00:00Z", "description": "The incident was recorded", "evidence": [evidence(record)]}]}


def hypotheses():
    return [{"id": "HYP-config", "explanation": "A configuration change may be involved", "supporting_observation_ids": ["OBS-start"],
             "contradicting_observation_ids": [], "next_tests": ["Compare the authorized change log"]},
            {"id": "HYP-load", "explanation": "A load increase may be involved", "supporting_observation_ids": [],
             "contradicting_observation_ids": ["OBS-recovery"], "next_tests": ["Compare supplied load observations"]}]


def metric(kind="ratio", **overrides):
    fields = {"ratio": {"numerator_field": "resolved", "denominator_field": "total", "unit": "percent"},
              "duration_mean": {"start_field": "start", "end_field": "end", "unit": "minutes"},
              "sum": {"value_field": "value", "unit": "number"}, "count": {"unit": "count"}}
    return MetricSpec.model_validate({"id": "MET-example", "name": "Example metric", "kind": kind,
        "owner": "Service owner", "source": "Supplied register", "cadence": "Weekly", **fields[kind], **overrides})


@pytest.mark.parametrize("present", [True, False])
def test_launcher_discovers_only_actual_native_libraries_and_removes_temp_python_paths(tmp_path, present):
    if present:
        (tmp_path / "libgobject-2.0.dylib").touch()
        (tmp_path / "libpango-1.0.dylib").touch()
    original = {"PYTHONPATH": "/private/tmp/unwanted", "PYTHONHOME": "/global", "UNCHANGED": "kept"}
    result = native_environment(original, platform="darwin", candidates=[tmp_path, tmp_path / "absent"])
    assert "PYTHONPATH" not in result and "PYTHONHOME" not in result and result["UNCHANGED"] == "kept"
    assert (result.get("DYLD_FALLBACK_LIBRARY_PATH") == str(tmp_path)) is present
    assert "PYTHONPATH" in original  # No global environment mutation.


@pytest.mark.parametrize("published,expected", [("2026-10-14", "located_unverified"), ("2020-01-01", "stale_support"), (None, "unknown_freshness"), ("2027-01-01", "future_evidence")])
def test_claims_report_real_source_date_status_without_inventing_freshness(published, expected):
    record = {**source(), "published_on": published}
    claim = ResearchClaim(id="CLM-record", text="Retain a decision record", kind="observation", evidence=[evidence(record)])
    result = assess_claims([claim], {record["id"]: record}, "2026-10-15", POLICY)
    assert result["claims"][0]["evidence_status"] == expected
    assert result["claims"][0]["verification"] == "unverified"


@pytest.mark.parametrize("change", ["quote", "source", "location", "sha", "duplicate", "date"])
def test_research_rejects_invented_evidence_or_invalid_assessment_date(change):
    record = source()
    entry = evidence(record)
    if change == "quote": entry["quote"] = "Invented assertion"
    if change == "source": entry["source_id"] = "SRC-missing"
    if change == "location": entry["location"] = "Different location"
    if change == "sha": entry["sha256"] = "b" * 64
    claim = ResearchClaim(id="CLM-record", text="Claim", kind="observation", evidence=[entry])
    with pytest.raises(ValueError):
        assess_claims([claim, claim] if change == "duplicate" else [claim], {record["id"]: record},
                      "2026-W01-1" if change == "date" else "2026-10-15", POLICY)


@pytest.mark.asyncio
async def test_actual_research_carries_unsupported_and_legacy_uncertainty():
    agent = ResearchAgent(api_key="")
    agent.source_records, agent.knowledge_records = [source()], []
    agent._call_claude = AsyncMock(return_value=json.dumps({"raw_research": "Recommendations need validation.", "claims": [
        {"id": "CLM-proposal", "text": "Consider a pilot", "kind": "recommendation", "evidence": []}]}))
    result = await agent.research_process("Example", [], {"as_of": "2026-10-15"})
    assert result["evidence_report"]["claims"][0]["evidence_status"] == "unsupported"
    assert agent._parse_research_response("Legacy prose", "Example")["evidence_report"]["missing_evidence"]
    agent._call_claude.return_value = '{"raw_research":"Incomplete"}'
    with pytest.raises(ValueError, match="Invalid structured"):
        await agent.research_process("Example", [])


@pytest.mark.parametrize("published", ["2026-10-14", None])
def test_manifest_preserves_optional_declared_dates_and_permissions(catalog, published):
    root = catalog.system_config.references_dir
    root.mkdir()
    path = root / "policy.md"
    path.write_text("Change Management decision record")
    item = {"path": "policy.md", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "classification": "public", "external_ai_allowed": True, "published_on": published}
    catalog.system_config.reference_manifest.write_text(yaml.safe_dump({"sources": [item]}))
    assert ReferenceIndex(catalog.system_config).records[0]["published_on"] == published
    item["external_ai_allowed"] = False
    catalog.system_config.reference_manifest.write_text(yaml.safe_dump({"sources": [item]}))
    assert ReferenceIndex(catalog.system_config).records == []


@pytest.mark.parametrize("change,expected", [("mfa", "fail"), ("unknown_mfa", "unknown"), ("inactive", "fail"), ("role", "fail"), ("missing_approval", "missing"), ("denied", "denied"), ("no_quote", "missing_evidence")])
def test_iam_checks_actual_supplied_flags_and_missing_approval_evidence(change, expected):
    data = snapshot()
    if change == "mfa": data["identities"][0]["mfa_enabled"] = False
    if change == "unknown_mfa": data["identities"][0]["mfa_enabled"] = None
    if change == "inactive": data["identities"][0]["active"] = False
    if change == "role": data["identities"][0]["roles"] = ["unknown"]
    if change == "missing_approval": data["approvals"] = []
    if change == "denied": data["approvals"][0]["approved"] = False
    if change == "no_quote": data["approvals"][0]["evidence"] = []
    result = check_iam(data, {"SRC-fixture": source()}, POLICY)
    assert result["status"] == "gaps_found" and any(c["result"] == expected for c in result["checks"])
    assert result["production_operation"] == "not_verified" and result["grant_access"] is False


@pytest.mark.parametrize("change", ["duplicate", "future_approval", "unknown_approval", "secret", "blank_role"])
@pytest.mark.asyncio
async def test_invalid_iam_input_fails_before_any_model_request(change):
    data = snapshot()
    if change == "duplicate": data["identities"] *= 2
    if change == "future_approval": data["approvals"][0]["approved_at"] = "2030-01-01T00:00:00Z"
    if change == "unknown_approval": data["approvals"][0]["subject_id"] = "not-in-snapshot"
    if change == "secret": data["password"] = "synthetic-not-a-credential"
    if change == "blank_role": data["roles"] = [" "]
    agent = AccessAgent(api_key="")
    agent.source_records, agent.knowledge_records = [source()], []
    agent._call_claude = AsyncMock(return_value="Advice")
    with pytest.raises(ValueError):
        await agent.analyze_access_requirements("Example", [], {"iam_environment": data})
    agent._call_claude.assert_not_awaited()


def test_iam_success_still_only_reports_snapshot_consistency_and_missing_environment():
    result = check_iam(snapshot(), {"SRC-fixture": source()}, POLICY)
    assert result["status"] == "snapshot_consistent" and result["production_operation"] == "not_verified"
    assert check_iam(None, {}, POLICY)["status"] == "missing_environment"
    empty = {**snapshot(), "identities": [], "approvals": []}
    assert check_iam(empty, {}, POLICY)["status"] == "empty_snapshot"


def test_problem_timeline_uses_timezone_order_and_distinguishes_reported_evidence():
    result = assess_problem(case(), [Hypothesis.model_validate(h) for h in hypotheses()], {"SRC-fixture": source()}, POLICY)
    assert [o["id"] for o in result["timeline"]] == ["OBS-start", "OBS-recovery"]
    assert result["timeline"][0]["status"] == "located_unverified"
    assert result["timeline"][1]["status"] == "user_reported_unverified" and result["root_cause_status"] == "unconfirmed"


@pytest.mark.parametrize("change", ["unknown", "both", "duplicate", "naive_time", "empty_test"])
def test_problem_rejects_invented_or_contradictory_observations(change):
    data, hyps = case(), hypotheses()
    if change == "unknown": hyps[0]["supporting_observation_ids"] = ["OBS-invented"]
    if change == "both": hyps[0]["contradicting_observation_ids"] = ["OBS-start"]
    if change == "duplicate": data["observations"].append(data["observations"][0])
    if change == "naive_time": data["observations"][0]["observed_at"] = "2026-10-15T10:00:00"
    if change == "empty_test": hyps[0]["next_tests"] = [" "]
    with pytest.raises(ValueError):
        assess_problem(data, [Hypothesis.model_validate(h) for h in hyps], {"SRC-fixture": source()}, POLICY)


@pytest.mark.asyncio
async def test_actual_problem_requires_competing_hypotheses_and_rejects_confirmed_root_cause():
    agent = ProblemAgent(api_key="")
    agent.source_records, agent.knowledge_records = [source()], []
    response = {"problem_research": "Two hypotheses need testing.", "hypotheses": hypotheses()}
    agent._call_claude = AsyncMock(return_value=json.dumps(response))
    result = await agent.research_problem_management("Example", [], case())
    assert len(result["case_assessment"]["hypotheses"]) == 2
    agent._call_claude.return_value = json.dumps({**response, "root_cause_status": "confirmed"})
    with pytest.raises(ValueError, match="Invalid structured"):
        await agent.research_problem_management("Example", [], case())


@pytest.mark.parametrize("kind,rows,expected", [("ratio", [{"resolved": 1, "total": 2}, {"resolved": 8, "total": 8}], 90),
    ("duration_mean", [{"start": "2026-10-15T08:00:00Z", "end": "2026-10-15T11:30:00+03:00"}], 30),
    ("sum", [{"value": 3.5}, {"value": 2}], 5.5), ("count", [{}, {}, {}], 3)])
def test_metrics_calculate_supported_units_and_weighted_denominators(kind, rows, expected):
    result = calculate_metric(metric(kind), rows, POLICY)
    assert result["status"] == "calculated" and result["value"] == expected
    assert result["verification"] == "calculated_from_supplied_data_only"


@pytest.mark.parametrize("change", ["negative", "bool", "nan", "numerator", "missing", "exclusion", "backwards", "timestamp_type", "unit", "same_fields", "overflow"])
def test_metrics_reject_invalid_data_units_and_undefined_assumptions(change):
    spec, rows = metric(), [{"resolved": 1, "total": 2}]
    if change == "negative": rows[0]["resolved"] = -1
    if change == "bool": rows[0]["resolved"] = True
    if change == "nan": rows[0]["total"] = float("nan")
    if change == "numerator": rows[0]["resolved"] = 3
    if change == "missing": rows[0].pop("total")
    if change == "exclusion": spec = metric(exclude_field="excluded")
    if change == "backwards": spec, rows = metric("duration_mean"), [{"start": "2026-10-15T01:00:00Z", "end": "2026-10-15T00:00:00Z"}]
    if change == "timestamp_type": spec, rows = metric("duration_mean"), [{"start": 1, "end": 2}]
    if change == "overflow": rows = [{"resolved": 1e308, "total": 1e308}] * 2
    with pytest.raises(ValueError):
        if change == "unit": metric(unit="hours")
        elif change == "same_fields": metric(denominator_field="resolved")
        else: calculate_metric(spec, rows, POLICY)


def test_metric_missing_exclusions_and_zero_denominators_are_explicit():
    spec = metric(exclude_field="excluded", missing_policy="exclude")
    result = calculate_metric(spec, [{"excluded": True}, {"excluded": False, "total": None}, {"excluded": False, "resolved": 1, "total": 2}], POLICY)
    assert result["value"] == 50 and result["excluded_rows"] == result["missing_rows"] == 1
    assert calculate_metric(metric(), [{"resolved": 0, "total": 0}], POLICY)["status"] == "undefined_zero_denominator"
    assert calculate_metric(metric(), None, POLICY)["status"] == "no_data"
    assert calculate_metric(metric(), [], POLICY)["status"] == "no_eligible_data"


@pytest.mark.asyncio
async def test_actual_data_preserves_explicit_specs_and_rejects_changed_formulas():
    agent = DataAgent(api_key="")
    spec = metric()
    response = {"analytics_framework": "Use the supplied ratio specification.", "metrics": [spec.model_dump()]}
    agent._call_claude = AsyncMock(return_value=json.dumps(response))
    inputs = {"metric_specs": [spec.model_dump()], "metric_rows": [{"resolved": 1, "total": 2}]}
    result = await agent.design_analytics_framework("Example", ["Example metric"], inputs)
    assert result["calculation_checks"][0]["value"] == 50
    response["metrics"][0]["missing_policy"] = "exclude"
    agent._call_claude.return_value = json.dumps(response)
    with pytest.raises(ValueError, match="changed explicitly"):
        await agent.design_analytics_framework("Example", [], inputs)


def write_drawing(tmp_path, kind="normal"):
    drawing = ezdxf.new("R2010")
    drawing.header["$INSUNITS"] = 4 if kind == "units" else 6
    drawing.layers.new("A-WALL")
    model = drawing.modelspace()
    if kind == "bulge": model.add_lwpolyline([(0, 0, 1), (4, 0, 0)], format="xyb", dxfattribs={"layer": "A-WALL"})
    elif kind == "constant_width": model.add_lwpolyline([(0, 0), (4, 0)], dxfattribs={"layer": "A-WALL", "const_width": 0.2})
    elif kind == "self_cross": model.add_lwpolyline([(0, 0), (4, 4), (0, 4), (4, 0)], close=True, dxfattribs={"layer": "A-WALL"})
    elif kind == "unsupported": model.add_arc((2, 2), 1, 0, 90, dxfattribs={"layer": "A-WALL"})
    else: model.add_line((-2, 0, 1 if kind == "nonplanar" else 0), (12 if kind == "clip" else 4, 0, 0), dxfattribs={"layer": "A-WALL"})
    if kind == "duplicate": model.add_line((4, 0), (-2, 0), dxfattribs={"layer": "A-WALL"})
    if kind == "degenerate": model.add_line((1, 1), (1, 1), dxfattribs={"layer": "A-WALL"})
    path = tmp_path / "plan.dxf"
    drawing.saveas(path)
    return path


@pytest.mark.parametrize("kind", ["units", "bulge", "constant_width", "self_cross", "unsupported", "nonplanar", "degenerate"])
def test_cad_rejects_invalid_geometry_before_furnishing_or_any_artifact_write(tmp_path, kind):
    path = write_drawing(tmp_path, kind)
    output = tmp_path / "output"
    with pytest.raises(ValueError):
        BuildingDesignAgent(api_key="").create_concept_model(path, output, (0, -1, 8, 8))
    assert not output.exists()


@pytest.mark.parametrize("kind", ["clip", "duplicate"])
def test_cad_selection_preserves_provenance_and_clips_actual_endpoints(tmp_path, kind):
    path = write_drawing(tmp_path, kind)
    result = BuildingDesignAgent(api_key="").create_concept_model(path, tmp_path / "output", (0, -1, 8, 8))
    checks = result["geometry_checks"]
    assert checks["selected_region_evidence"][0]["selected_start"] == [0.0, 0.0]
    assert checks["clipped_segments"] == 1
    assert result["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["mesh_checks"]["finite_vertices"] and checks["building_validation"] == "not_performed"
    if kind == "duplicate": assert checks["duplicate_segments_removed"] == 1


def test_cad_furniture_footprint_must_fit_the_selected_region(tmp_path):
    source_path = write_drawing(tmp_path)
    specification = tmp_path / "design.json"
    specification.write_text(json.dumps({"placements": [{"kind": "bed", "x": 0.1, "y": 2}]}))
    with pytest.raises(ValueError, match="footprint"):
        BuildingDesignAgent(api_key="").create_concept_model(source_path, tmp_path / "output", (0, -1, 8, 8), design_spec=specification)
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("limit", ["cad_max_bytes", "cad_max_entities", "cad_max_segments"])
def test_cad_enforces_configured_resource_bounds(tmp_path, monkeypatch, limit):
    path = write_drawing(tmp_path)
    drawing = ezdxf.readfile(path)
    drawing.modelspace().add_line((0, 2), (4, 2), dxfattribs={"layer": "A-WALL"})
    drawing.saveas(path)
    monkeypatch.setattr(config_manager.specialist_policy, limit, 1)
    with pytest.raises(ValueError, match="limit"):
        BuildingDesignAgent(api_key="").create_concept_model(path, tmp_path / "output", (0, -1, 8, 8))


def test_dwg_intake_rejects_unknown_version_codes(tmp_path):
    path = tmp_path / "invalid.dwg"
    path.write_bytes(b"AC10zz" + b"0" * 10)
    with pytest.raises(ValueError, match="recognized"):
        BuildingDesignAgent(api_key="").inspect_drawing(path)


@pytest.mark.asyncio
async def test_real_specialists_propagate_evidence_checks_and_metrics_through_pipeline_and_recovery(pipeline, monkeypatch):
    leader, catalog, workers = pipeline
    root = catalog.system_config.references_dir
    root.mkdir()
    path = root / "policy.md"
    path.write_text("Change Management: Retain the decision record.")
    catalog.system_config.reference_manifest.write_text(yaml.safe_dump({"sources": [{"path": "policy.md", "classification": "public",
        "external_ai_allowed": True, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "published_on": "2026-10-14"}]}))
    record = ReferenceIndex(catalog.system_config).records[0]
    from src.agents import research_agent, access_agent, problem_agent, data_agent
    for module in (research_agent, access_agent, problem_agent, data_agent): monkeypatch.setattr(module, "config_manager", catalog)
    research, access, problem, data = [cls(api_key="") for cls in (ResearchAgent, AccessAgent, ProblemAgent, DataAgent)]
    spec = metric()
    responses = [(research, {"raw_research": "Located proposal", "claims": [{"id": "CLM-record", "text": "Retain the record", "kind": "recommendation", "evidence": [evidence(record)]}]}),
        (access, "Guidance from the supplied IAM snapshot."),
        (problem, {"problem_research": "Competing hypotheses remain unconfirmed", "hypotheses": hypotheses()}),
        (data, {"analytics_framework": "Use the explicitly supplied ratio", "metrics": [spec.model_dump()]})]
    for agent, response in responses:
        async def completion(*args, agent=agent, response=response, **kwargs):
            for entry in agent.source_records: current_runtime.get().sources[entry["id"]] = {k: v for k, v in entry.items() if k != "text"}
            return json.dumps(response) if isinstance(response, dict) else response
        agent._call_claude = AsyncMock(side_effect=completion)
    # Keep the existing enrichment/compliance mock boundaries while exercising real research methods.
    workers["AccessAgent"].analyze_access_requirements = access.analyze_access_requirements
    workers["ProblemAgent"].research_problem_management = problem.research_problem_management
    workers["DataAgent"].design_analytics_framework = data.design_analytics_framework
    workers["ResearchAgent"].research_process = research.research_process
    for worker in [workers["AccessAgent"], workers["ProblemAgent"], workers["DataAgent"], workers["ResearchAgent"]]: worker.knowledge_records = []
    # The leader assigns sources to registered worker objects; mirror them to the real bound instances.
    async def synced_research(name, workflow):
        for real, key in [(research, "ResearchAgent"), (access, "AccessAgent"), (problem, "ProblemAgent"), (data, "DataAgent")]:
            real.source_records = workers[key].source_records
        return await original_research(name, workflow)
    original_research = leader._coordinate_research
    leader._coordinate_research = synced_research
    inputs = {"as_of": "2026-10-15", "iam_environment": snapshot(record), "problem_case": case(record),
              "metric_specs": [spec.model_dump()], "metric_rows": [{"resolved": 1, "total": 2}]}
    workers["DataAgent"].create_dashboard_design.side_effect = RuntimeError("Synthetic interruption")
    with pytest.raises(RuntimeError):
        await leader.generate_documentation("Change Management", ["markdown"], specialist_inputs=inputs)
    parent = leader.context["run_dir"]
    workers["DataAgent"].create_dashboard_design.side_effect = None
    await leader.resume_execution(parent, allow_external_ai=True)
    assert leader.context["specialists"] == ["access", "data", "problem"]
    for agent, _ in responses: agent._call_claude.assert_awaited_once()
    payload = workers["ContentAgent"].generate_sop.await_args.args[1]
    assert payload["research"]["evidence_report"]["claims"][0]["evidence_status"] == "located_unverified"
    assert payload["access"]["environment_checks"]["status"] == "snapshot_consistent"
    assert payload["problem"]["case_assessment"]["root_cause_status"] == "unconfirmed"
    assert payload["data"]["calculation_checks"][0]["value"] == 50
    metric_payload = workers["DataAgent"].create_dashboard_design.await_args.args[1][0]
    assert metric_payload["denominator_field"] == "total" and metric_payload["calculation_check"]["value"] == 50
    assert leader.workflow_status == "awaiting_human_approval"


def test_cli_rejects_credential_or_malformed_specialist_input_before_generation(tmp_path):
    from src.main import app
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"api_key": "synthetic-secret-marker"}))
    result = CliRunner().invoke(app, ["generate", "Change Management", "-f", "markdown", "--specialist-input", str(path)])
    assert result.exit_code == 2 and "Invalid specialist input" in result.output
    assert "synthetic-secret-marker" not in result.output


@pytest.mark.parametrize("domain", ["research", "access", "problem", "data"])
def test_specialist_policy_bounds_fail_visibly_without_truncating(domain):
    policy = SpecialistPolicy()
    with pytest.raises(ValueError):
        if domain == "research":
            policy.max_claims = 1
            claims = [ResearchClaim(id="CLM-" + str(i), text="Proposal", kind="recommendation", evidence=[]) for i in range(2)]
            assess_claims(claims, {}, "2026-10-16", policy)
        elif domain == "access":
            policy.max_identities = 1
            data = snapshot()
            data["identities"].append({**data["identities"][0], "id": "account-2"})
            check_iam(data, {"SRC-fixture": source()}, policy)
        elif domain == "problem":
            policy.max_observations = 1
            assess_problem(case(), [], {"SRC-fixture": source()}, policy)
        else:
            policy.max_metric_rows = 1
            calculate_metric(metric(), [{"resolved": 1, "total": 2}] * 2, policy)


def test_untyped_metric_rows_and_invalid_source_dates_are_rejected():
    from src.utils.specialists import SpecialistInputs
    with pytest.raises(ValueError, match="explicit metric"):
        SpecialistInputs(metric_rows=[{"value": 1}])
    with pytest.raises(ValueError):
        SourcePermission(path="policy.md", classification="public", sha256="a" * 64, published_on="2026-W01-1")


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["missing_check", "invented_value", "bool_value"])
async def test_pipeline_recomputes_typed_calculations_before_caching_or_content(pipeline, change):
    leader, _, workers = pipeline
    spec = metric()
    data = {"analytics_framework": "Unverified prose", "metric_specs": [spec.model_dump()]}
    rows = [{"resolved": 1, "total": 100 if change == "bool_value" else 2}]
    if change == "invented_value":
        data["calculation_checks"] = [{"metric_id": spec.id, "status": "calculated", "value": 999}]
    if change == "bool_value":
        data["calculation_checks"] = [calculate_metric(spec, rows, POLICY)]
        data["calculation_checks"][0]["value"] = True
    workers["DataAgent"].design_analytics_framework.return_value = data
    with pytest.raises(ValueError, match="Analytics"):
        await leader.generate_documentation("Change Management", ["markdown"], specialist_inputs={
            "metric_specs": [spec.model_dump()], "metric_rows": rows})
    workers["ContentAgent"].generate_sop.assert_not_awaited()
    journal = json.loads((Path(leader.context["run_dir"]) / "execution.json").read_text())
    assert "data" not in journal["record"]["completed_calls"]


@pytest.mark.asyncio
async def test_invalid_metric_data_is_rejected_before_parallel_model_work(pipeline):
    leader, _, workers = pipeline
    with pytest.raises(ValueError, match="nonnegative"):
        await leader.generate_documentation("Change Management", ["markdown"], specialist_inputs={
            "metric_specs": [metric().model_dump()], "metric_rows": [{"resolved": -1, "total": 2}]})
    workers["ResearchAgent"].research_process.assert_not_awaited()
    workers["DataAgent"].design_analytics_framework.assert_not_awaited()


@pytest.mark.asyncio
async def test_dependency_lock_identity_change_rejects_recovery_before_worker_calls(pipeline, monkeypatch):
    from src.utils import execution
    leader, _, workers = pipeline
    workers["ContentAgent"].generate_sop.side_effect = RuntimeError("Synthetic interruption")
    with pytest.raises(RuntimeError):
        await leader.generate_documentation("Change Management", ["markdown"])
    parent = leader.context["run_dir"]
    original = execution.file_digest
    monkeypatch.setattr(execution, "file_digest", lambda path: "b" * 64 if Path(path).name == "requirements.lock" else original(path))
    workers["ResearchAgent"].research_process.reset_mock()
    with pytest.raises(ValueError, match="configuration"):
        await leader.resume_execution(parent, allow_external_ai=True)
    workers["ResearchAgent"].research_process.assert_not_awaited()
