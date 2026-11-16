"""The installed design skills (.claude/skills/frontend-design, impeccable) are markdown only.

Khalid asked for the instruction files alone, pinned to a commit, with no scripts (Nov 15, 2026).
Agent 16's SEC-170: the skills' own text still tells the reader to run a launcher, a detector, a
hook, "doctor", "foundations" or `npx impeccable`, which would download and run unreviewed code as
Khalid. These tests check the folders hold only the approved files, that each file still matches the
SHA-256 recorded in its SOURCE.md, and that the guard refuses to run any of it.
"""

import hashlib
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"
DESIGN_SKILLS = ("frontend-design", "impeccable")
# Only text: no .mjs, .js, .cmd, .ps1, .sh, .exe, .json, and no scripts/ folder.
ALLOWED_SUFFIXES = {".md", ".txt", ""}


def _guard():
    spec = importlib.util.spec_from_file_location("dev_guard", ROOT / ".claude" / "hooks" / "dev_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("skill", DESIGN_SKILLS)
def test_the_skill_folder_holds_only_text(skill):
    folder = SKILLS / skill
    assert folder.is_dir(), f"{skill} is not installed"
    for path in folder.rglob("*"):
        if path.is_dir():
            assert path.name != "scripts", f"{path} is a scripts folder"
            continue
        assert path.suffix.lower() in ALLOWED_SUFFIXES, f"{path} is not a text file"


@pytest.mark.parametrize("skill", DESIGN_SKILLS)
def test_every_file_matches_the_hash_in_source_md(skill):
    """SOURCE.md records the pinned commit and a SHA-256 per file; nothing may drift (SEC-193)."""
    folder = SKILLS / skill
    source = (folder / "SOURCE.md").read_text(encoding="utf-8")
    assert re.search(r"Pinned commit: `[0-9a-f]{40}`", source), "SOURCE.md names no pinned commit"
    recorded = {m.group(1): m.group(2) for m in
                re.finditer(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|", source, re.M)}
    assert recorded, "SOURCE.md lists no file hashes"
    on_disk = {str(p.relative_to(folder)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in folder.rglob("*") if p.is_file() and p.name != "SOURCE.md"}
    assert set(on_disk) == set(recorded), "the folder and SOURCE.md list different files"
    for name, digest in recorded.items():
        assert on_disk[name] == digest, f"{skill}/{name} does not match its recorded SHA-256"


@pytest.mark.parametrize("skill", DESIGN_SKILLS)
def test_no_hidden_characters_in_the_skill_text(skill):
    """A skill file is read into a session, so no bidi, zero-width or control characters (SEC-193)."""
    bad = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁠-⁩﻿]")
    for path in (SKILLS / skill).rglob("*.md"):
        assert not bad.search(path.read_text(encoding="utf-8")), f"{path} holds hidden characters"


@pytest.mark.parametrize("command,powershell", [
    (r"npx impeccable install", False),
    (r"npx impeccable detect src/", False),
    (r"npx -y impeccable update", False),
    (r"npm exec impeccable", False),
    (r"pnpm dlx impeccable", False),
    (r"bunx impeccable context", False),
    (r".claude/skills/impeccable/scripts/impeccable context", False),
    (r'".claude\skills\impeccable\scripts\impeccable.cmd" foundations', False),
    (r"impeccable critique src/app", False),
    (r"node .claude/skills/impeccable/scripts/live-browser.js", False),
    (r"node .claude/skills/taste-skill/scripts/gate.mjs --hook claude", False),
    (r"node gate.mjs --start index.html", False),
    (r"npx typeui.sh pull premium && npx impeccable init", False),
    (r"& .claude\skills\impeccable\scripts\impeccable.cmd doctor", True),
    (r"Start-Process npx -ArgumentList 'impeccable','live'", True),
    # SEC-194 (Agent 16, second round): a version specifier, an option value or a .js name
    # must not walk around the block.
    (r"npx impeccable@latest", False),
    (r"npx impeccable@1.2.3 detect src/", False),
    (r"npm install impeccable@latest", False),
    (r"npx --package=impeccable -c 'impeccable context'", False),
    (r"npx -p impeccable impeccable live", False),
    (r"node impeccable.js", False),
    (r"npm exec -- impeccable@latest audit", False),
    (r"bunx taste-skill@2.5.1", False),
])
def test_guard_blocks_running_the_design_skills(command, powershell):
    assert "SEC-170" in (_guard().reason(command, powershell=powershell) or "")


@pytest.mark.parametrize("command", [
    r"cat .claude/skills/impeccable/SKILL.md",
    r"cat .claude/skills/impeccable/reference/craft-floor.md",
    r"cat .claude/skills/frontend-design/SKILL.md",
    r"grep -rn impeccable .claude/skills",
    r"ls .claude/skills/impeccable/reference",
    r"python3 scripts/dev.py test -q tests/test_design_skills_guard.py",
])
def test_guard_still_allows_reading_the_skill_text(command):
    assert _guard().reason(command) is None
