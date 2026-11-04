#!/usr/bin/env python3
"""PreToolUse guard for Bash and PowerShell in REEMA's Claude Code sessions (Development section, decision D3).

Blocks pushing, adding or changing remotes, publishing, deploying, sudo and network tools, also
when wrapped (sh -c, bash -c, eval, env, xargs, command substitution, powershell -Command, pwsh -c,
cmd /c, Invoke-Expression), and commands that name REEMA's output/assistant/ or REEMA's references/
through a path from outside the repository, written with either kind of slash.
Home Design section: Blender, FreeCAD and ODA File Converter run only from reema-agent22-3d-modeler
(the hook input's agent_type), one program per command by its installed path, with every path inside
the New Home project and each script's SHA-256 recorded as reviewed; Agent 22 runs nothing else, and
the home-design subagents write only inside their New Home folders.
Exit code 2 blocks the call and the message goes back to Claude. The prefix deny rules in
.claude/settings.json stay the first line; this catches wrapped forms they miss. It is not
airtight: a program can still open a connection itself.
"""

import hashlib
import json
import ntpath
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SINGLE = {"curl", "wget", "ssh", "scp", "sftp", "rsync", "nc", "ncat", "netcat", "telnet", "ftp",
          "sudo", "doas", "gh", "vercel", "netlify", "heroku", "flyctl"}
PAIRS = {("git", "push"), ("npm", "publish"), ("yarn", "publish"), ("pnpm", "publish"),
         ("twine", "upload"), ("uv", "publish"), ("poetry", "publish"), ("cargo", "publish"),
         ("gem", "push"), ("docker", "push"), ("podman", "push"), ("firebase", "deploy"),
         ("fly", "deploy")}
WRAPPERS = {"env", "command", "exec", "nohup", "time", "nice", "xargs", "builtin", "timeout", "caffeinate"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
PS_SHELLS = {"powershell", "pwsh", "cmd", "iex", "invoke-expression"}
OPERATORS = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")", "{", "}", "$"}
REDIRECTS = {">", ">>", "<", "<<", "<<<", ">&", "&>", "2>", "2>>"}
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
# Home Design section: only reema-agent22-3d-modeler runs these, by these installed paths (checked
# 2026-11-03), with every path inside the New Home project; they are blocked for everyone else.
AGENT22 = "reema-agent22-3d-modeler"
AGENT22_PROGRAMS = {
    "blender": r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
    "freecadcmd": r"C:\Users\Khali\AppData\Local\Programs\FreeCAD 1.1\bin\freecadcmd.exe",
    "odafileconverter": r"C:\Program Files\ODA\ODAFileConverter 27.10.0\ODAFileConverter.exe",
}
HOME_PROGRAMS = set(AGENT22_PROGRAMS) | {"freecad", "blender-launcher"}
LAUNCHERS = {"start-process", "saps", "start", "invoke-item", "ii"}
HOME_PROJECT = r"D:\Projects\REEMA Projects\New Home"
SCRIPT_LEDGER = HOME_PROJECT + r"\reviews\script_reviews.json"
# Every result goes in output\<folder>\, named <date>_<area>_<what>, e.g. 20261103_majlis_preview.png.
OUTPUT_FOLDERS = ("renders", "models", "drawings", "summaries", "reports")
OUTPUT_SUBFOLDERS = {"models": ("furniture",)}
RESULT_NAME = re.compile(r"(19|20)\d\d(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])_[a-z0-9]+(-[a-z0-9]+)*"
                         r"_[a-z0-9#][a-z0-9#_-]*(\.[a-z0-9]+)*", re.I)
REPORTS = r"output\reports"
HOME_AGENT_WRITES = {
    "reema-agent19-blueprint": (REPORTS,), "reema-agent20-space-planner": (REPORTS,),
    "reema-agent21-interior": (REPORTS,), "reema-agent23-design-reviewer": (REPORTS,),
    AGENT22: (r"scripts\blender", r"scripts\freecad", r"output\renders", r"output\models", r"output\drawings",
              REPORTS),
}
AHMAD_HOME_FILES = ("README.md", ".gitignore", r"output\README.md", r"reviews\script_reviews.json")
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
BLENDER_REQUIRED = {"--factory-startup", "--offline-mode", "--disable-autoexec"}
BLENDER_SWITCHES = BLENDER_REQUIRED | {"-b", "--background", "-noaudio", "-a", "--render-anim"}
NUMBER = re.compile(r"\d{1,5}")
BLENDER_VALUES = {
    "--python-exit-code": NUMBER, "-t": NUMBER, "--threads": NUMBER, "-f": NUMBER, "--render-frame": NUMBER,
    "-x": re.compile(r"[01]"), "--use-extension": re.compile(r"[01]"),
    "-E": re.compile(r"CYCLES|BLENDER_EEVEE_NEXT|BLENDER_EEVEE|BLENDER_WORKBENCH"),
    "--engine": re.compile(r"CYCLES|BLENDER_EEVEE_NEXT|BLENDER_EEVEE|BLENDER_WORKBENCH"),
    "-F": re.compile(r"PNG|JPEG|OPEN_EXR|TIFF"), "--render-format": re.compile(r"PNG|JPEG|OPEN_EXR|TIFF"),
}
ODA_VERSIONS = {"ACAD9", "ACAD10", "ACAD12", "ACAD13", "ACAD14", "ACAD2000", "ACAD2004", "ACAD2007",
                "ACAD2010", "ACAD2013", "ACAD2018"}
BLOCKED_WORDS = re.compile(r"\b(" + "|".join(sorted(SINGLE)) + r")\b|\bgit\s+push\b|\bremote\s+(add|set-url)\b"
                           r"|\b(npm|yarn|pnpm|uv|poetry|cargo)\s+publish\b|\btwine\s+upload\b")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _split_heredocs(command):
    """The command without heredoc bodies, and the bodies fed to a shell (those are checked as commands)."""
    lines, kept, shell_bodies, i = command.split("\n"), [], [], 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        for match in HEREDOC.finditer(line):
            body = []
            while i < len(lines) and lines[i].strip() != match.group(2):
                body.append(lines[i])
                i += 1
            i += 1
            fed_to = re.split(r"[;&|(]", line[:match.start()])[-1].split()
            piped_to = re.findall(r"\|\s*(?:\S*/)?(\w+)", line[match.end():])
            names = {Path(w).name for w in fed_to if "=" not in w and not w.startswith("-")} | set(piped_to)
            if names & (SHELLS | {"eval", "xargs"}):
                shell_bodies.append("\n".join(body))
    return "\n".join(kept), shell_bodies


def _name(word):
    """Command name from a / or \\ path, lower case and without .exe/.cmd/.bat/.com/.ps1 (Windows ignores both)."""
    return re.sub(r"\.(exe|cmd|bat|com|ps1)$", "", re.split(r"[\\/]", word)[-1].lower())


def _segments(command, powershell=False):
    if powershell:
        # In PowerShell ` escapes the next character or continues the line, and \ is literal.
        command = re.sub(r"`\r?\n", " ", command).replace("`", "")
    else:
        command = command.replace("`", " ; ")
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    if powershell:
        lexer.escape = ""
    segment = []
    for token in lexer:
        if token in OPERATORS or set(token) <= set(";&|()"):
            if segment:
                yield segment
            segment = []
        else:
            segment.append(token)
    if segment:
        yield segment


def _first_operand(words):
    for word in words:
        if not word.startswith("-"):
            return word
    return None


def _path_reason(word):
    word = word.replace("\\", "/").lower()
    root, name = ROOT.as_posix().lower(), ROOT.name.lower()
    if re.match(r"(\./)?output/assistant(/|$)", word) or f"{name}/output/assistant" in word \
            or word.startswith(f"{root}/output/assistant"):
        return "REEMA's output/assistant/ is used only through the task and memory commands"
    if f"{name}/references" in word or word.startswith(f"{root}/references"):
        return "REEMA's references/ cannot be reached from outside the repository"
    return None


def _after_options(words, depth):
    """powershell, pwsh, cmd and Invoke-Expression take their command after any options: check each tail."""
    for k, word in enumerate(words):
        if not re.fullmatch(r"[-/][A-Za-z]+", word) and (why := reason(" ".join(words[k:]), depth + 1, True)):
            return why
    return None


def _check(words, depth, powershell=False):
    words = [w for i, w in enumerate(words) if w not in REDIRECTS and (i == 0 or words[i - 1] not in REDIRECTS)]
    for word in words:
        if why := _path_reason(word):
            return why
        if "$(" in word and (why := reason(word[word.index("$(") + 2:].rstrip(")"), depth + 1, powershell)):
            return why
    i = 0
    while i < len(words):
        name = _name(words[i])
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[i]):
            i += 1
        elif name in WRAPPERS:
            i += 1
            while i < len(words) and (words[i].startswith("-") or words[i].isdigit()
                                      or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[i])
                                      or (name == "timeout" and re.fullmatch(r"[\d.]+[smhd]?", words[i]))):
                i += 1
        else:
            break
    if i >= len(words):
        return None
    name, rest = _name(words[i]), words[i + 1:]
    if name in HOME_PROGRAMS or any(_name(word) in HOME_PROGRAMS
                                    and (re.search(r"\.(exe|com|bat|cmd)$", word.lower())
                                         or _name(words[i + k]) in LAUNCHERS)
                                    for k, word in enumerate(rest)):
        return f"Blender, FreeCAD and ODA File Converter run only from Agent 22 ({AGENT22})"
    if name in SINGLE:
        return f"`{name}` is blocked (network, remote access or elevated rights)"
    if name in PS_SHELLS:
        return _after_options(rest, depth)
    if name in SHELLS or name == "eval":
        if name == "eval":
            inner = " ".join(rest)
        else:
            flags = [j for j, w in enumerate(rest) if re.fullmatch(r"-[a-z]*c[a-z]*", w)]
            inner = rest[flags[0] + 1] if flags and flags[0] + 1 < len(rest) else None
        return reason(inner, depth + 1) if inner else None
    if name == "git":
        j = 0
        while j < len(rest) and rest[j].startswith("-"):
            j += 2 if rest[j] in GIT_VALUE_OPTIONS else 1
        sub = rest[j:]
        if sub[:1] == ["push"]:
            return "`git push` is blocked: REEMA and its projects are local only"
        if sub[:1] == ["remote"] and _first_operand(sub[1:]) in {"add", "set-url"}:
            return "adding or changing a git remote is blocked"
        return None
    if name.startswith("python") and rest[:2] == ["-m", "twine"]:
        return "publishing packages is blocked"
    if (name, _first_operand(rest)) in PAIRS:
        return f"`{name} {_first_operand(rest)}` is blocked: nothing is published, pushed or deployed"
    return None


def reason(command, depth=0, powershell=False):
    """Why this Bash (or, with powershell=True, PowerShell) command is blocked, or None when it may run."""
    if depth > 5:
        return "command is nested too deeply to check"
    if not powershell:
        command, shell_bodies = _split_heredocs(command)
        for body in shell_bodies:
            if why := reason(body, depth + 1):
                return why
    try:
        segments = list(_segments(command, powershell))
    except ValueError:
        if BLOCKED_WORDS.search(command):
            return "command could not be parsed and names a blocked command"
        return None
    for words in segments:
        if found := _check(words, depth, powershell):
            return found
    return None


def _win(path):
    return ntpath.normcase(ntpath.normpath(str(path).replace("/", "\\")))


def _in_home(path, *folders):
    """True when path is absolute, on a drive, and inside New Home (or one of its folders)."""
    path, home = _win(path), _win(HOME_PROJECT)
    if not re.match(r"[a-z]:\\", path):
        return False
    return any(path.startswith(root + "\\") for root in [ntpath.join(home, f) for f in folders] or [home])


def _is_home_dir(path, folder):
    """True when path is New Home's folder itself (input, output\\drawings, ...)."""
    return re.match(r"[a-z]:\\", _win(path)) is not None and _win(path).rstrip("\\") == _win(ntpath.join(HOME_PROJECT, folder))


def _result_reason(path, *folders):
    """Why path is not a correctly named result in one of output\\<folders>, or None."""
    folders = folders or OUTPUT_FOLDERS
    parent, name = ntpath.split(_win(path))
    allowed = [ntpath.join("output", f, *sub) for f in folders for sub in [()] + [(s,) for s in OUTPUT_SUBFOLDERS.get(f, ())]]
    if not any(parent == _win(ntpath.join(HOME_PROJECT, folder)) for folder in allowed):
        return "results go directly in New Home\\" + " or ".join(f"{folder}\\" for folder in allowed)
    if not RESULT_NAME.fullmatch(name):
        return f"result names are <date>_<area>_<what>, for example 20261103_majlis_preview.png (got {name})"
    return None


def _approved(script, folder):
    """Why this script may not run, or None when its current SHA-256 is recorded as reviewed."""
    if not _in_home(script, ntpath.join("scripts", folder)) or not script.lower().endswith(".py"):
        return f"the script must be a .py file in New Home\\scripts\\{folder}\\"
    try:
        digest = hashlib.sha256(Path(script).read_bytes()).hexdigest()
        approved = json.loads(Path(SCRIPT_LEDGER).read_text(encoding="utf-8"))["approved"]
    except (OSError, ValueError, KeyError, TypeError):
        return "the script or reviews\\script_reviews.json could not be read"
    for entry in approved if isinstance(approved, list) else []:
        if (isinstance(entry, dict) and _win(ntpath.join(HOME_PROJECT, str(entry.get("script", "")))) == _win(script)
                and str(entry.get("sha256", "")).lower() == digest
                and _result_reason(ntpath.join(HOME_PROJECT, str(entry.get("review", ""))), "reports") is None
                and Path(HOME_PROJECT, str(entry.get("review", ""))).is_file()):
            return None
    return "this version of the script has no Agent 16 review recorded in reviews\\script_reviews.json"


def _pathlike(word):
    return "\\" in word or "/" in word or bool(re.match(r"[A-Za-z]:", word))


def _blender(args):
    scripts, switches, k = [], set(), 0
    while k < len(args) and args[k] != "--":
        word = args[k]
        if word in ("--python", "-P"):
            if k + 1 == len(args):
                return "--python needs a script"
            scripts.append(args[k + 1])
            k += 2
        elif word in ("-o", "--render-output"):
            if k + 1 == len(args):
                return "-o needs a render path"
            if why := _result_reason(args[k + 1], "renders"):
                return why
            k += 2
        elif word in BLENDER_VALUES:
            if k + 1 == len(args) or not BLENDER_VALUES[word].fullmatch(args[k + 1]):
                return f"`{word}` needs an allowed value"
            k += 2
        elif word in BLENDER_SWITCHES:
            switches.add(word)
            k += 1
        elif word.startswith("-"):
            return f"Blender option `{word}` is not allowed for Agent 22"
        elif not word.lower().endswith(".blend") or _result_reason(word, "models"):
            return "a .blend file must be a named result in New Home\\output\\models\\"
        else:
            k += 1
    if not switches & {"-b", "--background"} or not BLENDER_REQUIRED <= switches:
        return "Blender must run with -b --factory-startup --offline-mode --disable-autoexec"
    if len(scripts) != 1:
        return "Blender must run exactly one reviewed --python script"
    for word in args[k + 1:]:
        if _pathlike(word) and not _in_home(word, "input") and _result_reason(word):
            return "script arguments that are paths must be in New Home\\input\\ or named results in output\\"
    return _approved(scripts[0], "blender")


def _oda(args):
    if len(args) not in (6, 7) or not _is_home_dir(args[0], "input") \
            or not _is_home_dir(args[1], r"output\drawings"):
        return ("ODA File Converter takes: New Home\\input, New Home\\output\\drawings, version, type, "
                "recurse, audit, [filter]")
    if args[2] not in ODA_VERSIONS or args[3] not in {"DWG", "DXF", "DXB"} or args[4] not in ("0", "1") \
            or args[5] not in ("0", "1"):
        return "ODA File Converter needs an ACAD version, DWG/DXF/DXB, and 0 or 1 for recurse and audit"
    if len(args) == 7 and not re.fullmatch(r"[\w .*?-]+", args[6]):
        return "the ODA file filter must be a plain name or wildcard"
    return None


def agent22_reason(command, tool):
    """Why Agent 22 may not run this, or None: one allowed program, by its installed path, paths in New Home."""
    if tool != "PowerShell":
        return "Agent 22 runs its programs only through PowerShell"
    command = command.strip()
    if command.startswith("&"):
        command = command[1:].lstrip()
    if re.search(r"[;|&`<>$(){}@\r\n]", command):
        return "Agent 22 runs one program per command: no ;, |, &&, redirection, variables or subexpressions"
    lexer = shlex.shlex(command, posix=True)
    lexer.whitespace_split, lexer.escape = True, ""
    try:
        words = list(lexer)
    except ValueError:
        return "command could not be parsed"
    program = next((key for key, path in AGENT22_PROGRAMS.items() if words and _win(words[0]) == _win(path)), None)
    if program == "blender":
        return _blender(words[1:])
    if program == "freecadcmd":
        if len(words) != 2:
            return "FreeCAD runs exactly one reviewed script and no other arguments"
        return _approved(words[1], "freecad")
    if program == "odafileconverter":
        return _oda(words[1:])
    return "Agent 22 may run only Blender, FreeCAD (freecadcmd) and ODA File Converter, by their full installed paths"


def write_reason(tool_input, agent):
    """Why this write may not happen, or None. In New Home every result is a named file in output\\."""
    path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    if agent and _win(path) == _win(SCRIPT_LEDGER):
        return "only Ahmad records script approvals in reviews\\script_reviews.json"
    if agent in HOME_AGENT_WRITES:
        if not _in_home(path, *HOME_AGENT_WRITES[agent]):
            folders = ", ".join(f"New Home\\{f}\\" for f in HOME_AGENT_WRITES[agent])
            return f"{agent} writes only inside {folders}"
        if _in_home(path, "scripts"):
            return None if path.lower().endswith(".py") else "Agent 22's scripts are .py files"
        return _result_reason(path)
    if not _in_home(path):
        return None
    if agent:
        return _result_reason(path, "reports") and f"{agent} writes in New Home only named reports in output\\reports\\"
    if any(_win(path) == _win(ntpath.join(HOME_PROJECT, name)) for name in AHMAD_HOME_FILES):
        return None
    return _result_reason(path) and ("Ahmad writes in New Home only named results in output\\, the README files, "
                                     ".gitignore and reviews\\script_reviews.json")


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        print("dev_guard: unreadable hook input; blocked", file=sys.stderr)
        return 2
    tool, agent = event.get("tool_name"), event.get("agent_type")
    tool_input = event.get("tool_input") or {}
    if tool in WRITE_TOOLS:
        found = write_reason(tool_input, agent)
    elif tool not in ("Bash", "PowerShell"):
        return 0
    elif agent == AGENT22:
        found = agent22_reason(str(tool_input.get("command", "")), tool)
    else:
        found = reason(str(tool_input.get("command", "")), powershell=tool == "PowerShell")
    if found:
        print(f"Blocked by REEMA's guard (.claude/hooks/dev_guard.py): {found}. Ask Khalid to run it himself if it is really needed.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
