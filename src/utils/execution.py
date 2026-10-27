"""Locally authenticated, bounded SOP recovery records; not a general scheduler."""

import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
from copy import deepcopy

from pydantic import Field, JsonValue
from .coordination import Contract, DocumentationRequest
from .handoffs import adapt_handoff, payload_json
from .runs import atomic_json
from .ownership import RunLease

PHASES = {"planned", "researched", "generated", "drafted", "reviewed", "ready", "exported"}
FIELDS = {"research": "raw_research", "standards": "compliance_analysis", "data": "analytics_framework",
          "access": "access_analysis", "problem": "problem_research", "dashboard": "dashboard_design",
          "access_content": "access_content", "problem_content": "problem_content"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_digest(directory, patterns):
    directory = Path(directory)
    files = sorted({p for pattern in patterns for p in directory.rglob(pattern) if p.is_file()})
    return digest([(str(p.relative_to(directory)), file_digest(p)) for p in files])


def execution_identity(config, request, source_index):
    settings = config.system_config
    runtime_fields = ("leader_model", "worker_model", "max_run_tokens", "max_prompt_chars", "review_chunk_chars",
                      "knowledge_context_chars", "max_concurrent_agents", "enforce_page_target", "page_target",
                      "api_timeout_seconds", "api_max_retries", "retry_backoff_seconds", "model_prices")
    dependency_root = Path(__file__).resolve().parents[2]
    return {
        "request": digest(request.model_dump()),
        "dependency_locks": digest({name: file_digest(dependency_root / name) if (dependency_root / name).is_file() else None
                                    for name in ("requirements.lock", "requirements-dev.lock", "uv.lock", "pyproject.toml")}),
        "configuration": digest({"agents": config.agents_config, "processes": config.process_definitions,
                                  "standards": config.standards_mapping,
                                  "routing": config.assistant_routing.model_dump(),
                                  "document_profile": config.document_profile.model_dump(),
                                  "specialist_policy": config.specialist_policy.model_dump(),
                                  "runtime": {key: getattr(settings, key) for key in runtime_fields}}),
        "permissions": file_digest(settings.reference_manifest) if settings.reference_manifest.exists() else digest("absent"),
        "references": digest([{key: r[key] for key in ("id", "source", "sha256", "location", "classification")}
                              for r in source_index.records]),
        "knowledge": tree_digest(settings.knowledge_dir, ["*.md"]),
        "templates": tree_digest(settings.templates_dir, ["*"]),
        "code": tree_digest(Path(__file__).resolve().parents[1], ["*.py"]),
    }


def recovery_key(root, *, create=False):
    path = Path(root) / ".recovery-key"
    if path.is_symlink():
        raise ValueError("Recovery key must not be a symlink")
    if create:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(secrets.token_bytes(32))
    if not path.is_file():
        raise ValueError("Recovery key is unavailable; this execution cannot be resumed")
    if os.name == "posix" and path.stat().st_mode & 0o077:
        raise ValueError("Recovery key permissions must be private to the local user")
    key = path.read_bytes()
    if len(key) != 32:
        raise ValueError("Invalid recovery key")
    return key


class CompletedCall(Contract):
    arguments_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    result: JsonValue


class ExecutionRecord(Contract):
    version: int = 1
    request: DocumentationRequest
    identity: dict[str, str]
    completed_calls: dict[str, CompletedCall]
    sources: dict[str, dict]
    lineage: list[dict]
    usage: dict
    checkpoint_hashes: dict[str, str]
    run_sha256: str
    run_state: dict = Field(default_factory=dict)
    completed_assessments: dict[str, dict] = Field(default_factory=dict, max_length=3000)


def validate_result(capability, result, process_name, sources):
    if capability == "content":
        if not isinstance(result, str) or not result.strip():
            raise ValueError("Content capability returned no document text")
        return
    if capability not in FIELDS:
        raise ValueError("Unknown recoverable capability")
    try:
        adapt_handoff(process_name, capability,
                      "research" if capability in {"research", "standards", "data", "access", "problem"} else "enrichment",
                      result, text_key=FIELDS[capability], sources=sources)
    except ValueError:
        raise ValueError(f"Invalid {capability} output; check {FIELDS[capability]}, process identity and metadata") from None


class ExecutionJournal:
    def __init__(self, store, config, request, identity, *, previous=None, parent=None):
        self.store = store
        self.key = recovery_key(config.system_config.output_dir, create=True)
        self.data = previous.model_dump() if previous else {
            "version": 2, "request": request.model_dump(), "identity": identity,
            "completed_calls": {}, "sources": {}, "lineage": [], "usage": {},
            "checkpoint_hashes": {}, "run_sha256": "", "run_state": {}, "completed_assessments": {},
        }
        if previous:
            self.data["lineage"].append({"run": str(parent), "accounted_tokens": previous.usage.get("accounted_tokens", 0),
                                          "new_calls": len(previous.usage.get("calls", []))})
        store.journal = self
        self.data["version"] = 2
        self.data.setdefault("completed_assessments", {})
        store.state["execution_version"] = 2
        store.flush()

    def snapshot(self):
        self.data["checkpoint_hashes"] = self.store.state["checkpoints"]
        self.data["usage"] = self.store.state.get("usage", self.data["usage"])
        self.data["run_sha256"] = file_digest(self.store.directory / "run.json")
        self.data["run_state"] = deepcopy(self.store.state)
        signature = hmac.new(self.key, payload_json(self.data).encode(), hashlib.sha256).hexdigest()
        atomic_json(self.store.directory / "execution.json", {"record": self.data, "signature": signature})

    def assessment(self, key, value, sources):
        if len(self.data["completed_assessments"]) >= 3000:
            raise ValueError("Assessment checkpoint limit exceeded")
        self.data["completed_assessments"][key] = deepcopy(value)
        self.data["sources"] = deepcopy(sources)
        self.store.flush()

    def record(self, capability, arguments, result, sources):
        self.data["completed_calls"][capability] = {"arguments_sha256": digest(arguments), "result": deepcopy(result)}
        self.data["sources"] = sources.copy()
        self.store.flush()


def load_execution(directory, config, *, lease=None):
    directory = Path(directory).resolve()
    if lease is None:
        with RunLease(directory) as held:
            return load_execution(directory, config, lease=held)
    lease.permits(directory)
    if directory.parent != (config.system_config.output_dir / "runs").resolve():
        raise ValueError("Model recovery requires the original output root and runs directory")
    path = directory / "execution.json"
    if not path.is_file() or path.stat().st_size > 50_000_000:
        raise ValueError("Missing or oversized execution recovery record; legacy runs support ready-only export recovery")
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if set(envelope) != {"record", "signature"} or not isinstance(envelope["signature"], str):
        raise ValueError("Malformed execution recovery record")
    expected = hmac.new(recovery_key(config.system_config.output_dir), payload_json(envelope["record"]).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, envelope["signature"]):
        raise ValueError("Execution recovery record was changed or its key is invalid")
    record = ExecutionRecord.model_validate(envelope["record"])
    if record.version not in {1, 2}:
        raise ValueError("Recovery version is unsupported")
    if record.version == 2:
        state = record.run_state
        if not state or hashlib.sha256((json.dumps(state, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()).hexdigest() != record.run_sha256:
            raise ValueError("Authenticated run snapshot does not match its hash")
        lease.permits(directory, state.get("owner"))
    else:
        state = json.loads((directory / "run.json").read_text())
    if state.get("status") != "running" or record.version == 1:
        if file_digest(directory / "run.json") != record.run_sha256:
            raise ValueError("Run metadata changed or recovery version is unsupported")
    if state.get("status") not in {"failed", "cancelled", "running"} or (state.get("status") == "running" and (record.version != 2 or not state.get("owner"))):
        raise ValueError("Model recovery needs a failed/cancelled run or a locally abandoned authenticated owner")
    if "ready" in record.checkpoint_hashes:
        raise ValueError("A ready checkpoint exists; use offline export resume")
    if not record.completed_calls and not (record.version == 2 and state.get('status') == 'running'):
        raise ValueError("No completed research or generation is available to recover")
    tokens = record.usage.get("accounted_tokens", 0)
    if type(tokens) is not int or tokens < 0:
        raise ValueError("Invalid inherited usage accounting")
    checkpoints = {}
    for phase, checksum in record.checkpoint_hashes.items():
        if phase not in PHASES or file_digest(directory / f"{phase}.json") != checksum:
            raise ValueError("Changed or unsupported phase checkpoint")
        checkpoints[phase] = json.loads((directory / f"{phase}.json").read_text())
    for capability, call in record.completed_calls.items():
        validate_result(capability, call.result, record.request.process_name, record.sources)
    return record, checkpoints
