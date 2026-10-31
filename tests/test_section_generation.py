"""Agent 3 writes the SOP one configured section per model request."""

import json
import re
from unittest.mock import AsyncMock

import pytest

from src.agents import ContentAgent
from src.utils.config import config_manager
from src.utils.documents import SectionSpec, section_map

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
    agent = ContentAgent()
    agent._reply = AsyncMock(side_effect=fake_reply)
    document = await agent.generate_sop("Example", RESEARCH)

    prompts = [call.args[0][0]["content"] for call in agent._reply.await_args_list]
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
    agent = ContentAgent()
    agent._reply = AsyncMock(return_value=json.dumps({"section_id": "sec-roles", "body": "Misplaced"}))
    with pytest.raises(ValueError, match=r"Section 1 \(Introduction\) failed: Reply was for section 'sec-roles'"):
        await agent.generate_sop("Example", RESEARCH)
    agent._reply.assert_awaited_once()


@pytest.mark.asyncio
async def test_section_body_cannot_add_top_level_sections():
    agent = ContentAgent()
    agent._reply = AsyncMock(side_effect=lambda messages, system="": json.dumps(
        {"section_id": requested(messages[-1]["content"]), "body": "## Extra section\nText"}))
    with pytest.raises(ValueError, match="cannot add top-level sections"):
        await agent.generate_sop("Example", RESEARCH)


def test_section_page_targets_fit_the_document_target():
    low, high = config_manager.system_config.page_target
    assert sum(s.target_pages[0] for s in SECTIONS) >= low
    assert sum(s.target_pages[1] for s in SECTIONS) <= high
    with pytest.raises(ValueError, match="target_pages"):
        SectionSpec(id="sec-example", title="Example", instructions="Example", target_pages=[3, 2])
