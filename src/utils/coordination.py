"""Bounded request/session contracts and explicit advisory coordination data."""

import json
import re
import unicodedata
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .handoffs import HandoffMetadata, payload_json
from .specialists import SpecialistInputs

# Specialists Ahmad may consult in chat. Abdullah (leader_agent) leads only the SOP pipeline.
AGENT_KEYS = {"research_agent", "standards_agent", "content_agent",
              "review_agent", "access_agent", "problem_agent", "data_agent", "building_design_agent",
              "euc_agent"}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")


class Selection(Contract):
    agent: str
    capability: Literal["advice"] = "advice"
    reasons: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def supported(self):
        if self.agent not in AGENT_KEYS:
            raise ValueError("Unsupported advisory capability")
        return self


class RequestPlan(Contract):
    request_id: str = Field(default_factory=lambda: uuid4().hex)
    objective: str = Field(min_length=1)
    intent: Literal["advisory", "local_action", "unsupported_action"] = "advisory"
    status: Literal["ready", "needs_clarification", "unsupported"] = "ready"
    selections: list[Selection] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    excluded_agents: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique(self):
        if len({s.agent for s in self.selections}) != len(self.selections):
            raise ValueError("Duplicate capability selection")
        if self.intent != "advisory" and self.selections:
            raise ValueError("Local or unsupported actions cannot consult specialists")
        return self


def normalized_text(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", value)
    value = value.translate(str.maketrans("أإآى", "اااي"))
    return re.sub(r"\bو(?=ال)", "و ", value)


def plan_request(message, routing, objective=""):
    if message.startswith("/"):
        return RequestPlan(objective=objective or message, intent="local_action")
    value = normalized_text(message)
    if re.match(r"^(?:(?:please|لو سمحت|من فضلك)\s+)?(?:send|schedule|book|buy|purchase|deploy|approve|ارسل|احجز|اشتري|وافق|انشر|حدد موعد)\b", value, re.I):
        return RequestPlan(objective=objective or message, intent="unsupported_action", status="unsupported",
                           questions=["This chat can draft or advise, but cannot perform that external action."])
    if re.match(r"^(?:should|can we|is it)\b", message, re.I) and re.search(r"\bwithout\b", message, re.I):
        return RequestPlan(objective=objective or message, status="needs_clarification",
                           questions=["Are you asking about the risk of missing a prerequisite, or excluding that topic from the advice?"])
    if re.match(r"^(?:هل|ينفع|اقدر)\b", value) and "بدون" in value:
        return RequestPlan(objective=objective or message, status="needs_clarification",
            questions=["هل تسأل عن مخاطر غياب المتطلب أم تريد استبعاده من نطاق الإجابة؟"])
    selections = []
    excluded = set()
    negators = "|".join(re.escape(normalized_text(term)) for term in routing.negation_terms)
    for rule in routing.routes:
        if rule.agent not in AGENT_KEYS:
            continue
        reasons = []
        for keyword in rule.keywords:
            prefix = r"(?:و)?" if re.search(r"[\u0600-\u06ff]", keyword) else ""
            for match in re.finditer(r"(?<!\w)" + prefix + re.escape(normalized_text(keyword)) + r"(?!\w)", value):
                if any(match.start() >= ex.start() and match.end() <= ex.end()
                       for phrase in rule.exclude_phrases
                       for ex in re.finditer(re.escape(normalized_text(phrase)), value)):
                    continue
                # Negation applies within the current clause; contrast starts a new clause.
                before = re.split(r"[,.;!?،؛؟\n]|\b(?:but|instead|however|لكن|ولكن|بس)\b", value[:match.start()])[-1]
                after = re.split(r"[,.;!?،؛؟\n]|\b(?:but|instead|however|لكن|ولكن|بس)\b", value[match.end():])[0]
                before = re.sub(r"\b(?:not only|ليس فقط)\b", "", before)
                before = re.sub(r"\b(?:(?:do not|don't)\s+(?:skip|avoid|exclude)|لا (?:تتجاهل|تستبعد))\b", "", before)
                if re.search(r"(?<!\w)(?:" + negators + r")(?!\w)", before):
                    excluded.add(rule.agent)
                    continue
                if re.match(r"\s+(?:مو مطلوب|غير مطلوب|ليس ضمن)", after):
                    excluded.add(rule.agent)
                    continue
                reasons.append(keyword)
        if reasons:
            existing = next((s for s in selections if s.agent == rule.agent), None)
            if existing:
                existing.reasons.extend(reasons)
            else:
                selections.append(Selection(agent=rule.agent, reasons=sorted(set(reasons))))
    if excluded & {s.agent for s in selections}:
        return RequestPlan(objective=objective or message, status="needs_clarification", selections=selections,
            excluded_agents=sorted(excluded), questions=["The request both includes and excludes a capability. Clarify its scope. / الطلب يتضمن نفس المجال ويستبعده؛ حدد النطاق المطلوب."])
    if len(selections) > routing.max_specialists:
        return RequestPlan(objective=objective or message, status="needs_clarification",
                           selections=selections, questions=["This request spans too many capabilities. Narrow the objective or split the request."],
                           limitations=["No matched specialist has been silently dropped."])
    return RequestPlan(objective=objective or message, selections=selections, excluded_agents=sorted(excluded - {s.agent for s in selections}),
                       limitations=["Deterministic phrase and clause rules; implied intent may need clarification."])


class IntentResolution(Contract):
    intent: Literal["advisory", "unsupported_action", "local_action"]
    agents: list[str] = Field(max_length=10)
    excluded_agents: list[str] = Field(default_factory=list, max_length=10)
    status: Literal["ready", "needs_clarification"]
    questions: list[str]
    rationale: str = Field(min_length=1, max_length=1500)

    @model_validator(mode="after")
    def capabilities(self):
        if set(self.agents + self.excluded_agents) - AGENT_KEYS or len(set(self.agents)) != len(self.agents) or set(self.agents) & set(self.excluded_agents):
            raise ValueError("Intent resolution contains unknown, duplicate or excluded capabilities")
        if self.intent != "advisory" and self.agents:
            raise ValueError("Action resolution cannot consult or execute capabilities")
        if self.status == "needs_clarification" and not self.questions:
            raise ValueError("Ambiguous intent needs an explicit clarification")
        return self


class SessionFact(Contract):
    key: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source: Literal["user_statement", "local_command", "coordination_record"] = "user_statement"
    turn: int = Field(ge=0)


class SessionContext(Contract):
    area: Literal["work", "personal"]
    project: str = ""
    objective: str = ""
    decisions: dict[str, SessionFact] = Field(default_factory=dict)
    constraints: dict[str, SessionFact] = Field(default_factory=dict)
    pending: dict[str, SessionFact] = Field(default_factory=dict)
    outcomes: dict[str, SessionFact] = Field(default_factory=dict)
    requests: dict[str, SessionFact] = Field(default_factory=dict)
    selected_specialists: list[str] = Field(default_factory=list)
    turn: int = 0

    def bounded(self, limit):
        if len(self.model_dump_json()) > limit:
            raise ValueError("Session context exceeds its budget; edit or clear explicit entries. No decisions were discarded.")
        return self


class AdvisoryInput(Contract):
    message: str = Field(min_length=1)
    shared_context: str = Field(min_length=1)
    session: SessionContext
    history: list[dict[str, str]] = Field(default_factory=list)


class Position(Contract):
    topic: str = Field(min_length=1)
    stance: str = Field(min_length=1)


class Advice(Contract):
    advice: str = Field(min_length=1)
    metadata: HandoffMetadata = Field(default_factory=HandoffMetadata)
    positions: list[Position] = Field(default_factory=list)
    structured: bool = True

    @model_validator(mode="after")
    def content_present(self):
        if not self.advice.strip():
            raise ValueError("Empty advisory response")
        return self


def parse_advice(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Specialist returned no advisory content")
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    if clean.startswith("{"):
        return Advice.model_validate_json(clean)
    return Advice(advice=text, structured=False,
                  metadata=HandoffMetadata(unresolved_questions=["Unstructured advice; disagreements have not been fully assessed."]))


class Consultation(Contract):
    agent: str
    name: str
    status: Literal["completed", "failed"]
    result: Advice | None = None
    error_type: str | None = None


class Briefing(Contract):
    coordinator: Literal["Ahmad"] = "Ahmad"
    status: Literal["ready", "partial", "failed"]
    consultations: list[Consultation]
    disagreements: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    consensus: Literal["not_established"] = "not_established"
    objective: str = ""
    next_steps: list[str] = Field(default_factory=list)


class DocumentationRequest(Contract):
    process_name: str = Field(min_length=1)
    custom: bool = False
    formats: list[Literal["markdown", "html", "docx", "pdf"]] = Field(min_length=1)
    specialists: list[Literal["access", "problem", "data", "euc"]] = Field(default_factory=list)
    objective: str = Field(min_length=1, max_length=8000)
    constraints: list[str] = Field(default_factory=list)
    required_deliverables: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    specialist_inputs: SpecialistInputs | None = None

    @model_validator(mode="after")
    def supported_deliverables(self):
        if set(self.required_deliverables) - {"SOP", *self.formats}:
            raise ValueError("Required deliverables must be the SOP and requested output formats")
        return self


class WorkflowPlan(Contract):
    request: DocumentationRequest
    dependencies: dict[str, list[str]]
    workflow: Literal["sop_v1"] = "sop_v1"
