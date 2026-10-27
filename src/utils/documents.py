"""Located document contracts. References are traceability, never certification."""

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .validation import REQUIRED_SECTIONS, _heading_key, validate_sop


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")

    @model_validator(mode="after")
    def nonblank_text(self):
        if any(isinstance(value, str) and not value.strip() for value in self.__dict__.values()):
            raise ValueError("Document contract text cannot be blank")
        return self


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SectionSpec(Contract):
    id: str = Field(pattern=r"^sec-[a-z0-9-]+$")
    title: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    display_title: str | None = None


class ExportStyle(Contract):
    font: str = Field(default="DejaVu Sans", pattern=r"^[A-Za-z ]{1,40}$")
    body_pt: int = Field(default=11, ge=10, le=14)
    margin_inches: float = Field(default=0.8, ge=0.6, le=1.2)
    line_spacing: float = Field(default=1.15, ge=1.0, le=1.6)
    arabic_font: str = Field(default="Arial", pattern=r"^[A-Za-z ]{1,40}$")


class TemplateLayout(Contract):
    heading_before_pt: int = Field(ge=6, le=30)
    table_padding_pt: int = Field(ge=3, le=9)
    paragraph_after_pt: int = Field(ge=3, le=12)


class DocumentProfile(Contract):
    sections: list[SectionSpec] = Field(min_length=11, max_length=11)
    max_review_cycles: int = Field(default=2, ge=1, le=3)
    require_applicable_control_references: bool = True
    style: ExportStyle = Field(default_factory=ExportStyle)
    template: str = "standard"
    document_label: str = Field(default="Standard Operating Procedure", min_length=1, max_length=100)
    layouts: dict[str, TemplateLayout] = Field(default_factory=lambda: {
        "standard": TemplateLayout(heading_before_pt=18, table_padding_pt=5, paragraph_after_pt=7),
        "compact": TemplateLayout(heading_before_pt=10, table_padding_pt=3, paragraph_after_pt=5)})

    @model_validator(mode="after")
    def mandatory(self):
        if self.template not in self.layouts:
            raise ValueError("Selected document template is not configured")
        ids = ("sec-introduction", "sec-definitions", "sec-roles", "sec-overview", "sec-procedures", "sec-flow",
               "sec-kpis", "sec-tools", "sec-compliance", "sec-appendices", "sec-control")
        expected = dict(zip(map(_heading_key, REQUIRED_SECTIONS), ids))
        if (len({s.id for s in self.sections}) != 11 or
                {_heading_key(s.title): s.id for s in self.sections} != expected):
            raise ValueError("Document profile must retain all eleven unique mandatory sections")
        return self


class SectionBody(Contract):
    section_id: str
    body: str = Field(min_length=1)


def validate_body(body):
    visible = mask_fences(body)
    if not body.strip() or re.search(r"(?m)^#{1,2}\s", visible):
        raise ValueError("Section bodies must be nonempty and cannot add top-level sections")
    from .diagrams import extract_flows
    extract_flows(body)


class SectionDraft(Contract):
    sections: list[SectionBody]

    def assemble(self, process_name, profile):
        indexed = {s.section_id: s.body for s in self.sections}
        if len(indexed) != len(self.sections) or set(indexed) != {s.id for s in profile.sections}:
            raise ValueError("Section draft must include each configured section exactly once")
        parts = [f"# {process_name} {profile.document_label}"]
        for number, section in enumerate(profile.sections, 1):
            body = indexed[section.id]
            validate_body(body)
            parts.append(f"## {number}. {section.display_title or section.title}\n\n{body}")
        content = "\n\n".join(parts) + "\n"
        validate_sop(content, profile)
        return content


def mask_fences(content):
    """Keep absolute offsets while hiding headings inside fenced examples."""
    return re.sub(r"(?ms)^(```|~~~).*?^\1[^\n]*$", lambda m: re.sub(r"[^\n]", " ", m.group()), content)


def section_map(content, profile, *, require_complete=False):
    headings = []
    known = {_heading_key(title): s.id for s in profile.sections for title in (s.title, s.display_title) if title}
    for match in re.finditer(r"(?m)^(#{1,2})[ \t]+(.+?)[ \t]*#*[ \t]*$", mask_fences(content)):
        key = _heading_key(match.group(2)).removesuffix(" kpis")
        if key in known or len(match.group(1)) == 2:
            headings.append((match, known.get(key, "extra-" + sha(key)[:16])))
    result = {}
    for number, (match, section_id) in enumerate(headings):
        if section_id in result:
            raise ValueError("Ambiguous duplicate document section: " + section_id)
        end = headings[number + 1][0].start() if number + 1 < len(headings) else len(content)
        result[section_id] = {"start": match.start(), "body_start": match.end(), "end": end,
                              "sha256": sha(content[match.end():end]), "title": match.group(2)}
    if require_complete:
        validate_sop(content, profile)
        if not {s.id for s in profile.sections} <= set(result):
            raise ValueError("Document does not match the configured section profile")
    return result


class Patch(SectionBody):
    base_section_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class SectionPatch(Contract):
    base_document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    patches: list[Patch] = Field(min_length=1)

    def apply(self, content, targets, profile):
        if self.base_document_sha256 != sha(content):
            raise ValueError("Revision refers to a stale document")
        ids = [p.section_id for p in self.patches]
        if len(set(ids)) != len(ids) or set(ids) != set(targets):
            raise ValueError("Revision must replace exactly the requested sections")
        locations = section_map(content, profile, require_complete=True)
        replacements = []
        for patch in self.patches:
            location = locations.get(patch.section_id)
            if not location or patch.base_section_sha256 != location["sha256"]:
                raise ValueError("Revision refers to a stale or unknown section")
            validate_body(patch.body)
            replacements.append((location["body_start"], location["end"], "\n\n" + patch.body.strip() + "\n\n"))
        for start, end, body in sorted(replacements, reverse=True):
            content = content[:start] + body + content[end:]
        section_map(content, profile, require_complete=True)
        return content


class ControlEvidence(Contract):
    source_id: str = Field(pattern=r"^SRC-[A-Za-z0-9_-]+$")
    source: str = Field(min_length=1)
    location: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    quote: str = Field(min_length=1)


class Control(Contract):
    id: str = Field(pattern=r"^CTRL-[A-Za-z0-9_-]+$")
    framework: str = Field(min_length=1)
    clause: str = Field(min_length=1)
    requirement: str = Field(min_length=1)
    applicability: Literal["applicable", "not_applicable", "undetermined"]
    rationale: str = Field(min_length=1)
    target_sections: list[str] = Field(min_length=1)
    evidence: list[ControlEvidence]


class ControlRegister(Contract):
    controls: list[Control]
    verification: Literal["unverified"] = "unverified"

    def validate_sources(self, sources, profile):
        if len({c.id for c in self.controls}) != len(self.controls):
            raise ValueError("Duplicate control IDs")
        allowed = {s.id for s in profile.sections}
        for control in self.controls:
            if len(set(control.target_sections)) != len(control.target_sections) or not set(control.target_sections) <= allowed:
                raise ValueError("Unknown or duplicate control target section")
            for evidence in control.evidence:
                source = sources.get(evidence.source_id)
                if not source or any(getattr(evidence, k) != source.get(k) for k in ("source", "location", "sha256")):
                    raise ValueError("Control evidence does not match authorized recorded provenance")
                if evidence.quote not in source.get("text", ""):
                    raise ValueError("Control evidence quote is absent from its recorded source excerpt")
        return self


class StandardsAnalysis(Contract):
    compliance_analysis: str = Field(min_length=1)
    control_register: ControlRegister


def legacy_register(standards):
    return ControlRegister(controls=[Control(id="CTRL-UNASSESSED-" + str(i), framework=s, clause="Not established",
        requirement="Establish applicable requirements using authorized evidence", applicability="undetermined",
        rationale="Legacy narrative contains no typed applicability or supporting evidence", target_sections=["sec-compliance"], evidence=[])
        for i, s in enumerate(standards, 1)])


def control_coverage(content, register, sources, profile):
    register.validate_sources(sources, profile)
    locations = section_map(content, profile, require_complete=True)
    visible = mask_fences(content)
    rows, errors, warnings = [], [], []
    for control in register.controls:
        referenced = [section for section in control.target_sections
                      if f"[{control.id}]" in visible[locations[section]["body_start"]:locations[section]["end"]]]
        missing = sorted(set(control.target_sections) - set(referenced))
        if control.applicability == "applicable" and missing and profile.require_applicable_control_references:
            errors.append(f"{control.id}: required control reference absent from {', '.join(missing)}")
        if not control.evidence:
            warnings.append(f"{control.id}: missing supporting source evidence")
        if control.applicability == "undetermined":
            warnings.append(f"{control.id}: applicability requires human determination")
        rows.append({"control_id": control.id, "applicability": control.applicability,
                     "referenced_sections": referenced, "missing_sections": missing,
                     "evidence_status": "located_unverified" if control.evidence else "missing",
                     "semantic_coverage": "requires_human_verification"})
    return {"document_sha256": sha(content), "controls": rows, "errors": errors, "warnings": warnings,
            "verification": "unverified"}


class LocatedFinding(Contract):
    severity: Literal["critical", "major", "minor"]
    description: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, gt=0)
    action: str = Field(min_length=1)


class LocatedAssessment(Contract):
    quality_score: int = Field(ge=0, le=100)
    decision: Literal["acceptable", "revise"]
    issues: list[LocatedFinding]
    recommendations: list[str]
    summary: str = Field(min_length=1, max_length=2000)


def locate_findings(content, issues, profile):
    locations = section_map(content, profile)
    result = []
    for issue in issues:
        issue = LocatedFinding.model_validate(issue)
        location = locations.get(issue.section_id)
        if location and issue.start is None and issue.end is None:
            body = content[location["body_start"]:location["end"]]
            matches = list(re.finditer(re.escape(issue.quote), body))
            if len(matches) != 1:
                raise ValueError("Finding quote must identify exactly one location, or supply exact offsets")
            issue.start = location["body_start"] + matches[0].start()
            issue.end = location["body_start"] + matches[0].end()
        if (not location or issue.start is None or issue.end is None or not location["body_start"] <= issue.start < issue.end <= location["end"]
                or content[issue.start:issue.end] != issue.quote):
            raise ValueError("Review finding has an invalid section, offset or quoted location")
        value = issue.model_dump()
        value["finding_id"] = "F-" + sha(issue.section_id + "\n" + issue.description + "\n" + issue.quote + "\n" + issue.severity + "\n" + issue.action)[:16]
        value["blocking"] = issue.severity in {"critical", "major"}
        result.append(value)
    return list({i["finding_id"]: i for i in result}.values())


def validate_located_review(review, content, profile):
    if "review_contract" not in review:
        return  # Public legacy worker adapters remain supported.
    if review["review_contract"] != "located_v1" or review.get("document_sha256") != sha(content):
        raise ValueError("Review does not bind the current document")
    raw = review.get("issues")
    if not isinstance(raw, list):
        raise ValueError("Located review needs a finding list")
    try:
        located = locate_findings(content, [{k: f[k] for k in LocatedFinding.model_fields} for f in raw], profile)
    except (KeyError, TypeError):
        raise ValueError("Incomplete located review finding") from None
    if len(located) != len(raw) or any(a != b for a, b in zip(located, raw)):
        raise ValueError("Located review finding identity or blocking condition changed")
    if review.get("needs_revision") and not raw:
        raise ValueError("Revision requires actionable located findings")


class Correction(Contract):
    finding_id: str
    status: Literal["resolved", "open"]
    rationale: str = Field(min_length=1)
    section_id: str
    quote: str = Field(min_length=1)


class CorrectionAssessment(Contract):
    corrections: list[Correction]

    def validate_against(self, content, findings, profile):
        expected = {f["finding_id"]: f for f in findings}
        if len({c.finding_id for c in self.corrections}) != len(self.corrections) or {c.finding_id for c in self.corrections} != set(expected):
            raise ValueError("Correction recheck must cover every original finding exactly once")
        locations = section_map(content, profile, require_complete=True)
        for correction in self.corrections:
            if correction.section_id != expected[correction.finding_id]["section_id"]:
                raise ValueError("Correction recheck changed the finding location")
            loc = locations[correction.section_id]
            if correction.quote not in content[loc["body_start"]:loc["end"]]:
                raise ValueError("Correction recheck has no supporting text in the revised section")
        return self
