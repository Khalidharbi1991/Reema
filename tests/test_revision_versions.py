"""Version numbers on revised SOP file names (V2 -> V2.1, --major -> V3.0). No provider calls."""

import json
from pathlib import Path

import pytest

from src.utils.config import config_manager
from src.utils.documents import section_map
from src.utils.existing_sops import file_version, find_sops, is_revision_output, load_sop, next_revision_stem
from src.utils.existing_sops import instruction_findings
from tests.existing_sop_helpers import template_sop
from tests.test_sop_revise import NEW_ESCALATION, leader_with, patch_reply, recheck_reply

PROFILE = config_manager.document_profile


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "output_dir", tmp_path / "output")
    return tmp_path / "output"


@pytest.mark.parametrize("stem, expected", [
    ("SOP_User_Incident_Management_V2", ("SOP_User_Incident_Management", 2, 0)),
    ("SOP_User_Incident_Management_v2", ("SOP_User_Incident_Management", 2, 0)),
    ("SOP_User_Incident_Management_V2.1", ("SOP_User_Incident_Management", 2, 1)),
    ("SOP_User_Incident_Management_V2_1", ("SOP_User_Incident_Management", 2, 1)),
    ("ITG Access Management QP001 V0.9", ("ITG_Access_Management_QP001", 0, 9)),
    ("SOP_User_Incident_Management_V2_revised", ("SOP_User_Incident_Management", 2, 0)),
    ("SOP_User_Incident_Management_V2_revised_revised", ("SOP_User_Incident_Management", 2, 0)),
    ("incident", ("incident", 1, 0)),
    ("incident_revised", ("incident", 1, 0)),
    ("QP001_V0.8_PR", ("QP001_V0_8_PR", 1, 0)),  # A version in the middle is part of the name.
    ("Survey", ("Survey", 1, 0)),  # "v" inside a word is not a version.
])
def test_version_is_read_from_the_end_of_the_name(stem, expected):
    assert file_version(stem) == expected


def runs_with(root, *names):
    for i, name in enumerate(names):
        folder = root / "runs" / f"run{i}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text("x")


@pytest.mark.parametrize("source, existing, major, expected", [
    ("X_V2.md", [], False, "X_V2.1"),
    ("X_V2.3.md", [], False, "X_V2.4"),
    ("X_V0.9.docx", [], False, "X_V0.10"),
    ("X_V0.9.docx", [], True, "X_V1.0"),
    ("X_V2.3.md", [], True, "X_V3.0"),
    ("incident.md", [], False, "incident_V1.1"),
    ("incident.md", [], True, "incident_V2.0"),
    # Revising V2 again never reuses a number, whatever state those runs are in.
    ("X_V2.md", ["X_V2.1.md", "X_V2.1.docx", "X_V2.2.md"], False, "X_V2.3"),
    ("X_V2.1.md", ["X_V2.1.md", "X_V2.2.md"], False, "X_V2.3"),
    ("X_V2.md", ["X_V3.0.md"], True, "X_V4.0"),
    ("X_V2.md", ["X_V3.0.md"], False, "X_V2.1"),
    # Old "_revised" drafts count as the plain version only.
    ("X_V2_revised_revised.md", ["X_V2_revised.md", "X_V2_revised_revised.md"], False, "X_V2.1"),
    # Other SOPs and other file kinds do not count; names compare without case.
    ("X_V2.md", ["Y_V2.1.md", "X_V2.5.pdf", "x_v2.4.md", "changes.md"], False, "X_V2.5"),
])
def test_next_version(tmp_path, source, existing, major, expected):
    runs_with(tmp_path, *existing)
    assert next_revision_stem(tmp_path / "src" / source, tmp_path, major=major) == expected


def test_top_level_output_files_count_too(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "X_V2.1.docx").write_text("x")
    assert next_revision_stem("X_V2.docx", tmp_path) == "X_V2.2"


def test_revision_outputs_are_found_by_old_and_new_names(tmp_path):
    runs_with(tmp_path, "SOP_Incident_V2_revised.docx", "SOP_Incident_V2.1.md", "changes.md", "findings.md")
    assert is_revision_output("a/SOP_Incident_V2.1.docx") and is_revision_output("a/SOP_Incident_V2_revised.md")
    assert not is_revision_output("a/changes.md") and not is_revision_output("a/SOP_Incident_V2.1.pdf")
    names = {p.name for p in find_sops(tmp_path, {"incident"})}
    assert names == {"SOP_Incident_V2_revised.docx", "SOP_Incident_V2.1.md"}


async def revise(path, major=False):
    source = load_sop(path)
    findings = instruction_findings(source.content, PROFILE, "Add a 15 minute P1 escalation rule", ["sec-procedures"])
    leader, _, _ = leader_with(patch_reply(source.content, {"sec-procedures": NEW_ESCALATION}),
                               lambda *a, **k: recheck_reply(findings, "within 15 minutes"))
    outputs = await leader.revise_existing(source, findings, local_author=True, origin={"instruction": "x"},
                                           major=major)
    return Path(outputs["markdown"])


@pytest.mark.asyncio
async def test_revise_names_drafts_by_version_and_leaves_document_control(tmp_path, output_root):
    path = tmp_path / "SOP_User_Incident_Management_V2.md"
    path.write_text(template_sop())
    first = await revise(path)
    assert first.name == "SOP_User_Incident_Management_V2.1.md"
    state = json.loads((first.parent / "run.json").read_text())
    assert state["file_version"] == {"from": "V2", "to": "V2.1", "major": False, "document_control": "not updated"}
    changes = (first.parent / "changes.md").read_text()
    assert changes.startswith("File version: V2.1 (from V2). The version in Document Control")
    before, after = section_map(path.read_text(), PROFILE), section_map(first.read_text(), PROFILE)
    assert before["sec-control"]["sha256"] == after["sec-control"]["sha256"]
    # The same V2 again, then the V2.1 draft itself, then a major step.
    assert (await revise(path)).name == "SOP_User_Incident_Management_V2.2.md"
    assert (await revise(first)).name == "SOP_User_Incident_Management_V2.3.md"
    big = await revise(first, major=True)
    assert big.name == "SOP_User_Incident_Management_V3.0.md"
    assert json.loads((big.parent / "run.json").read_text())["file_version"]["major"] is True


@pytest.mark.asyncio
async def test_existing_legacy_drafts_are_not_renamed(tmp_path, output_root):
    legacy = output_root / "runs" / "old"
    legacy.mkdir(parents=True)
    (legacy / "SOP_X_V2_revised.md").write_text(template_sop())
    draft = await revise(legacy / "SOP_X_V2_revised.md")
    assert draft.name == "SOP_X_V2.1.md"
    assert [p.name for p in legacy.iterdir()] == ["SOP_X_V2_revised.md"]

