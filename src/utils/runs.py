"""Local, checksum-verified checkpoints. Not an authenticated audit ledger."""

import hashlib
import json
import os
from uuid import uuid4
from pathlib import Path
from .approvals import timestamp
from .ownership import RunLease


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        if os.name != "nt":
            fd = os.open(path.parent, os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


class RunStore:
    def __init__(self, directory, process_name, formats):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.lease = RunLease(self.directory).__enter__()
        self.state = {"schema_version": 1, "process_name": process_name, "formats": formats,
                      "created_at": timestamp(), "status": "running", "checkpoints": {}, "owner": self.lease.owner}
        self.flush()

    def close(self):
        self.lease.close()

    def flush(self):
        self.state["updated_at"] = timestamp()
        atomic_json(self.directory / "run.json", self.state)

    def save(self, phase, payload):
        if phase not in {"planned", "researched", "generated", "drafted", "reviewed", "ready", "exported",
                         "source", "findings", "revised"}:
            raise ValueError("Unknown checkpoint phase")
        path = self.directory / f"{phase}.json"
        atomic_json(path, payload)
        self.state["checkpoints"][phase] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.state["phase"] = phase
        self.flush()

    def finish(self, status, error_type=None):
        self.state["status"] = status
        if error_type:
            self.state["error_type"] = error_type
        try: self.flush()
        finally: self.close()


def load_ready(directory, *, lease=None):
    directory = Path(directory).resolve()
    if lease is None:
        with RunLease(directory) as held:
            return load_ready(directory, lease=held)
    lease.permits(directory)
    state = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    path = directory / "ready.json"
    if state.get("schema_version") != 1 or hashlib.sha256(path.read_bytes()).hexdigest() != state.get("checkpoints", {}).get("ready"):
        raise ValueError("Missing, unsupported, or changed ready checkpoint")
    payload = json.loads(path.read_text(encoding="utf-8"))
    # A Claude Code generate run has no model review; every other ready checkpoint carries one.
    unreviewed = payload.get("review") is None and state.get("authoring") == "claude_code_session"
    if not isinstance(payload.get("content"), str) or not (isinstance(payload.get("review"), dict) or unreviewed):
        raise ValueError("Invalid ready checkpoint")
    return state, payload
