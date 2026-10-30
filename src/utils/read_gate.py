"""Local gate before a Claude Code session reads a document; no model call.

A prepare step copies document text into output/claude_code/, where the session's subagents read it.
It refuses until it is given --confirm-read with the token printed for this exact file, which Ahmad
passes only after Khalid's yes. The token is the start of the file's SHA-256, so the yes covers those
bytes only. The gate makes the step deliberate and binds it to the file; it cannot prove who said yes.

A file under REFERENCES_DIR must also be listed in the reference manifest, allowed, not restricted and
unchanged (matching SHA-256), the same rule that governs reference excerpts. Reference excerpts for a
generate request have one token for the whole set of files they come from.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .config import CatalogLoader, config_manager

TOKEN_LENGTH = 12


class ReadNotConfirmed(ValueError):
    """prepare was run without the confirm-read token for this file."""


def read_token(sha256: str) -> str:
    return sha256[:TOKEN_LENGTH]


def check_manifest(path, sha256: str) -> bool:
    """Refuse a file under REFERENCES_DIR unless the manifest allows these exact bytes; True if it applied."""
    from ..knowledge.retrieval import Manifest
    settings = config_manager.system_config
    path, root = Path(path).resolve(), settings.references_dir.resolve()
    if not path.is_relative_to(root):
        return False
    if not settings.reference_manifest.exists():
        raise ValueError(f"{path.name} is in {root}, and there is no reference manifest that allows it")
    manifest = Manifest.model_validate(yaml.load(settings.reference_manifest.read_text(encoding="utf-8"), Loader=CatalogLoader))
    entry = next((s for s in manifest.sources if (root / s.path).resolve() == path), None)
    if entry is None:
        raise ValueError(f"{path.name} is not listed in the reference manifest")
    if entry.classification == "restricted" or not entry.external_ai_allowed:
        raise ValueError(f"The reference manifest does not allow {path.name} to be read by a model")
    if entry.sha256 != sha256:
        raise ValueError(f"{path.name} changed since the manifest allowed it; update its SHA-256 after review")
    return True


def require_read_permission(path, sha256: str, confirm_read) -> dict:
    """Both checks, before any text is copied; returns the record to keep in the request."""
    manifest = check_manifest(path, sha256)
    token = read_token(sha256)
    if confirm_read != token:
        raise ReadNotConfirmed(f"Claude Code may read {Path(path).name} only after Khalid's yes. Ask him; on his yes, "
                               f"run prepare again with --confirm-read {token}")
    return {"confirm_read": token, "confirmed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reference_manifest": manifest}


def references_sha256(records) -> str:
    """One SHA-256 over the reference files (manifest path and file SHA-256) behind a set of excerpts."""
    files = sorted({(record["source"], record["sha256"]) for record in records})
    return hashlib.sha256(json.dumps(files).encode("utf-8")).hexdigest()


def require_references_permission(records, confirm_read) -> dict:
    """The confirm-read gate for manifest-allowed reference excerpts; nothing to confirm when there are none.

    The manifest itself (allowed, not restricted, unchanged) is enforced by ReferenceIndex, which
    selected the excerpts. The token covers exactly these files at these SHA-256 values.
    """
    if not records:
        return {"confirm_read": None, "reference_files": []}
    names = sorted({record["source"] for record in records})
    token = read_token(references_sha256(records))
    if confirm_read != token:
        raise ReadNotConfirmed(f"Excerpts from {len(names)} reference file(s) would be read by Claude Code: "
                               f"{', '.join(names)}. Ask Khalid; on his yes, run prepare again with "
                               f"--confirm-read {token}")
    return {"confirm_read": token, "confirmed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reference_files": names}
