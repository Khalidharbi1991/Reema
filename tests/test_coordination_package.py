"""Synthetic coordination/recovery acceptance scenarios; no live model quality claims."""

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from typer.testing import CliRunner

from src.assistant import AssistantSession
from src.agents import LeaderAgent
from src.utils.capabilities import invoke_pipeline
from src.utils.config import config_manager
from src.utils.coordination import RequestPlan, Selection
from src.utils.execution import load_execution
from src.utils.provider import current_runtime, Completion
from src.utils.tasks import TaskStore
from src.utils.approvals import read_record
from tests.test_phase01 import catalog, pipeline


class ChatAgent:
    def __init__(self, name, directory):
        self.name, self.directory = name, directory
        self._call_claude = AsyncMock(return_value=json.dumps({"advice": "Synthetic advice"}))

    def task_store(self, area):
        return TaskStore(self.directory, area)

    async def close(self):
        pass


@pytest.fixture
def chat(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "task_data_dir", tmp_path)
    monkeypatch.setattr(config_manager.system_config, "allow_external_ai", False)
    session = AssistantSession("work", project="Alpha", api_key="synthetic")
    for key, name in [("secretary_agent", "Ahmad"), ("leader_agent", "Abdullah"),
                      ("access_agent", "Agent 6"), ("data_agent", "Agent 8"),
                      ("content_agent", "Agent 3"), ("research_agent", "Agent 1"),
                      ("standards_agent", "Agent 2"), ("problem_agent", "Agent 7")]:
        session.agents[key] = ChatAgent(name, tmp_path)
    return session


def prompt(session, key="secretary_agent"):
    return session.agents[key]._call_claude.await_args.args[0][-1]["content"]


@pytest.mark.parametrize("message,selected", [
    ("Draft an SOP with MFA and a KPI dashboard", ["access_agent", "data_agent", "content_agent"]),
    ("No security advice; prepare an agenda", ["content_agent"]),
    ("Without security advice, draft an SOP", ["content_agent"]),
    ("Write an email without MFA jargon", ["content_agent"]),
    ("Not only security but a KPI dashboard", ["access_agent", "data_agent"]),
    ("Do not skip MFA", ["access_agent"]),
    ("Maintain standard applications", []),
    ("Explain accessibility", []),
    ("Hello", []),
])
def test_request_planner_acceptance(chat, message, selected):
    plan = chat.plan(message)
    assert plan.status == "ready"
    assert [s.agent for s in plan.selections] == selected


@pytest.mark.asyncio
async def test_mixed_request_uses_abdullah_coordinator_and_every_needed_specialist(chat):
    result = await chat.reply("Draft an SOP with MFA and a KPI dashboard", allow_external_ai=True)
    assert isinstance(chat._coordination_leader, LeaderAgent)
    assert result["consulted_agents"] == ["Agent 6", "Agent 8", "Agent 3"]
    assert result["coordination"]["coordinator"] == "Abdullah"
    assert result["coordination"]["consensus"] == "not_established"
    for key in ("access_agent", "data_agent", "content_agent", "secretary_agent"):
        chat.agents[key]._call_claude.assert_awaited_once()
    chat.agents["leader_agent"]._call_claude.assert_not_awaited()  # No redundant leader completion.
    assert "Abdullah coordination briefing" in prompt(chat)


@pytest.mark.asyncio
async def test_follow_up_keeps_selected_specialists_and_local_outcomes(chat):
    await chat.reply("Add a task to check rollout")
    assert any(item.source == "local_command" for item in chat.task_context.outcomes.values())
    await chat.reply("Explain MFA and KPI dashboards", allow_external_ai=True)
    answer = await chat.reply("Continue", allow_external_ai=True)
    assert answer["consulted_agents"] == ["Agent 6", "Agent 8"]
    assert chat.agents["access_agent"]._call_claude.await_count == 2
    assert chat.task_context.outcomes


@pytest.mark.asyncio
async def test_local_outcomes_use_the_created_task_identity_not_hex_in_its_title(chat):
    title_hash = "a" * 32
    await chat.reply("Add a task to inspect hash " + title_hash)
    task = chat.agents["secretary_agent"].task_store("work").list(project="Alpha")[0]
    assert "task-" + task["id"] in chat.task_context.outcomes
    assert "task-" + title_hash not in chat.task_context.outcomes


@pytest.mark.asyncio
async def test_specialist_domain_prompt_keeps_application_scope_guards(chat):
    from src.agents import AccessAgent
    agent = AccessAgent(api_key="")
    agent._call_claude = AsyncMock(return_value=json.dumps({"advice": "Synthetic"}))
    chat.agents["access_agent"] = agent
    await chat.reply("Explain MFA", allow_external_ai=True)
    system = agent._call_claude.await_args.kwargs["system"]
    assert "IAM" in system and "personal contexts separate" in system


@pytest.mark.asyncio
async def test_specialist_consultations_respect_configured_concurrency(chat, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "max_concurrent_agents", 1)
    active = peak = 0

    async def completion(*args, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(.001)
        active -= 1
        return json.dumps({"advice": "Synthetic"})

    for key in ("access_agent", "data_agent", "content_agent"):
        chat.agents[key]._call_claude.side_effect = completion
    await chat.reply("Draft an SOP with MFA and KPI dashboards", allow_external_ai=True)
    assert peak == 1


@pytest.mark.asyncio
async def test_failures_and_different_reported_positions_remain_visible(chat):
    chat.agents["access_agent"]._call_claude.return_value = json.dumps({"advice": "Proceed", "positions": [{"topic": "Release", "stance": "Proceed"}]})
    chat.agents["data_agent"]._call_claude.return_value = json.dumps({"advice": "Hold", "positions": [{"topic": "Release", "stance": "Hold"}]})
    chat.agents["content_agent"]._call_claude.side_effect = RuntimeError("Synthetic failure")
    answer = await chat.reply("Draft an SOP with MFA and a KPI dashboard", allow_external_ai=True)
    assert answer["coordination"]["status"] == "partial"
    assert answer["coordination"]["disagreements"]
    assert "RuntimeError" in prompt(chat) and "Reported positions differ" in prompt(chat)
    assert any(fact.source == "coordination_record" for fact in chat.task_context.pending.values())
    assert answer["coordination"]["consensus"] == "not_established"


@pytest.mark.asyncio
async def test_all_specialist_failures_do_not_claim_success(chat):
    chat.agents["access_agent"]._call_claude.side_effect = RuntimeError("Failure")
    answer = await chat.reply("Explain MFA", allow_external_ai=True)
    assert answer["coordination"]["status"] == "failed" and answer["consulted_agents"] == []
    assert "advice is unavailable" in prompt(chat)


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed", ['{"advice": " "}', '{"advice": "Text", "unexpected": true}'])
async def test_malformed_structured_advice_is_reported_as_failure(chat, malformed):
    chat.agents["access_agent"]._call_claude.return_value = malformed
    answer = await chat.reply("Explain MFA", allow_external_ai=True)
    assert answer["coordination"]["status"] == "failed"
    assert answer["consulted_agents"] == []


@pytest.mark.asyncio
async def test_agent_initialization_failure_does_not_abandon_sibling_consultations(chat, monkeypatch):
    original = chat._agent

    def resolve(key):
        if key == "access_agent":
            raise ValueError("Synthetic initialization failure")
        return original(key)

    monkeypatch.setattr(chat, "_agent", resolve)
    answer = await chat.reply("Explain MFA and KPI dashboards", allow_external_ai=True)
    assert answer["coordination"]["status"] == "partial"
    chat.agents["data_agent"]._call_claude.assert_awaited_once()
    assert chat._coordination_leader.consultation_status["completed"] == ["data_agent"]


@pytest.mark.asyncio
async def test_local_actions_unsupported_actions_and_clarification_are_offline(chat, monkeypatch):
    added = await chat.reply("Add a task to review the pilot")
    assert "Added work task" in added["reply"]
    assert chat.agents["secretary_agent"].task_store("work").list(project="Alpha")
    unsupported = await chat.reply("Send the email")
    assert unsupported["plan"]["intent"] == "unsupported_action"
    ambiguous = await chat.reply("Should we proceed without security approval?")
    assert ambiguous["plan"]["status"] == "needs_clarification"
    monkeypatch.setattr(config_manager.assistant_routing, "max_specialists", 1)
    broad = await chat.reply("Draft an SOP with MFA and a KPI dashboard")
    assert broad["plan"]["status"] == "needs_clarification" and len(broad["plan"]["selections"]) == 3
    for agent in chat.agents.values():
        agent._call_claude.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_and_verbatim_session_decisions_survive_recent_history_window(chat):
    await chat.reply("/objective Migrate the support devices")
    await chat.reply("/decision platform Use Intune")
    await chat.reply("Constraint: Do not buy another platform")
    await chat.reply("/outcome pilot Pilot testing completed")
    await chat.reply("We decided to retain the existing support group", allow_external_ai=True)
    for number in range(5):
        await chat.reply(f"Explain MFA step {number}", allow_external_ai=True)
    text = prompt(chat)
    for expected in ("Use Intune", "Do not buy another platform", "Pilot testing completed", "retain the existing support group"):
        assert expected in text
    assert len(chat.history) == 6
    assert chat.agents["secretary_agent"].task_store("work").memories() == []
    assert chat.task_context.objective == "Migrate the support devices"


@pytest.mark.asyncio
async def test_memory_edits_and_project_changes_clear_all_session_context(chat):
    await chat.reply("/decision secret Alpha decision secret")
    await chat.reply("Explain MFA", allow_external_ai=True)
    chat.agents["secretary_agent"].task_store("work").remember("tone", "Brief")
    await chat.reply("Explain MFA again", allow_external_ai=True)
    assert "Alpha decision secret" not in prompt(chat)
    await chat.reply("/constraint scope Alpha only")
    await chat.reply("/project Beta")
    assert not chat.task_context.constraints and not chat.task_context.requests and chat.history == []
    assert chat.task_context.project == "Beta"


@pytest.mark.asyncio
async def test_multiple_specialists_receive_only_selected_area_and_project(chat, tmp_path):
    work, personal = TaskStore(tmp_path, "work"), TaskStore(tmp_path, "personal")
    work.remember("goal", "Alpha allowed goal", kind="project", project="Alpha")
    work.remember("goal", "Beta secret goal", kind="project", project="Beta")
    personal.remember("goal", "Personal secret goal", kind="profile")
    work.add("Alpha task", project="Alpha", details="Task detail secret")
    work.add("Beta task secret", project="Beta")
    await chat.reply("Plan the MFA and KPI dashboard", allow_external_ai=True)
    for key in ("access_agent", "data_agent", "secretary_agent"):
        text = prompt(chat, key)
        assert "Alpha allowed goal" in text and "Alpha task" in text
        assert all(secret not in text for secret in ("Beta secret goal", "Personal secret goal", "Beta task secret", "Task detail secret"))


@pytest.mark.asyncio
async def test_session_budget_rejects_growth_without_discarding_decisions(chat, monkeypatch):
    await chat.reply("/decision platform Keep existing tools")
    monkeypatch.setattr(config_manager.assistant_routing, "context_max_chars", 1000)
    with pytest.raises(ValueError, match="budget"):
        await chat.reply("/constraint large " + "x" * 1200)
    assert chat.task_context.decisions["platform"].text == "Keep existing tools"
    assert "large" not in chat.task_context.constraints
    for agent in chat.agents.values():
        agent._call_claude.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorization_and_session_reentrancy_are_enforced(chat):
    with pytest.raises(PermissionError):
        await chat.reply("Explain MFA and KPI dashboards")
    started, release = asyncio.Event(), asyncio.Event()

    async def waiting(*args, **kwargs):
        started.set()
        await release.wait()
        return json.dumps({"advice": "Synthetic"})

    chat.agents["access_agent"]._call_claude.side_effect = waiting
    task = asyncio.create_task(chat.reply("Explain MFA", allow_external_ai=True))
    try:
        await asyncio.wait_for(started.wait(), 2)
        with pytest.raises(RuntimeError, match="already running"):
            await chat.reply("/project Beta")
    finally:
        release.set()
        await task
    assert chat.project == "Alpha"


def test_invalid_plans_cannot_name_arbitrary_capabilities():
    with pytest.raises(ValueError):
        Selection(agent="send_email", reasons=["send"])
    with pytest.raises(ValueError):
        RequestPlan(objective="Goal", intent="local_action", selections=[Selection(agent="access_agent", reasons=["MFA"])])


@pytest.mark.asyncio
async def test_capability_registry_cannot_dispatch_unknown_tools():
    worker = SimpleNamespace(send_email=AsyncMock())
    with pytest.raises(ValueError, match="Unsupported"):
        await invoke_pipeline({"Mail": worker}, "send_email", {"message": "Hello"})
    worker.send_email.assert_not_awaited()


async def interrupted(pipeline, phase="review", specialists=None):
    leader, _, workers = pipeline
    worker, method = {"standards": ("StandardsAgent", "analyze_compliance"),
                      "content": ("ContentAgent", "generate_sop"),
                      "access_content": ("AccessAgent", "generate_access_content"),
                      "review": ("ReviewAgent", "review_content"),
                      "compliance": ("AccessAgent", "validate_access_compliance")}[phase]
    method_mock = getattr(workers[worker], method)
    method_mock.side_effect = RuntimeError("Synthetic interruption")
    with pytest.raises(RuntimeError):
        await leader.generate_documentation("Change Management", ["markdown"], specialists=specialists,
                                            objective="Support team SOP", constraints=["Use existing tools"])
    directory = Path(leader.context["run_dir"])
    method_mock.side_effect = None
    return directory


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["standards", "content", "access_content", "review", "compliance"])
async def test_completed_research_and_generation_are_recovered_without_duplicate_calls(pipeline, phase):
    leader, config, workers = pipeline
    selected = ["access", "data", "problem"]
    parent = await interrupted(pipeline, phase, selected)
    methods = [("ResearchAgent", "research_process"), ("StandardsAgent", "analyze_compliance"),
               ("ContentAgent", "generate_sop"), ("AccessAgent", "generate_access_content"),
               ("ProblemAgent", "generate_problem_content"), ("DataAgent", "create_dashboard_design"),
               ("ReviewAgent", "review_content")]
    before = {name: getattr(workers[cls], name).await_count for cls, name in methods}
    record, _ = load_execution(parent, config)
    config.system_config.allow_external_ai = False
    with pytest.raises(PermissionError, match="fresh"):
        await leader.resume_execution(parent)
    outputs = await leader.resume_execution(parent, allow_external_ai=True)
    child = Path(leader.context["run_dir"])
    assert child != parent and Path(outputs["markdown"]).is_file()
    assert read_record(Path(leader.context["delivery"]["approval_record"])).status == "awaiting_human_approval"
    assert not (parent / "approval.json").exists()
    for capability, (cls, method) in {"research": ("ResearchAgent", "research_process"),
        "standards": ("StandardsAgent", "analyze_compliance"), "content": ("ContentAgent", "generate_sop"),
        "access_content": ("AccessAgent", "generate_access_content"),
        "problem_content": ("ProblemAgent", "generate_problem_content"),
        "dashboard": ("DataAgent", "create_dashboard_design")}.items():
        if capability in record.completed_calls:
            assert getattr(workers[cls], method).await_count == before[method]
    if phase == "compliance":
        assert workers["ReviewAgent"].review_content.await_count == before["review_content"]
        assert leader.get_status()["reused_tasks"] >= 4
    state = json.loads((child / "run.json").read_text())
    assert state["resumed_from"] == str(parent) and state["usage"]["lineage"]
    assert state["status"] == "awaiting_human_approval"
    assert "Use existing tools" in json.dumps(json.loads((child / "planned.json").read_text()))


@pytest.mark.asyncio
async def test_cancelled_partial_research_preserves_completed_sibling(pipeline):
    leader, _, workers = pipeline
    started = asyncio.Event()

    async def waiting(*args):
        started.set()
        await asyncio.Event().wait()

    workers["StandardsAgent"].analyze_compliance.side_effect = waiting
    task = asyncio.create_task(leader.generate_documentation("Change Management", ["markdown"]))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    parent = Path(leader.context["run_dir"])
    workers["StandardsAgent"].analyze_compliance.side_effect = None
    await leader.resume_execution(parent, allow_external_ai=True)
    assert workers["ResearchAgent"].research_process.await_count == 1
    assert workers["StandardsAgent"].analyze_compliance.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["run.json", "execution.json", "researched.json", "generated.json", "drafted.json", "key"])
async def test_tampered_recovery_records_are_rejected_before_reuse(pipeline, target):
    leader, config, workers = pipeline
    parent = await interrupted(pipeline)
    if target == "key":
        (config.system_config.output_dir / ".recovery-key").write_bytes(b"x" * 32)
    elif target == "run.json":
        (parent / target).write_text((parent / target).read_text() + "\n")
    else:
        (parent / target).write_text('{}')
    before = workers["ResearchAgent"].research_process.await_count
    with pytest.raises(ValueError):
        await leader.resume_execution(parent, allow_external_ai=True)
    assert workers["ResearchAgent"].research_process.await_count == before


@pytest.mark.asyncio
async def test_rewriting_plain_hashes_cannot_forge_a_recovery_record(pipeline):
    leader, _, workers = pipeline
    parent = await interrupted(pipeline)
    envelope = json.loads((parent / "execution.json").read_text())
    envelope["record"]["completed_calls"]["research"]["result"]["raw_research"] = "Forged research"
    (parent / "execution.json").write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="changed"):
        await leader.resume_execution(parent, allow_external_ai=True)
    assert workers["ResearchAgent"].research_process.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["agent_config", "process_config", "runtime", "knowledge", "permission", "source", "manifest_deleted"])
async def test_changed_inputs_configuration_or_source_permissions_block_recovery(pipeline, change):
    leader, config, workers = pipeline
    reference = config.system_config.references_dir / "source.md"
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_text("Change Management approval requirement")
    manifest = {"version": 1, "sources": [{"path": "source.md", "classification": "internal", "external_ai_allowed": True,
                                            "sha256": hashlib.sha256(reference.read_bytes()).hexdigest()}]}
    config.system_config.reference_manifest.write_text(json.dumps(manifest))
    parent = await interrupted(pipeline)
    if change == "agent_config":
        config.agents_config["research_agent"]["temperature"] = .1
    elif change == "process_config":
        config.process_definitions["change_management"]["description"] += " Changed"
    elif change == "runtime":
        config.system_config.max_prompt_chars += 1
    elif change == "knowledge":
        config.system_config.knowledge_dir.mkdir(parents=True)
        (config.system_config.knowledge_dir / "new.md").write_text("New source")
    elif change == "permission":
        manifest["sources"][0]["external_ai_allowed"] = False
        config.system_config.reference_manifest.write_text(json.dumps(manifest))
    elif change == "source":
        reference.write_text("Changed after authorization")
    else:
        config.system_config.reference_manifest.unlink()
    with pytest.raises(ValueError):
        await leader.resume_execution(parent, allow_external_ai=True)
    assert workers["ResearchAgent"].research_process.await_count == 1


@pytest.mark.asyncio
async def test_recovery_preserves_usage_lineage_without_resetting_the_budget(pipeline):
    leader, config, workers = pipeline

    class Provider:
        complete = AsyncMock(return_value=Completion("Synthetic research", 10, 5))

    provider = Provider()

    async def paid_research(*args):
        value = await current_runtime.get().call(provider, agent="Agent 1", model="fake", max_tokens=10,
            system="Synthetic", messages=[{"role": "user", "content": "Synthetic research"}])
        return {"raw_research": value}

    workers["ResearchAgent"].research_process.side_effect = paid_research
    parent = await interrupted(pipeline, "standards")
    workers["ReviewAgent"].review_content.side_effect = RuntimeError("Review interruption")
    with pytest.raises(RuntimeError):
        await leader.resume_execution(parent, allow_external_ai=True)
    child = Path(leader.context["run_dir"])
    workers["ReviewAgent"].review_content.side_effect = None
    await leader.resume_execution(child, allow_external_ai=True)
    usage = json.loads((Path(leader.context["run_dir"]) / "run.json").read_text())["usage"]
    assert provider.complete.await_count == 1
    assert usage["accounted_tokens"] == usage["inherited_accounted_tokens"] == 15
    assert usage["new_accounted_tokens"] == 0 and usage["calls"] == [] and len(usage["lineage"]) == 2


@pytest.mark.asyncio
async def test_model_recovery_cannot_change_formats_or_skip_fresh_consent(pipeline):
    leader, config, _ = pipeline
    parent = await interrupted(pipeline)
    assert config.system_config.allow_external_ai
    with pytest.raises(PermissionError, match="fresh"):
        await leader.resume_execution(parent)
    with pytest.raises(ValueError, match="formats"):
        await leader.resume_execution(parent, ["html"], allow_external_ai=True)


@pytest.mark.asyncio
async def test_inherited_usage_can_block_new_requests_without_repeating_completed_work(pipeline):
    leader, config, workers = pipeline
    config.system_config.max_run_tokens = 5000
    old_provider = SimpleNamespace(complete=AsyncMock(return_value=Completion("Research", 4895, 5)))
    new_provider = SimpleNamespace(complete=AsyncMock(return_value=Completion("Standards", 10, 5)))

    async def research(*args):
        text = await current_runtime.get().call(old_provider, agent="Agent 1", model="fake", max_tokens=10,
            system="Synthetic", messages=[{"role": "user", "content": "Synthetic"}])
        return {"raw_research": text}

    async def standards(*args):
        text = await current_runtime.get().call(new_provider, agent="Agent 2", model="fake", max_tokens=10,
            system="Synthetic", messages=[{"role": "user", "content": "Synthetic"}])
        return {"compliance_analysis": text}

    workers["ResearchAgent"].research_process.side_effect = research
    parent = await interrupted(pipeline, "standards")
    workers["StandardsAgent"].analyze_compliance.side_effect = standards
    with pytest.raises(ValueError, match="budget"):
        await leader.resume_execution(parent, allow_external_ai=True)
    assert old_provider.complete.await_count == 1
    new_provider.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_changed_implementation_identity_rejects_recovery(pipeline, monkeypatch):
    from src.utils import execution
    leader, _, workers = pipeline
    parent = await interrupted(pipeline)
    original = execution.tree_digest

    def changed(directory, patterns):
        return "0" * 64 if Path(directory).name == "src" else original(directory, patterns)

    monkeypatch.setattr(execution, "tree_digest", changed)
    with pytest.raises(ValueError, match="changed"):
        await leader.resume_execution(parent, allow_external_ai=True)
    assert workers["ResearchAgent"].research_process.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("available", [True, False])
async def test_recovered_source_identity_must_be_currently_available(pipeline, available):
    from src.knowledge.retrieval import ReferenceIndex
    leader, config, workers = pipeline
    source_file = config.system_config.references_dir / "allowed.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("Change Management evidence")
    config.system_config.reference_manifest.write_text(json.dumps({"version": 1, "sources": [{
        "path": "allowed.md", "classification": "internal", "external_ai_allowed": True,
        "sha256": hashlib.sha256(source_file.read_bytes()).hexdigest()}]}))
    source = ReferenceIndex(config.system_config).records[0]
    source_id = source["id"] if available else "SRC-invented"

    async def research(*args):
        current_runtime.get().sources[source_id] = {key: value for key, value in source.items() if key != "text"}
        return {"raw_research": "Requirement [" + source_id + "]"}

    workers["ResearchAgent"].research_process.side_effect = research
    parent = await interrupted(pipeline)
    if available:
        await leader.resume_execution(parent, allow_external_ai=True)
        ready = json.loads((Path(leader.context["run_dir"]) / "ready.json").read_text())
        assert ready["sources"][source_id]["sha256"] == source["sha256"]
    else:
        with pytest.raises(ValueError, match="provenance"):
            await leader.resume_execution(parent, allow_external_ai=True)
    assert workers["ResearchAgent"].research_process.await_count == 1


@pytest.mark.asyncio
async def test_cli_model_recovery_is_explicit_and_creates_new_pending_record(pipeline, monkeypatch):
    from src import main
    leader, config, _ = pipeline
    parent = await interrupted(pipeline)
    monkeypatch.setattr(main, "config_manager", config)
    monkeypatch.setattr(main, "initialize_system", lambda selected: {"leader": leader})
    runner = CliRunner()
    denied = await asyncio.to_thread(runner.invoke, main.app, ["resume", str(parent), "--model-phases"])
    assert denied.exit_code == 1 and "fresh" in denied.output
    # CliRunner cannot start asyncio.run in the test's running event loop.
    result = await asyncio.to_thread(runner.invoke, main.app, ["resume", str(parent), "--model-phases", "--allow-external-ai"])
    assert result.exit_code == 0, result.output
    assert "Awaiting human approval" in result.output
