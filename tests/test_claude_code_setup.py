"""Claude Code company setup (.claude/ skills, subagents and settings) stays consistent. No provider calls."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / ".claude"
SKILLS = sorted((CLAUDE / "skills").glob("*/SKILL.md"))
AGENTS = sorted((CLAUDE / "agents").glob("*.md"))


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path} has no frontmatter"
    return dict(line.split(": ", 1) for line in match.group(1).splitlines()), text[match.end():]


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_names_match_folders_and_name_only_real_skills_and_subagents(path):
    meta, body = frontmatter(path)
    assert meta["name"] == path.parent.name and meta["description"]
    known = {p.parent.name for p in SKILLS} | {p.stem for p in AGENTS}
    assert set(re.findall(r"\breema-[a-z-]*[a-z]", body)) <= known


@pytest.mark.parametrize("path", AGENTS, ids=lambda p: p.stem)
def test_subagents_are_read_write_only(path):
    meta, _ = frontmatter(path)
    assert meta["name"] == path.stem and meta["description"] and meta["tools"] == "Read, Write"


def test_abdullah_routes_to_the_working_skills():
    assert {"abdullah-docs", "reema-review", "reema-revise"} <= {p.parent.name for p in SKILLS}


def test_revise_skill_offers_review_findings_mode():
    revise = (CLAUDE / "skills" / "reema-revise" / "SKILL.md").read_text(encoding="utf-8")
    docs = (CLAUDE / "skills" / "abdullah-docs" / "SKILL.md").read_text(encoding="utf-8")
    assert "--from-review" in revise and "--finding" in revise and "1-5" in revise
    assert "instruction path only" not in revise and "takes an instruction only" not in docs


def test_org_chart_members_exist():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    chart = text[text.index("### Org chart"):text.index("## Boundaries")]
    named = set(re.findall(r"`(reema-[a-z-]+)`", chart))
    assert named == {p.stem for p in AGENTS}
    assert "`abdullah-docs`" in chart


def test_settings_deny_approval_push_and_the_assistant_stores():
    deny = json.loads((CLAUDE / "settings.json").read_text())["permissions"]["deny"]
    assert {"Bash(reema approve:*)", "Bash(reema reject:*)", "Bash(reema publish:*)",
            "Bash(python3 scripts/dev.py run publish:*)", "Bash(git push:*)",
            "Read(./output/assistant/**)"} <= set(deny)
