"""Local human decisions bound to the exact exported document bytes.

This is a local audit record, not an identity service or digital signature.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .validation import validate_output_files


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    process_name: str
    status: Literal["awaiting_human_approval", "approved", "rejected"] = "awaiting_human_approval"
    # None for a draft no model reviewed (a Claude Code generate run); older records always carry a score.
    quality_score: Optional[int] = Field(default=None, ge=0, le=100)
    created_at: str
    artifacts: Dict[str, Artifact] = Field(min_length=1)
    supporting_records: Dict[str, Artifact] = Field(default_factory=dict)
    reviewer: Optional[str] = None
    decided_at: Optional[str] = None
    notes: str = ""

    @model_validator(mode="after")
    def validate_decision(self):
        if self.status == "awaiting_human_approval":
            if self.reviewer is not None or self.decided_at is not None:
                raise ValueError("Pending records cannot contain an approval identity")
        elif not self.reviewer or not self.decided_at:
            raise ValueError("Decisions require a reviewer and timestamp")
        return self


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def create_pending_record(path: Path, process_name: str, output_files: dict, quality_score: Optional[int],
                          supporting_records=None):
    validate_output_files(output_files, list(output_files))
    record = ApprovalRecord(
        process_name=process_name, quality_score=quality_score, created_at=timestamp(),
        artifacts={fmt: Artifact(path=str(Path(name).resolve()), sha256=checksum(name))
                   for fmt, name in output_files.items()},
        supporting_records={key: Artifact(path=str(Path(name).resolve()), sha256=checksum(name))
                            for key, name in (supporting_records or {}).items()},
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    # A run has its own directory. Never replace another run's approval record.
    with path.open("x", encoding="utf-8") as stream:
        stream.write(record.model_dump_json(indent=2) + "\n")
    return record


def read_record(path: Path):
    return ApprovalRecord.model_validate_json(path.read_text(encoding="utf-8"))


def record_decision(path: Path, decision: str, reviewer: str, notes: str = ""):
    if decision not in ("approved", "rejected") or not reviewer.strip():
        raise ValueError("A human reviewer and an approved/rejected decision are required")
    # Exclusive creation prevents concurrent CLI decisions from overwriting each other.
    lock = path.with_suffix(path.suffix + ".lock")
    # Close the lock handle before unlinking, including on Windows.
    lock.open("x", encoding="utf-8").close()
    try:
        record = read_record(path)
        if record.status != "awaiting_human_approval":
            raise ValueError("This run already has a human decision; generate a new run for revisions")
        if decision == "approved":
            files = {fmt: artifact.path for fmt, artifact in record.artifacts.items()}
            validate_output_files(files, list(files))
            for artifact in [*record.artifacts.values(), *record.supporting_records.values()]:
                if not Path(artifact.path).is_file():
                    raise ValueError("A reviewed artifact or supporting record is missing")
                if checksum(artifact.path) != artifact.sha256:
                    raise ValueError("An output changed after review; generate a new run before approval")
        values = record.model_dump()
        values.update(status=decision, reviewer=reviewer.strip(), decided_at=timestamp(), notes=notes)
        record = ApprovalRecord.model_validate(values)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
        temporary.replace(path)
        return record
    finally:
        lock.unlink()
