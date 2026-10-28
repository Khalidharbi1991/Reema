"""Agent 3 writes the SOP one configured section per model request."""

import asyncio
import json
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agents import ContentAgent, ResearchAgent
from src.utils.config import SystemConfig, config_manager
from src.utils.documents import SectionSpec, section_map
from src.utils.provider import Completion, RunRuntime, current_runtime

SECTIONS = config_manager.document_profile.sections
REGISTER = {"controls": [
    {"id": "CTRL-APPLIES", "applicability": "applicable", "target_sections": ["sec-procedures"]},
    {"id": "CTRL-OPEN", "applicability": "undetermined", "target_sections": ["sec-procedures"]}]}
RESEARCH = {"research": {"raw_research": "x" * 5000 + "RESEARCH-TAIL"},
            "standards": {"compliance_analysis": "Controls", "control_register": REGISTER}}


def requested(content):
    return re.search(r'Set section_id to "(sec-[a-z0-9-]+)"', content).group(1)


def body_for(section_id):
    return f"Body of {section_id} with distinct text BODY-{section_id}"


async def fake_reply(messages, system=""):
    section_id = requested(messages[-1]["content"])
    return json.dumps({"section_id": section_id, "body": body_for(section_id)})


@pytest.mark.asyncio
async def test_sections_are_written_in_order_then_assembled():
    agent = ContentAgent(api_key="")
    agent._call_claude = AsyncMock(side_effect=fake_reply)
    document = await agent.generate_sop("Example", RESEARCH)

    prompts = [call.args[0][0]["content"] for call in agent._call_claude.await_args_list]
    assert [requested(prompt) for prompt in prompts] == [s.id for s in SECTIONS]
    assert list(section_map(document, config_manager.document_profile, require_complete=True)) == [s.id for s in SECTIONS]
    assert all(body_for(s.id) in document for s in SECTIONS)
    assert all("RESEARCH-TAIL" in prompt for prompt in prompts)
    for number, (section, prompt) in enumerate(zip(SECTIONS, prompts), 1):
        assert f"WRITE SECTION {number} of {len(SECTIONS)}" in prompt
        assert f"Target length: {section.target_pages[0]}-{section.target_pages[1]} pages." in prompt
        # Definitions and RACI are shared once written, so later sections reuse them.
        assert ("BODY-sec-definitions" in prompt) == (number > 2)
        assert ("BODY-sec-roles" in prompt) == (number > 3)
        assert ("GRAPH SCHEMA" in prompt) == (section.id in {"sec-procedures", "sec-flow"})
        required = "applicable control IDs in square brackets in this section: CTRL-APPLIES."
        assert (required in prompt) == (section.id == "sec-procedures")


@pytest.mark.asyncio
async def test_reply_for_the_wrong_section_is_rejected():
    agent = ContentAgent(api_key="")
    agent._call_claude = AsyncMock(return_value=json.dumps({"section_id": "sec-roles", "body": "Misplaced"}))
    with pytest.raises(ValueError, match=r"Section 1 \(Introduction\) failed: Reply was for section 'sec-roles'"):
        await agent.generate_sop("Example", RESEARCH)
    agent._call_claude.assert_awaited_once()


@pytest.mark.asyncio
async def test_section_body_cannot_add_top_level_sections():
    agent = ContentAgent(api_key="")
    agent._call_claude = AsyncMock(side_effect=lambda messages, system="": json.dumps(
        {"section_id": requested(messages[-1]["content"]), "body": "## Extra section\nText"}))
    with pytest.raises(ValueError, match="cannot add top-level sections"):
        await agent.generate_sop("Example", RESEARCH)


@pytest.mark.asyncio
async def test_truncated_section_reply_fails_closed_through_the_real_runtime(tmp_path):
    settings = SystemConfig(_env_file=None, project_root=tmp_path, allow_external_ai=True, retry_backoff_seconds=0)
    agent = ContentAgent(api_key="")

    async def create(**request):
        section_id = requested(request["messages"][-1]["content"])
        truncated = section_id == "sec-procedures"
        text = '{"section_id": "sec-procedures", "body": "Step 1' if truncated else json.dumps(
            {"section_id": section_id, "body": body_for(section_id)})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5),
                               stop_reason="max_tokens" if truncated else "end_turn")

    agent.client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=create)))
    runtime = RunRuntime(settings)
    token = current_runtime.set(runtime)
    try:
        with pytest.raises(RuntimeError, match=r"Section 5 \(Detailed Procedures\) failed: .*stop reason max_tokens"
                                               r".*exceeded max_tokens=16000"):
            await agent.generate_sop("Example", RESEARCH)
    finally:
        current_runtime.reset(token)
    # Truncation is not retried, and no later section is requested.
    assert agent.client.messages.create.await_count == 5
    assert runtime.events[-1]["status"] == "failed"
    assert runtime.events[-1]["error_type"] == "IncompleteResponseError"
    assert runtime.events[-1]["stop_reason"] == "max_tokens"
    assert "temperature" not in agent.client.messages.create.await_args.kwargs


class Journal:
    """Minimal stand-in for the signed run journal's assessment store."""

    def __init__(self):
        self.data = {"identity": {"run": "synthetic"}, "completed_assessments": {}}

    def assessment(self, key, value, sources):
        self.data["completed_assessments"][key] = value


@pytest.mark.asyncio
async def test_interrupted_generation_reuses_finished_sections():
    journal = Journal()
    token = current_runtime.set(SimpleNamespace(execution_journal=journal, sources={}))
    try:
        interrupted = ContentAgent(api_key="")

        async def fail_on_procedures(messages, system=""):
            if requested(messages[-1]["content"]) == "sec-procedures":
                raise RuntimeError("Synthetic interruption")
            return await fake_reply(messages, system)

        interrupted._call_claude = AsyncMock(side_effect=fail_on_procedures)
        with pytest.raises(RuntimeError, match=r"Section 5 \(Detailed Procedures\) failed"):
            await interrupted.generate_sop("Example", RESEARCH)
        assert len(journal.data["completed_assessments"]) == 4

        resumed = ContentAgent(api_key="")
        resumed._call_claude = AsyncMock(side_effect=fake_reply)
        document = await resumed.generate_sop("Example", RESEARCH)
    finally:
        current_runtime.reset(token)
    asked = [requested(call.args[0][0]["content"]) for call in resumed._call_claude.await_args_list]
    assert asked == [s.id for s in SECTIONS[4:]]
    assert all(body_for(s.id) in document for s in SECTIONS)


def test_agent_three_has_its_own_section_budget_and_timeout():
    content, research = ContentAgent(api_key=""), ResearchAgent(api_key="")
    assert (content.max_tokens, content.timeout_seconds) == (16000, 480)
    assert research.timeout_seconds is None


@pytest.mark.asyncio
async def test_per_call_timeout_overrides_the_default_deadline(tmp_path):
    settings = SystemConfig(_env_file=None, project_root=tmp_path, allow_external_ai=True,
                            api_timeout_seconds=10, api_max_retries=0, retry_backoff_seconds=0)

    class SlowProvider:
        async def complete(self, **request):
            await asyncio.sleep(0.2)
            return Completion("Done", 1, 1)

    request = {"agent": "Agent 3", "model": "fake", "max_tokens": 20, "messages": [{"role": "user", "content": "x"}]}
    runtime = RunRuntime(settings)
    with pytest.raises(RuntimeError, match="TimeoutError"):
        await runtime.call(SlowProvider(), timeout_seconds=0.01, **request)
    assert await runtime.call(SlowProvider(), **request) == "Done"


@pytest.mark.asyncio
async def test_base_agent_passes_its_timeout_to_the_runtime(tmp_path):
    settings = SystemConfig(_env_file=None, project_root=tmp_path, allow_external_ai=True)
    agent = ContentAgent(api_key="")
    agent.client = object()
    runtime = RunRuntime(settings)
    runtime.call = AsyncMock(return_value="Done")
    token = current_runtime.set(runtime)
    try:
        await agent._call_claude([{"role": "user", "content": "Write"}], system="Instructions")
    finally:
        current_runtime.reset(token)
    assert runtime.call.await_args.kwargs["timeout_seconds"] == 480
    assert runtime.call.await_args.kwargs["max_tokens"] == 16000


def test_section_page_targets_fit_the_document_target():
    low, high = config_manager.system_config.page_target
    assert sum(s.target_pages[0] for s in SECTIONS) >= low
    assert sum(s.target_pages[1] for s in SECTIONS) <= high
    with pytest.raises(ValueError, match="target_pages"):
        SectionSpec(id="sec-example", title="Example", instructions="Example", target_pages=[3, 2])
