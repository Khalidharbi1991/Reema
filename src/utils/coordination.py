"""Bounded request contracts for the SOP pipeline."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .specialists import SpecialistInputs


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")


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
