"""Confirm-read gate and reference manifest before a Claude Code session reads a document. No provider calls."""

import hashlib
import importlib.util
from pathlib import Path

import pytest

from src.utils.config import config_manager
from src.utils.read_gate import ReadNotConfirmed, check_manifest, read_token, require_read_permission
from tests.existing_sop_helpers import confirm, template_sop

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "output_dir", tmp_path / "output")
    return tmp_path / "output"


@pytest.fixture
def references(tmp_path, monkeypatch):
    root = tmp_path / "references"
    root.mkdir()
    monkeypatch.setattr(config_manager.system_config, "references_dir", root)
    monkeypatch.setattr(config_manager.system_config, "reference_manifest", root / "manifest.yaml")
    return root


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(root, path, *, allowed=True, classification="internal", digest=None):
    (root / "manifest.yaml").write_text(
        f"version: 1\nsources:\n  - path: {path.name}\n    classification: {classification}\n"
        f"    external_ai_allowed: {str(allowed).lower()}\n    sha256: \"{digest or sha(path)}\"\n")


def test_token_is_bound_to_the_exact_bytes(tmp_path):
    path = tmp_path / "sop.md"
    path.write_text(template_sop())
    digest = sha(path)
    assert read_token(digest) == digest[:12] == confirm(path)
    for wrong in (None, "", digest[:11], read_token("0" * 64)):
        with pytest.raises(ReadNotConfirmed, match=f"--confirm-read {digest[:12]}"):
            require_read_permission(path, digest, wrong)
    record = require_read_permission(path, digest, digest[:12])
    assert record["confirm_read"] == digest[:12] and record["reference_manifest"] is False


@pytest.mark.parametrize("name, args", [
    ("claude_code_review", ()),
    ("claude_code_revise", (["Tools & Systems"], "Name the current tool version")),
])
def test_prepare_copies_nothing_without_the_token(tmp_path, output_root, capsys, name, args):
    module = script(name)
    path = tmp_path / "sop.md"
    path.write_text(template_sop())
    assert module.main(["prepare", str(path), *(["--section", args[0][0], "--instruction", args[1]] if args else [])]) == 1
    assert f"--confirm-read {confirm(path)}" in capsys.readouterr().err
    assert not (output_root / "claude_code").exists()
    work_id = module.prepare(path, *args, confirm_read=confirm(path))
    request = next((output_root / "claude_code" / work_id).glob("*request.json")).read_text()
    assert f'"confirm_read": "{confirm(path)}"' in request
    path.write_text(template_sop() + "\nEdited.\n")
    with pytest.raises(ReadNotConfirmed):
        module.prepare(path, *args, confirm_read=read_token(sha(path))[:-1] + "x")


def test_files_outside_references_need_no_manifest(tmp_path, references):
    path = tmp_path / "sop.md"
    path.write_text(template_sop())
    assert check_manifest(path, sha(path)) is False


def test_reference_files_need_an_allowing_manifest_entry(references):
    path = references / "policy.md"
    path.write_text(template_sop())
    with pytest.raises(ValueError, match="no reference manifest"):
        check_manifest(path, sha(path))
    (references / "manifest.yaml").write_text("version: 1\nsources: []\n")
    with pytest.raises(ValueError, match="not listed"):
        check_manifest(path, sha(path))
    manifest(references, path, allowed=False)
    with pytest.raises(ValueError, match="does not allow"):
        check_manifest(path, sha(path))
    manifest(references, path, classification="restricted")
    with pytest.raises(ValueError, match="does not allow"):
        check_manifest(path, sha(path))
    manifest(references, path, digest="0" * 64)
    with pytest.raises(ValueError, match="changed since the manifest"):
        check_manifest(path, sha(path))
    manifest(references, path)
    assert check_manifest(path, sha(path)) is True
    # The manifest is checked before the token, so a token alone never opens a reference.
    manifest(references, path, allowed=False)
    with pytest.raises(ValueError, match="does not allow"):
        require_read_permission(path, sha(path), confirm(path))
