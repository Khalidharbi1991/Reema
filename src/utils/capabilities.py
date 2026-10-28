"""Explicit capability adapters shared by chat and SOP coordination; no arbitrary tools."""

import json
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError
from .coordination import AdvisoryInput, Advice
from .handoffs import payload_json


class Inputs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ResearchInputs(Inputs):
    process_name: str = Field(min_length=1)
    standards: list[str]


class EvidenceResearchInputs(ResearchInputs):
    research_context: dict[str, JsonValue] | None = None


class AccessResearchInputs(ResearchInputs):
    research_data: dict[str, JsonValue] | None = None


class ProblemResearchInputs(ResearchInputs):
    incident_data: dict[str, JsonValue] | None = None


class AnalyticsInputs(Inputs):
    process_name: str = Field(min_length=1)
    kpis: list[str]
    research_data: dict[str, JsonValue] | None = None


class ContentInputs(Inputs):
    process_name: str = Field(min_length=1)
    research_data: dict[str, JsonValue]


class AccessInputs(Inputs):
    process_name: str = Field(min_length=1)
    access_requirements: dict[str, JsonValue]


class EndpointInputs(Inputs):
    process_name: str = Field(min_length=1)
    endpoint_requirements: dict[str, JsonValue]


class DashboardInputs(Inputs):
    process_name: str = Field(min_length=1)
    metrics: list[dict[str, JsonValue]]


class ReviewInputs(Inputs):
    content: str = Field(min_length=1)


class RefineInputs(ReviewInputs):
    feedback: list[str]


class LocatedRevisionInputs(ReviewInputs):
    findings: list[dict[str, JsonValue]] = Field(min_length=1)


class AccessComplianceInputs(ReviewInputs):
    regulations: list[str]


class ProblemComplianceInputs(Inputs):
    process_name: str = Field(min_length=1)
    content: str = Field(min_length=1)


class FormatInputs(ReviewInputs):
    output_formats: list[str]
    process_name: str = Field(min_length=1)


PIPELINE_CAPABILITIES = {
    "research": ("ResearchAgent", "research_process", EvidenceResearchInputs),
    "standards": ("StandardsAgent", "analyze_compliance", ResearchInputs),
    "data": ("DataAgent", "design_analytics_framework", AnalyticsInputs),
    "access": ("AccessAgent", "analyze_access_requirements", AccessResearchInputs),
    "problem": ("ProblemAgent", "research_problem_management", ProblemResearchInputs),
    "euc": ("EUCAgent", "analyze_endpoint_requirements", ResearchInputs),
    "content": ("ContentAgent", "generate_sop", ContentInputs),
    "access_content": ("AccessAgent", "generate_access_content", AccessInputs),
    "problem_content": ("ProblemAgent", "generate_problem_content", ContentInputs),
    "euc_content": ("EUCAgent", "generate_endpoint_content", EndpointInputs),
    "dashboard": ("DataAgent", "create_dashboard_design", DashboardInputs),
    "review": ("ReviewAgent", "review_content", ReviewInputs),
    "refine": ("ContentAgent", "refine_content", RefineInputs),
    "revise_sections": ("ContentAgent", "revise_sections", LocatedRevisionInputs),
    "recheck": ("ReviewAgent", "recheck_corrections", LocatedRevisionInputs),
    "access_compliance": ("AccessAgent", "validate_access_compliance", AccessComplianceInputs),
    "problem_compliance": ("ProblemAgent", "validate_problem_compliance", ProblemComplianceInputs),
    "format": ("FormatAgent", "convert_to_formats", FormatInputs),
}


async def invoke_pipeline(workers, capability, arguments):
    if capability not in PIPELINE_CAPABILITIES:
        raise ValueError("Unsupported document capability")
    worker, method, schema = PIPELINE_CAPABILITIES[capability]
    try:
        inputs = schema.model_validate(arguments).model_dump()
    except ValidationError:
        raise ValueError(f"Invalid {capability} inputs; expected fields: " + ", ".join(schema.model_fields)) from None
    # Preserve positional public signatures for existing registered workers.
    values = [inputs[field] for field in schema.model_fields]
    while values and values[-1] is None:
        values.pop()
    return await getattr(workers[worker], method)(*values)


async def invoke_advice(agent, arguments, fallback_system=""):
    inputs = AdvisoryInput.model_validate(arguments)
    builder = getattr(agent, "_build_system_prompt", None)
    system = fallback_system + ("\n\n" + builder() if callable(builder) else "")
    system += ("\nProvide advisory analysis only. Do not execute actions or claim approvals. "
               "Preserve explicit user decisions and constraints; label uncertainty and missing evidence. "
               "Return JSON matching this schema:\n" + json.dumps(Advice.model_json_schema()))
    return await agent._call_claude(inputs.history + [{"role": "user", "content": inputs.shared_context}], system=system)
