"""Claude Code company setup (.claude/ skills, subagents and settings) stays consistent. No provider calls."""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / ".claude"
SKILLS = sorted((CLAUDE / "skills").glob("*/SKILL.md"))
AGENTS = sorted((CLAUDE / "agents").glob("*.md"))
READ_WRITE = "Read, Write"
SHELL = "Read, Write, Edit, Glob, Grep, Bash"
TOOLS = {
    "reema-writer": READ_WRITE, "reema-reviewer": READ_WRITE, "reema-consistency-reviewer": READ_WRITE,
    "reema-reviser": READ_WRITE, "reema-rechecker": READ_WRITE, "reema-agent9-design": READ_WRITE,
    "reema-agent10-euc": READ_WRITE, "reema-agent12-requirements": READ_WRITE,
    "reema-agent13-architect": READ_WRITE, "reema-agent14-developer": SHELL, "reema-agent15-tester": SHELL,
    "reema-agent16-security": READ_WRITE, "reema-agent17-ui": READ_WRITE, "reema-agent18-game-writer": READ_WRITE,
}
DEV_AGENTS = {12: "reema-agent12-requirements", 13: "reema-agent13-architect", 14: "reema-agent14-developer",
              15: "reema-agent15-tester", 16: "reema-agent16-security", 17: "reema-agent17-ui",
              18: "reema-agent18-game-writer"}
DEV_LEAD = CLAUDE / "skills" / "reema-agent11-dev-lead" / "SKILL.md"
PROJECTS = "D:/Projects/REEMA Projects"


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
    assert set(re.findall(r"\breema-[a-z0-9-]*[a-z0-9]", body)) <= known


def test_every_subagent_has_a_tool_list():
    assert {p.stem for p in AGENTS} == set(TOOLS)


@pytest.mark.parametrize("path", AGENTS, ids=lambda p: p.stem)
def test_subagents_have_exactly_their_listed_tools(path):
    meta, _ = frontmatter(path)
    assert meta["name"] == path.stem and meta["description"] and meta["tools"] == TOOLS[path.stem]
    if "Bash" in meta["tools"]:
        assert path.stem in {"reema-agent14-developer", "reema-agent15-tester"}


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
    named = set(re.findall(r"`(reema-[a-z0-9-]+)`", chart))
    assert named - {p.parent.name for p in SKILLS} == {p.stem for p in AGENTS}
    assert "`abdullah-docs`" in chart
    row = next(line for line in chart.splitlines() if line.startswith("| Development |"))
    assert "`reema-agent11-dev-lead`" in row and "| Working" in row
    assert all(f"`{name}`" in row for name in DEV_AGENTS.values())


def test_settings_deny_approval_push_and_the_assistant_stores():
    deny = json.loads((CLAUDE / "settings.json").read_text())["permissions"]["deny"]
    assert {"Bash(reema approve:*)", "Bash(reema reject:*)", "Bash(reema publish:*)",
            "Bash(python3 scripts/dev.py run publish:*)", "Bash(git push:*)",
            "Read(./output/assistant/**)"} <= set(deny)


def test_settings_deny_remotes_publishing_deploys_network_and_protected_folders():
    deny = set(json.loads((CLAUDE / "settings.json").read_text())["permissions"]["deny"])
    assert {"Bash(git remote add:*)", "Bash(git remote set-url:*)", "Bash(gh:*)", "Bash(npm publish:*)",
            "Bash(twine upload:*)", "Bash(uv publish:*)", "Bash(docker push:*)", "Bash(vercel:*)",
            "Bash(netlify:*)", "Bash(firebase deploy:*)", "Bash(sudo:*)", "Bash(curl:*)", "Bash(wget:*)",
            "Bash(ssh:*)", "Bash(scp:*)", "Bash(rsync:*)", "Bash(nc:*)",
            "Read(./references/**)", "Edit(./references/**)", "Write(./references/**)",
            "Edit(./output/assistant/**)", "Write(./output/assistant/**)"} <= deny
    assert not any(re.match(r"Bash\((pip|npm|uv|yarn|pnpm) (install|add)", rule) for rule in deny)


def test_settings_add_the_projects_folder_and_the_bash_guard_hook():
    settings = json.loads((CLAUDE / "settings.json").read_text())
    assert settings["permissions"]["additionalDirectories"] == [PROJECTS]
    hooks = settings["hooks"]["PreToolUse"]
    assert any(h["matcher"] == "Bash" and any(".claude/hooks/dev_guard.py" in c["command"] for c in h["hooks"])
               for h in hooks)


def test_team_table_lists_twenty_roles_with_agents_11_to_18():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    team = text[text.index("## Current team"):text.index("## Documentation pipeline")]
    rows = [line for line in team.splitlines() if re.match(r"\| (Ahmad|Abdullah|Agent \d+) \|", line)]
    assert "There are twenty active agent roles." in team and len(rows) == 20
    assert "`reema-agent11-dev-lead`" in next(r for r in rows if r.startswith("| Agent 11 |"))
    for number, name in DEV_AGENTS.items():
        assert f"`{name}`" in next(r for r in rows if r.startswith(f"| Agent {number} |"))


@pytest.mark.parametrize("number,name", DEV_AGENTS.items(), ids=DEV_AGENTS.values())
def test_development_subagents_name_their_agent_and_boundaries(number, name):
    meta, body = frontmatter(CLAUDE / "agents" / f"{name}.md")
    assert f"Agent {number}," in meta["description"] and body.startswith(f"You are Agent {number},")
    assert "reema-agent11-dev-lead" in meta["description"]
    assert PROJECTS in body and "references/" in body and "output/assistant/" in body
    assert "Never push, add a remote, deploy, publish" in body


def test_dev_lead_skill_holds_khalids_rules():
    _, body = frontmatter(DEV_LEAD)
    flat = " ".join(body.split())
    assert "| Small fix |" in body and "| 14, 15 |" in body
    assert "| 12 (short PRD), 14, 15, 16 |" in body
    assert "| 12, 13, 17, 14, 15, 16 |" in body
    assert "| 12, 18, 13, 17, 14, 15, 16 |" in body
    assert all(name in body for name in DEV_AGENTS.values())
    assert "Start only on Khalid's explicit yes" in flat and "Never skip Khalid" in flat
    assert "every package to be installed" in flat
    assert "Agent 12 writes `docs/PRD.md` before any code" in flat
    assert "one git repo per project" in flat and PROJECTS in flat
    assert "job-<short>-<YYYYMMDD>-start" in flat and "job-<short>-<YYYYMMDD>-done" in flat
    assert "Before every risky change" in flat and "pre-<short>-<YYYYMMDD-HHMM>" in flat
    assert "no open Critical or High finding" in flat and "No online scanner" in flat
    assert "Push, add or change a remote, deploy, or publish" in flat
    assert "`references/`" in flat and "`output/assistant/`" in flat


def _guard():
    spec = importlib.util.spec_from_file_location("dev_guard", CLAUDE / "hooks" / "dev_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("command", [
    "git push", "git -C proj push origin main", "cd proj && git push", "sh -c 'git push'",
    "bash -lc \"curl https://example.com\"", "echo $(curl x)", "echo \"$(curl x)\"", "echo `wget x`",
    "FOO=1 env curl x", "xargs -n 1 curl < urls", "/usr/bin/curl x", "eval 'ssh host'", "timeout 5 wget x",
    "git remote add origin url", "git remote set-url origin url", "npm publish", "uv publish",
    "python3 -m twine upload dist/*", "docker push image", "vercel deploy", "sudo ls", "gh pr create",
    "rsync -a . host:", "cat output/assistant/work.db", "bash <<EOF\ngit push\nEOF",
    "cat <<'EOF' | sh\ncurl x\nEOF", "echo 'unbalanced curl x",
    f"ls '{PROJECTS}/../IT Consultant/references'",
])
def test_guard_blocks_push_remotes_publish_deploy_network_and_protected_paths(command):
    assert _guard().reason(command)


@pytest.mark.parametrize("command", [
    "python3 scripts/dev.py test -q -rs", "git status", "git log --oneline", "git remote -v",
    "git tag -a pre-x-20261101-1200 -m why", "pytest -q", "npm install react@18.3.1",
    "pip install requests==2.32.3", "grep -rn curl src", "python3 scripts/dev.py run find-sop incident",
    "python3 - <<'EOF'\nprint(\"Khalid's note: no curl, no npm publish\")\nEOF",
    "git commit -F - <<'EOF'\nDocument Khalid's rule: never git push or publish\nEOF",
])
def test_guard_allows_local_work_and_package_installs(command):
    assert _guard().reason(command) is None


def test_guard_hook_exit_codes():
    script = str(CLAUDE / "hooks" / "dev_guard.py")
    def run(event):
        return subprocess.run([sys.executable, "-I", script], input=json.dumps(event), capture_output=True, text=True)
    blocked = run({"tool_name": "Bash", "tool_input": {"command": "sh -c 'git push'"}})
    assert blocked.returncode == 2 and "git push" in blocked.stderr
    assert run({"tool_name": "Bash", "tool_input": {"command": "git status"}}).returncode == 0
    assert run({"tool_name": "Read", "tool_input": {"file_path": "x"}}).returncode == 0
