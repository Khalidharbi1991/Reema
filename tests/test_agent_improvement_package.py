"""Offline behavioral baselines; fake completions do not measure model reasoning."""

from unittest.mock import AsyncMock

import pytest

from src.agents import SecretaryAgent
from src.utils.handoffs import (
    AgentHandoff, ComplianceResult, EvidenceReference,
    ReviewResult, adapt_handoff, payload_json,
)


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
async def test_communication_record_does_not_claim_dispatch():
    secretary = SecretaryAgent()
    secretary._reply = AsyncMock()
    result = await secretary.coordinate_team_communication("Check pending evidence", "Abdullah", ["Agent 2"])
    assert result["status"] == "recorded" and result["dispatch_status"] == "not_dispatched"
    assert secretary.communication_log == [result]
    secretary._reply.assert_not_awaited()


