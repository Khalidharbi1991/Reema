"""Validated internal handoffs with lossless adapters for the public agent APIs.

These contracts describe supplied/model-produced material. Provenance, a model
score, or a proposed deliverable never implies factual verification or approval.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, model_validator

from .quality import Finding


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str = Field(pattern=r"^SRC-[A-Za-z0-9_-]+$")
    source: str = Field(min_length=1)
    location: str = Field(min_length=1)
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    verification: Literal["unverified"] = "unverified"


class HandoffFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    description: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    applicability: Literal["applicable", "not_applicable", "unknown"] = "unknown"
    verification: Literal["unverified"] = "unverified"


class Deliverable(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    status: Literal["proposed", "generated_draft"] = "proposed"


class HandoffMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    findings: list[HandoffFinding] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    deliverables: list[Deliverable] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_references(self):
        ids = [item.source_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate evidence identifiers in handoff")
        if any(set(item.source_ids) - set(ids) for item in self.findings):
            raise ValueError("Finding refers to evidence absent from the handoff")
        return self


class AgentHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1] = 1
    process_name: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    stage: Literal["research", "enrichment", "review"]
    payload: dict[str, JsonValue] | str
    metadata: HandoffMetadata = Field(default_factory=HandoffMetadata)
    verification: Literal["unverified"] = "unverified"

    @model_validator(mode="after")
    def check_identity(self):
        if not self.payload or isinstance(self.payload, str) and not self.payload.strip():
            raise ValueError("Agent handoff has no content")
        if isinstance(self.payload, dict) and "process_name" in self.payload:
            if self.payload["process_name"] != self.process_name:
                raise ValueError("Handoff process identity does not match the request")
        return self


_JSON = TypeAdapter(JsonValue)


def payload_json(value):
    """Serialize every supplied field; reject unsupported values instead of stringifying them."""
    return json.dumps(_JSON.validate_python(value, strict=True), ensure_ascii=False, allow_nan=False)


def adapt_handoff(process_name, producer, stage, payload, *, text_key=None, sources=None):
    """Validate a legacy result without dropping unknown extension fields.

    Structured metadata is opt-in under handoff_metadata. Legacy narrative is
    left intact, never parsed into purported evidence/findings. Only recorded
    runtime source identities can be added as provenance by this adapter.
    """
    if stage == "research" and not isinstance(payload, dict):
        raise ValueError("Research handoff must return a mapping")
    if text_key is not None:
        text = payload.get(text_key) if isinstance(payload, dict) else payload
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{producer} returned no valid {text_key}")
    metadata = HandoffMetadata.model_validate(
        payload.get("handoff_metadata", {}) if isinstance(payload, dict) else {})
    # Work with a new model; do not mutate worker-owned dictionaries.
    data = metadata.model_dump()
    cited = set(re.findall(r"\[(SRC-[A-Za-z0-9_-]+)\]", payload_json(payload)))
    supplied_ids = {item.source_id for item in metadata.evidence}
    for item in metadata.evidence:
        record = (sources or {}).get(item.source_id)
        if record and (item.source != record.get("source") or item.location != record.get("location")
                       or item.sha256 is not None and item.sha256 != record.get("sha256")):
            raise ValueError("Handoff evidence identity conflicts with recorded source provenance")
    for source_id in sorted(cited | supplied_ids):
        record = (sources or {}).get(source_id)
        if record and record.get("source") and record.get("location"):
            if source_id not in supplied_ids:
                data["evidence"].append(EvidenceReference(
                    source_id=source_id, source=record["source"], location=record["location"],
                    sha256=record.get("sha256")).model_dump())
        else:
            question = f"Source provenance not recorded for {source_id}"
            if question not in data["unresolved_questions"]:
                data["unresolved_questions"].append(question)
    return AgentHandoff(process_name=process_name, producer=producer, stage=stage,
                        payload=payload, metadata=HandoffMetadata.model_validate(data))


class ReviewResult(BaseModel):
    """Gate-relevant fields; legacy extras remain in the enclosing handoff payload."""
    model_config = ConfigDict(extra="forbid", strict=True)
    quality_score: int = Field(ge=0, le=100)
    needs_revision: bool = False
    approval_status: Literal["APPROVED", "REQUIRES_REVISION", "REVISION_REQUESTED",
                             "PENDING_REVIEW", "APPROVED_WITH_CHANGES"] | None = None
    issues: list[Finding] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    refined_content: str | None = None

    @model_validator(mode="after")
    def check_decision(self):
        if self.approval_status == "APPROVED" and (
                self.needs_revision or any(issue.severity == "critical" or issue.blocking for issue in self.issues)):
            raise ValueError("Contradictory model review decision")
        if self.refined_content is not None and not self.refined_content.strip():
            raise ValueError("Reviewer returned an empty rewrite")
        return self

    @classmethod
    def from_legacy(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Review must return a mapping")
        return cls.model_validate({key: item for key, item in value.items() if key in cls.model_fields})


class ComplianceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    compliant: bool
    findings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_decision(self):
        if self.compliant and self.findings:
            raise ValueError("Contradictory compliance decision with unresolved findings")
        return self

    @classmethod
    def from_legacy(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Compliance result must return a mapping")
        return cls.model_validate({key: item for key, item in value.items() if key in cls.model_fields})
