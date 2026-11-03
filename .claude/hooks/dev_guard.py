#!/usr/bin/env python3
"""PreToolUse guard for Bash and PowerShell in REEMA's Claude Code sessions (Development section, decision D3).

Blocks pushing, adding or changing remotes, publishing, deploying, sudo and network tools, also
when wrapped (sh -c, bash -c, eval, env, xargs, command substitution, powershell -Command, pwsh -c,
cmd /c, Invoke-Expression), and commands that name REEMA's output/assistant/ or REEMA's references/
through a path from outside the repository, written with either kind of slash.
Exit code 2 blocks the call and the message goes back to Claude. The prefix deny rules in
.claude/settings.json stay the first line; this catches wrapped forms they miss. It is not
airtight: a program can still open a connection itself.
"""

import json
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


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        print("dev_guard: unreadable hook input; blocked", file=sys.stderr)
        return 2
    tool = event.get("tool_name")
    if tool not in ("Bash", "PowerShell"):
        return 0
    found = reason(str((event.get("tool_input") or {}).get("command", "")), powershell=tool == "PowerShell")
    if found:
        print(f"Blocked by REEMA's guard (.claude/hooks/dev_guard.py): {found}. Ask Khalid to run it himself if it is really needed.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
