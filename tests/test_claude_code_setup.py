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
    "reema-reviser": READ_WRITE, "reema-rechecker": READ_WRITE, "reema-agent10-euc": READ_WRITE, "reema-agent12-requirements": READ_WRITE,
    "reema-agent13-architect": READ_WRITE, "reema-agent14-developer": SHELL, "reema-agent15-tester": SHELL,
    "reema-agent16-security": READ_WRITE, "reema-agent17-ui": READ_WRITE, "reema-agent18-game-writer": READ_WRITE,
    "reema-agent19-blueprint": READ_WRITE, "reema-agent20-space-planner": READ_WRITE,
    "reema-agent21-interior": READ_WRITE, "reema-agent22-3d-modeler": "Read, Write, PowerShell",
    "reema-agent23-design-reviewer": READ_WRITE,
}
HOME_AGENTS = {19: "reema-agent19-blueprint", 20: "reema-agent20-space-planner", 21: "reema-agent21-interior",
               22: "reema-agent22-3d-modeler", 23: "reema-agent23-design-reviewer"}
DESIGN_LEAD = CLAUDE / "skills" / "reema-agent9-design-lead" / "SKILL.md"
NEW_HOME = "D:/Projects/REEMA Projects/New Home"
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
    if "PowerShell" in meta["tools"]:
        assert path.stem == "reema-agent22-3d-modeler"


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
    row = next(line for line in chart.splitlines() if line.startswith("| Home Design |"))
    assert "`reema-agent9-design-lead`" in row and "| Working" in row
    assert all(f"`{name}`" in row for name in HOME_AGENTS.values())


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
    for matcher in ("Bash", "PowerShell", "Write|Edit|MultiEdit|NotebookEdit"):
        assert any(h["matcher"] == matcher and any(".claude/hooks/dev_guard.py" in c["command"] for c in h["hooks"])
                   for h in hooks)


def test_team_table_lists_twenty_five_roles_with_agents_9_and_11_to_23():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    team = text[text.index("## Current team"):text.index("## Documentation pipeline")]
    rows = [line for line in team.splitlines() if re.match(r"\| (Ahmad|Abdullah|Agent \d+) \|", line)]
    assert "There are twenty-five active agent roles." in team and len(rows) == 25
    assert "`reema-agent11-dev-lead`" in next(r for r in rows if r.startswith("| Agent 11 |"))
    assert "`reema-agent9-design-lead`" in next(r for r in rows if r.startswith("| Agent 9 |"))
    for number, name in {**DEV_AGENTS, **HOME_AGENTS}.items():
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
    blender = f'& "{_guard().AGENT22_PROGRAMS["blender"]}" -b --version'
    assert run({"tool_name": "PowerShell", "tool_input": {"command": blender}}).returncode == 2
    agent22 = run({"tool_name": "PowerShell", "agent_type": "reema-agent22-3d-modeler",
                   "tool_input": {"command": "git status"}})
    assert agent22.returncode == 2 and "Agent 22 may run only" in agent22.stderr
    ledger = run({"tool_name": "Write", "agent_type": "reema-agent16-security",
                  "tool_input": {"file_path": _guard().SCRIPT_LEDGER}})
    assert ledger.returncode == 2 and "only Ahmad" in ledger.stderr


@pytest.mark.parametrize("number,name", HOME_AGENTS.items(), ids=HOME_AGENTS.values())
def test_home_design_subagents_name_their_agent_and_keep_agent_9s_rules(number, name):
    meta, body = frontmatter(CLAUDE / "agents" / f"{name}.md")
    assert f"Agent {number}," in meta["description"] and body.startswith(f"You are Agent {number},")
    assert "reema-agent9-design-lead" in meta["description"]
    assert NEW_HOME in body and "references/" in body and "output/assistant/" in body
    for rule in ("Never invent dimensions", '"[to confirm]"', "licensed professional",
                 "Never upload, push, publish or send anything off this computer"):
        assert rule in body


def test_design_lead_skill_holds_khalids_rules():
    _, body = frontmatter(DESIGN_LEAD)
    flat = " ".join(body.split())
    assert "asking Khalid which part of the home to design" in flat
    assert "Never design the whole land" in flat and "Start only on Khalid's explicit yes" in flat
    assert "never upload them, never commit them to any remote" in flat
    assert all(name in body for name in HOME_AGENTS.values()) and "reema-agent16-security" in body
    assert "reviews/script_reviews.json" in flat and "No subagent may write that file" in flat
    assert "job-<short>-<YYYYMMDD>-start" in flat and "pre-<short>-<YYYYMMDD-HHMM>" in flat
    assert NEW_HOME in flat and "drawing summary" in flat
    assert not (CLAUDE / "agents" / "reema-agent9-design.md").exists()


def _home(tmp_path, monkeypatch, script="scripts/blender/majlis.py", approve=True):
    guard = _guard()
    home = tmp_path / "New Home"
    for folder in ("scripts/blender", "scripts/freecad", "models", "renders", "reviews", "input"):
        (home / folder).mkdir(parents=True)
    (home / script).write_text("import bpy\n", encoding="utf-8")
    (home / "reviews" / "SCRIPT_REVIEW_majlis.md").write_text("no findings\n", encoding="utf-8")
    import hashlib
    entries = [{"script": script, "sha256": hashlib.sha256((home / script).read_bytes()).hexdigest(),
                "review": "reviews/SCRIPT_REVIEW_majlis.md"}] if approve else []
    (home / "reviews" / "script_reviews.json").write_text(json.dumps({"approved": entries}), encoding="utf-8")
    monkeypatch.setattr(guard, "HOME_PROJECT", str(home))
    monkeypatch.setattr(guard, "SCRIPT_LEDGER", str(home / "reviews" / "script_reviews.json"))
    return guard, home


BLENDER_FLAGS = "-b --factory-startup --offline-mode --disable-autoexec"


def test_agent22_runs_reviewed_scripts_and_the_converter_inside_new_home(tmp_path, monkeypatch):
    guard, home = _home(tmp_path, monkeypatch)
    blender, oda = guard.AGENT22_PROGRAMS["blender"], guard.AGENT22_PROGRAMS["odafileconverter"]
    script = home / "scripts" / "blender" / "majlis.py"
    allowed = [
        f'& "{blender}" {BLENDER_FLAGS} --python "{script}"',
        f'& "{blender}" {BLENDER_FLAGS} "{home / "models" / "majlis.blend"}" -E CYCLES -t 8 '
        f'--python "{script}" --python-exit-code 1 -o "{home / "renders" / "majlis_####"}" -f 1 -- --samples 64',
        f'& "{oda}" "{home / "input"}" "{home / "input"}" ACAD2018 DXF 0 1 "*.dwg"',
    ]
    for command in allowed:
        assert guard.agent22_reason(command, "PowerShell") is None, command
    (home / "scripts" / "freecad" / "walls.py").write_text("import FreeCAD\n", encoding="utf-8")
    freecad = f'& "{guard.AGENT22_PROGRAMS["freecadcmd"]}" "{home / "scripts" / "freecad" / "walls.py"}"'
    assert "no Agent 16 review" in guard.agent22_reason(freecad, "PowerShell")


def test_agent22_is_refused_anything_else(tmp_path, monkeypatch):
    guard, home = _home(tmp_path, monkeypatch)
    blender, oda = guard.AGENT22_PROGRAMS["blender"], guard.AGENT22_PROGRAMS["odafileconverter"]
    script = home / "scripts" / "blender" / "majlis.py"
    refused = [
        "git status", "python -c print(1)", f'& "{blender}" {BLENDER_FLAGS} --python "{script}"; curl x',
        f'& "{blender}" {BLENDER_FLAGS} --python "{script}" | Out-File x', f"blender {BLENDER_FLAGS} --python {script}",
        f'& "{blender}" -b --python "{script}"',
        f'& "{blender}" {BLENDER_FLAGS} --python-expr "import os"',
        f'& "{blender}" {BLENDER_FLAGS} --enable-autoexec --python "{script}"',
        f'& "{blender}" {BLENDER_FLAGS} --python "C:\\Temp\\x.py"',
        f'& "{blender}" {BLENDER_FLAGS} --python "{home / "scripts" / "blender" / ".." / ".." / ".." / "x.py"}"',
        f'& "{blender}" {BLENDER_FLAGS} --python "{script}" -o "C:\\Temp\\out"',
        f'& "{blender}" {BLENDER_FLAGS} "C:\\Temp\\other.blend" --python "{script}"',
        f'& "{blender}" {BLENDER_FLAGS} --python "{script}" -- "C:\\Users\\Khali\\secret.txt"',
        f'& "{blender}" {BLENDER_FLAGS} --python "$env:TEMP\\x.py"',
        f'& "{oda}" "C:\\Drawings" "{home / "input"}" ACAD2018 DXF 0 1',
        f'& "{oda}" "{home / "input"}" "{home / "input"}" ACAD2018 PDF 0 1',
    ]
    for command in refused:
        assert guard.agent22_reason(command, "PowerShell"), command
    assert guard.agent22_reason(f'"{blender}" {BLENDER_FLAGS} --python "{script}"', "Bash")
    script.write_text("import bpy, socket\n", encoding="utf-8")
    assert "no Agent 16 review" in guard.agent22_reason(f'& "{blender}" {BLENDER_FLAGS} --python "{script}"',
                                                         "PowerShell")


@pytest.mark.parametrize("command", [
    "blender -b", "& 'C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe' --version",
    "Start-Process blender", "cmd /c freecadcmd.exe x.py", "powershell -Command ODAFileConverter in out",
    "env FREECAD=1 freecad",
])
def test_guard_blocks_the_home_programs_for_everyone_but_agent22(command):
    assert "only from Agent 22" in _guard().reason(command, powershell=True)


def test_guard_still_lets_ahmad_name_the_home_folders():
    for command in ("ls scripts/blender", "grep -rn blender src", "git -C 'D:/Projects/REEMA Projects/New Home' status"):
        assert _guard().reason(command) is None


def test_home_design_subagents_write_only_in_their_new_home_folders(tmp_path, monkeypatch):
    guard, home = _home(tmp_path, monkeypatch)
    write = guard.write_reason
    assert write({"file_path": str(home / "docs" / "majlis-blueprint.md")}, "reema-agent19-blueprint") is None
    assert write({"file_path": str(home / "scripts" / "blender" / "x.py")}, "reema-agent19-blueprint")
    assert write({"file_path": str(home / "scripts" / "blender" / "x.py")}, "reema-agent22-3d-modeler") is None
    assert write({"file_path": str(home / "reviews" / "SCRIPT_REVIEW_x.md")}, "reema-agent22-3d-modeler")
    assert write({"file_path": "D:/Projects/IT Consultant/src/main.py"}, "reema-agent22-3d-modeler")
    assert write({"file_path": str(home / "reviews" / "SCRIPT_REVIEW_x.md")}, "reema-agent16-security") is None
    assert write({"file_path": str(home / "reviews" / "script_reviews.json")}, "reema-agent16-security")
    assert write({"file_path": str(home / "reviews" / "script_reviews.json")}, None) is None
