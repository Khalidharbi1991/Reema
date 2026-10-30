"""Agent 10's end-user computing role and SOP enrichment."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agents import EUCAgent
from src.utils.approvals import read_record
from src.utils.capabilities import invoke_pipeline
from src.utils.config import config_manager
from src.utils.execution import load_execution
from tests.test_phase01 import catalog, pipeline


def test_agent_10_is_a_configured_role():
    settings = config_manager.get_agent_config("euc_agent")
    assert EUCAgent.AGENT_NAME == settings["name"] == "Agent 10"
    assert EUCAgent.AGENT_ROLE == settings["role"]
    # No model override: Agent 10 inherits the configured worker default.
    assert settings.get("model") is None


def test_agent_10_prompt_keeps_the_reversible_advisory_protocol():
    system = EUCAgent(api_key="")._build_system_prompt()
    for guard in ("Frame before advising", "Reversibility first", "kill switch", "irreversible",
                  "-WhatIf", "Never fabricate cmdlets", "cannot run scripts", "Asia/Riyadh",
                  "Sunday to Thursday", "Next step:", "Open risks / assumptions:"):
        assert guard in system
    assert "Treat the user as a peer" in system


@pytest.fixture
def euc_pipeline(pipeline):
    leader, catalog, workers = pipeline
    workers["EUCAgent"] = SimpleNamespace(
        analyze_endpoint_requirements=AsyncMock(return_value={
            "process_name": "Workstation Security Patches",
            "endpoint_analysis": "Pilot ring first. Rollback by uninstall. RING-TAIL-REQUIREMENT"}),
        generate_endpoint_content=AsyncMock(return_value="Ring plan table and kill switch. EUC-APPENDIX-END"),
    )
    leader.register_worker("EUCAgent", workers["EUCAgent"])
    return leader, catalog, workers


@pytest.mark.parametrize("process", ["Workstation Security Patches", "Devices Batch Management"])
def test_endpoint_processes_select_agent_10(catalog, process):
    assert catalog.resolve_process(process)[1]["specialists"] == ["euc"]


@pytest.mark.asyncio
async def test_agent_10_enriches_the_patch_sop_and_stops_at_human_approval(euc_pipeline):
    leader, catalog, workers = euc_pipeline
    outputs = await leader.generate_documentation("Workstation Security Patches", ["markdown"])
    euc = workers["EUCAgent"]
    euc.analyze_endpoint_requirements.assert_awaited_once_with(
        "Workstation Security Patches", catalog.get_standards_for_process("Workstation Security Patches"))
    euc.generate_endpoint_content.assert_awaited_once()
    process, requirements = euc.generate_endpoint_content.await_args.args
    assert process == "Workstation Security Patches"
    assert "RING-TAIL-REQUIREMENT" in requirements["endpoint_analysis"] and "handoff_metadata" in requirements
    document = Path(outputs["markdown"]).read_text(encoding="utf-8")
    assert "## Appendix: Endpoint Deployment & Rollback Plan" in document
    assert "Agent 10 (End-User Computing Specialist)" in document and "EUC-APPENDIX-END" in document
    assert "RING-TAIL-REQUIREMENT" in json.dumps(workers["ContentAgent"].generate_sop.await_args.args[1])
    assert read_record(Path(leader.context["delivery"]["approval_record"])).status == "awaiting_human_approval"
    assert "euc:euc" not in leader.context["handoffs"] and "research:euc" in leader.context["handoffs"]
    assert "enrichment:euc_content" in leader.context["handoffs"]


@pytest.mark.asyncio
async def test_agent_10_is_opt_in_for_other_processes(euc_pipeline):
    leader, _, workers = euc_pipeline
    workers["EUCAgent"].analyze_endpoint_requirements.return_value = {"process_name": "Change Management",
                                                                     "endpoint_analysis": "Rings"}
    await leader.generate_documentation("Change Management", ["markdown"])
    workers["EUCAgent"].analyze_endpoint_requirements.assert_not_awaited()
    await leader.generate_documentation("Change Management", ["markdown"], specialists=["euc"])
    workers["EUCAgent"].analyze_endpoint_requirements.assert_awaited_once()
    with pytest.raises(ValueError, match="access, problem, data, or euc"):
        await leader.generate_documentation("Change Management", ["markdown"], specialists=["mail"])


@pytest.mark.asyncio
async def test_selected_agent_10_must_be_registered(pipeline):
    leader, _, _ = pipeline
    with pytest.raises(ValueError, match="Required agents missing: EUCAgent"):
        await leader.generate_documentation("Workstation Security Patches", ["markdown"])


@pytest.mark.asyncio
async def test_failed_endpoint_enrichment_blocks_delivery(euc_pipeline):
    leader, _, workers = euc_pipeline
    workers["EUCAgent"].generate_endpoint_content.return_value = ""
    with pytest.raises(RuntimeError, match="Required enrichment 'euc_content' failed"):
        await leader.generate_documentation("Workstation Security Patches", ["markdown"])
    workers["ReviewAgent"].review_content.assert_not_awaited()


@pytest.mark.asyncio
async def test_endpoint_analysis_for_another_process_is_rejected(euc_pipeline):
    leader, _, workers = euc_pipeline
    with pytest.raises(ValueError, match="Invalid euc output"):
        await leader.generate_documentation("Devices Batch Management", ["markdown"])
    workers["ContentAgent"].generate_sop.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_10_research_and_appendix_are_recovered_without_repeat_calls(euc_pipeline):
    leader, config, workers = euc_pipeline
    workers["ReviewAgent"].review_content.side_effect = RuntimeError("Synthetic interruption")
    with pytest.raises(RuntimeError):
        await leader.generate_documentation("Workstation Security Patches", ["markdown"])
    parent = Path(leader.context["run_dir"])
    record, _ = load_execution(parent, config)
    assert {"euc", "euc_content"} <= set(record.completed_calls)
    workers["ReviewAgent"].review_content.side_effect = None
    outputs = await leader.resume_execution(parent, allow_external_ai=True)
    assert workers["EUCAgent"].analyze_endpoint_requirements.await_count == 1
    assert workers["EUCAgent"].generate_endpoint_content.await_count == 1
    assert "EUC-APPENDIX-END" in Path(outputs["markdown"]).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_endpoint_capabilities_reject_unexpected_inputs():
    worker = SimpleNamespace(generate_endpoint_content=AsyncMock(return_value="Content"))
    with pytest.raises(ValueError, match="endpoint_requirements"):
        await invoke_pipeline({"EUCAgent": worker}, "euc_content",
                              {"process_name": "Patches", "endpoint_requirements": {}, "tenant_secret": "x"})
    worker.generate_endpoint_content.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_10_pipeline_prompts_keep_placeholders_and_skip_chat_closing():
    agent = EUCAgent(api_key="")
    agent._call_claude = AsyncMock(return_value="## 1. SCOPE\nFleet [to confirm]")
    analysis = await agent.analyze_endpoint_requirements("Workstation Security Patches", ["ITIL v4"])
    assert analysis["process_name"] == "Workstation Security Patches"
    assert analysis["endpoint_analysis"].endswith("[to confirm]") and "1. SCOPE" in analysis["sections"]
    call = agent._call_claude.await_args
    assert "Do not invent device counts" in call.kwargs["messages"][0]["content"]
    assert "Reversibility first" in call.kwargs["system"] and "Next step:" not in call.kwargs["system"]
    prompt = agent._build_endpoint_content_prompt("Workstation Security Patches", {"endpoint_analysis": "TAIL-123"})
    assert "TAIL-123" in prompt and "ROLLBACK AND KILL SWITCH" in prompt and "[to confirm]" in prompt


def test_cli_setup_registers_agent_10_only_when_selected():
    from src.main import initialize_system
    assert isinstance(initialize_system(["euc"])["leader"].worker_agents["EUCAgent"], EUCAgent)
    assert "EUCAgent" not in initialize_system([])["leader"].worker_agents
