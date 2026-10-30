"""Explicit capability adapters for SOP coordination; no arbitrary tools."""

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError


class Inputs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ContentInputs(Inputs):
    process_name: str = Field(min_length=1)
    research_data: dict[str, JsonValue]


class ReviewInputs(Inputs):
    content: str = Field(min_length=1)


class LocatedRevisionInputs(ReviewInputs):
    findings: list[dict[str, JsonValue]] = Field(min_length=1)
    # Omitted (None) keeps the positional call and full-profile check.
    require_complete: bool | None = None


class FinishedRevisionInputs(LocatedRevisionInputs):
    # Revising a finished SOP: full-profile choice is explicit and the scope limits apply.
    require_complete: bool
    finished_sop: bool


class FormatInputs(ReviewInputs):
    output_formats: list[str]
    process_name: str = Field(min_length=1)


PIPELINE_CAPABILITIES = {
    "content": ("ContentAgent", "generate_sop", ContentInputs),
    "review_existing": ("ReviewAgent", "review_existing", ReviewInputs),
    "revise_finished": ("ContentAgent", "revise_sections", FinishedRevisionInputs),
    "recheck_finished": ("ReviewAgent", "recheck_corrections", FinishedRevisionInputs),
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

