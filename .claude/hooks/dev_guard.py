#!/usr/bin/env python3
"""PreToolUse guard for Bash and PowerShell in REEMA's Claude Code sessions (Development section, decision D3).

Blocks pushing (Khalid pushes main himself; a session-run push was not adopted, SEC-97/98), adding or
changing remotes, changing git config, `git credential` and credential helpers, any path through a
.git folder, shell and PowerShell profiles, persistent environment variables (setx), publishing,
deploying, sudo and network tools, also
when wrapped (sh -c, bash -c, eval, env, xargs, command substitution, powershell -Command, pwsh -c,
cmd /c, Invoke-Expression), and commands that name REEMA's task store (teams/coordination/data/,
formerly output/assistant/) or REEMA's references (teams/documentation/input/references/, formerly
references/) through a path from outside the repository, written with either kind of slash.
Home Design section: Blender, FreeCAD and ODA File Converter run only from reema-agent22-3d-modeler
(the hook input's agent_type), one program per command by its installed path, with every path inside
the New Home project (teams/home-design/New Home/) and each script's SHA-256 recorded as reviewed; Agent 22 runs nothing else, and
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
# Settings that could redirect or widen a push: where it goes (remote.*, url.*.pushInsteadOf), what
# it sends (push.*, remote.*.mirror, branch.*) or config pulled in from elsewhere (include*).
GIT_CONFIG_KEYS = re.compile(r"(remote|push|branch|url|include|includeif)\.", re.I)
GIT_CONFIG_FILES = re.compile(r"(^|[\s'\"/])\.git/config\b|\.gitconfig\b|/etc/gitconfig\b")
# SEC-90 / SEC-91: any path through a .git folder (written with either slash, or `cd .git`), so its
# config, hooks and commondir are changed only by git itself. ".gitignore" and ".github" are not ".git".
# These blocks stay as a backstop although the push stays manual (Khalid, Nov 14, 2026).
GIT_FOLDER = re.compile(r"(^|[\s'\"=/:;&|(<>,])\.git([/\s'\";&|)<>,]|$)", re.I)
# SEC-92: start-up files that could set environment variables, aliases or a `git` function.
PROFILE_NAME = r"\.(bashrc|bash_profile|bash_login|profile|zshrc|zshenv|zprofile)\b|profile\.ps1\b"
PROFILES = re.compile(PROFILE_NAME + r"|\$profile\b", re.I)
# SEC-102: git's lower-level commands that push without the word "push".
GIT_PUSH_PLUMBING = {"send-pack", "http-push", "remote-http", "remote-https", "remote-ext", "remote-fd",
                     "receive-pack"}
# SEC-102: variables git, Git Credential Manager, curl or the shell read to change where git connects,
# which credential it uses, or to print secrets (GIT_TRACE*, GCM_TRACE*). Setting one is blocked in
# every form: in front of a command, through env, export, declare/typeset -x, cmd's set, or
# PowerShell's $env:NAME / env:NAME. A few that only change the editor, pager or prompts may be set.
RISKY_NAME = (r"GIT_\w+|GCM_\w+|\w*_PROXY|SSL_CERT_(?:FILE|DIR)|CURL_CA_BUNDLE|REQUESTS_CA_BUNDLE|BASH_ENV|ENV"
              r"|SSH_ASKPASS|LD_PRELOAD")
RISKY_SETTERS = (
    # NAME=value or NAME+=value anywhere (in front of a command, after env/export/declare -x/set)
    re.compile(r"(?<![\w$.:])(?P<name>" + RISKY_NAME + r")\s*\+?=", re.I),
    # PowerShell's environment drive in any form ($env:NAME = ..., Set-Item env:NAME, New-Item env:\NAME)
    re.compile(r"\benv:[\\/]?(?P<name>" + RISKY_NAME + r")\b", re.I),
    # bash builtins that assign without "=": printf -v NAME, read NAME, export NAME (after unset tricks)
    re.compile(r"\bprintf\s+-v\s+['\"]?(?P<name>" + RISKY_NAME + r")\b", re.I),
    re.compile(r"\b(?:read|export|declare|typeset|local|readonly)\b[^;&|\n]*?(?<![\w$.])(?P<name>" + RISKY_NAME
               + r")\b", re.I),
)
HARMLESS_ENV = {"GIT_EDITOR", "GIT_PAGER", "GIT_TERMINAL_PROMPT", "NO_PROXY"}
PERSISTENT_ENV = re.compile(r"\bsetx\b|setenvironmentvariable|hkcu:?/+environment|hkey_current_user/+environment"
                            r"|currentversion/+policies/+system|session manager/+environment", re.I)
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
HOME_PROJECT = str(ROOT / "teams" / "home-design" / "New Home")
# The current folders first, then the folders they were moved from on 2026-11-07.
TASK_STORES = ("teams/coordination/data", "output/assistant")
REFERENCE_DIRS = ("teams/documentation/input/references", "references")
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
AHMAD_HOME_FILES = ("README.md", ".gitignore", r".claude\settings.json", r"output\README.md",
                    r"reviews\script_reviews.json")
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
# SEC-170: the design skills in .claude/skills/ (frontend-design, impeccable) are installed as
# markdown only, with no scripts. Their own text still tells the reader to run a launcher, a
# detector, a hook, "doctor", "foundations" or `npx impeccable`, which would download and run
# unreviewed code as Khalid. No session runs them; reading the markdown stays allowed.
DESIGN_SKILL_PROGRAMS = {"impeccable", "taste-skill"}
DESIGN_SKILL_RUNNERS = {"npx", "bunx", "pnpx", "node", "bun", "deno", "npm", "pnpm", "yarn"} | LAUNCHERS
DESIGN_SKILL_SCRIPT = re.compile(r"[\\/]skills[\\/](impeccable|taste-skill|frontend-design)[\\/]scripts[\\/]"
                                 r"|(^|[\\/])gate\.mjs$", re.I)
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


# Snafi (SEC-14): the worker's secrets (Windows Credential Manager, "REEMA-Snafi:<NAME>"), its
# folder under %APPDATA%\REEMA\, Khalid's daily Snafi backups, and running the worker itself
# (it would use Khalid's real keys and make paid calls). No session or agent may do any of these.
# Matched on the whole command, lower-cased, with backslashes as slashes, so quoting, Join-Path,
# environment variables and wildcards do not get around it. A backstop, not a full guarantee.
SNAFI_PRIVATE = (
    (r"appdata.*reema|reema.*appdata|appdata[^\s'\"]*[*?\[]", "the worker's folder under %APPDATA%\\REEMA\\"),
    (r"reema-snafi|snafi_worker[./]secret_store|snafi_worker[./]set_secrets|secret_store|set_secrets"
     r"|google_refresh_token|google_client_secret|yahoo_app_password|todoist_api_token"
     # Step 5 (SEC-128): the Web Push private key.
     r"|snafi_vapid_private_key",
     "the worker's secrets in Credential Manager"),
    # Step 3: connecting, checking or cancelling Khalid's Google connection is his alone (it signs in
    # as him and stores or reads his refresh token).
    (r"connect-google|google[./]connect\b|-m\s+['\"]?src\.snafi_worker\.google",
     "Khalid's Google connection (connect-google)"),
    # SEC-79: importing the worker's secret loading or Google code from a one-liner or script would
    # hand a session Khalid's live Gmail, Calendar and Drive token outside the gate.
    # Step 4: the same for Yahoo (IMAP and SMTP with the app password) and Todoist (the API token).
    (r"snafi_worker[./](config|services|google|secret_store|set_secrets|yahoo|todoist|personal[./]credentials)\b"
     r"|secrets\.load|googleauth|storedlogin"
     r"|build_personal|windowscredentials|oauth2\.googleapis\.com/token"
     r"|imap\.mail\.yahoo\.com|smtp\.mail\.yahoo\.com|api\.todoist\.com",
     "the worker's secrets, Google, Yahoo and Todoist connections (loading them outside the worker)"),
    (r"\bcmdkey\b|credread|credwrite|credenumerate|creddelete|vaultcmd|passwordvault|storedcredential"
     r"|credentialmanager|security\.credentials|win32cred|\bkeyring\b",
     "Windows Credential Manager"),
    (r"snafi[-_ .]*back|coordination/[^\s'\"]*[*?\[]|coordination/\.\.|/\*/snafi|coordination.*snafi|snafi.*coordination",
     "Khalid's Snafi backups (teams/coordination/snafi-backups/)"),
    (r"(-m|-c)\s+['\"]?src\.snafi_worker|src/snafi_worker/(__main__|restore|install_task)"
     r"|snafi_worker/deploy/|snafi\.cmd|snafi\.py\b",
     "running the Snafi worker, its restore, its deploy or its task setup (Khalid runs these himself)"),
    (r"c:/snafiworker|users/(snafi-)?worker(/|\b)|\brunas\b|(snafi-)?worker[^\s]*/(appdata|\.gemini)",
     "the worker Windows user's folders and the worker's copy in C:\\SnafiWorker"),
)


AGY_PROGRAM = re.compile(r"^(?:&\s*)?['\"]?(?:[^\s'\"]*/)?agy(?:\.exe)?['\"]?$")


def _runs_agy(text):
    """A command segment that starts the agy program (it would use Khalid's own Google sign-in)."""
    for segment in re.split(r"[;&|\n]+|\$\(|`", text):
        words = segment.strip().split()
        if words and words[0] in ("&", "call", "start", "exec"):
            words = words[1:]
        if words and AGY_PROGRAM.match(words[0]):
            return True
    return False


def _snafi_reason(command):
    text = command.replace("\\", "/").lower()
    for pattern, what in SNAFI_PRIVATE:
        if re.search(pattern, text):
            return f"Snafi: {what} is never touched by a Claude Code session or agent"
    if _runs_agy(text):
        return "Snafi: running agy (the Antigravity CLI) from a Claude Code session or agent is not allowed"
    return None


def _path_reason(word):
    word = word.replace("\\", "/").lower()
    root, name = ROOT.as_posix().lower(), ROOT.name.lower()
    for store in TASK_STORES:
        if re.match(rf"(\./)?{re.escape(store)}(/|$)", word) or f"{name}/{store}" in word \
                or word.startswith(f"{root}/{store}"):
            return "REEMA's task store (teams/coordination/data/) is used only through the task and memory commands"
    for refs in REFERENCE_DIRS:
        if f"{name}/{refs}" in word or word.startswith(f"{root}/{refs}"):
            return "REEMA's references (teams/documentation/input/references/) cannot be reached from outside the repository"
    return None


def _after_options(words, depth):
    """powershell, pwsh, cmd and Invoke-Expression take their command after any options: check each tail."""
    for k, word in enumerate(words):
        if not re.fullmatch(r"[-/][A-Za-z]+", word) and (why := reason(" ".join(words[k:]), depth + 1, True)):
            return why
    return None


GIT_CONFIG_READS = {"--get", "--get-all", "--get-regexp", "--list", "-l", "get", "list"}
GIT_CONFIG_WRITES = {"--add", "--unset", "--unset-all", "--replace-all", "--rename-section", "--remove-section",
                     "--edit", "-e", "set", "unset", "rename-section", "remove-section", "edit"}


def _git_config_read(args):
    """True only for a read of git config (--get, --list, ...), never a change."""
    lowered = {a.lower().split("=", 1)[0] for a in args}
    if lowered & GIT_CONFIG_WRITES:
        return False
    positional = [a for a in args if not a.startswith("-")]
    return bool(lowered & GIT_CONFIG_READS) or len(positional) == 1  # `git config user.name` reads


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
    if (name in DESIGN_SKILL_PROGRAMS
            or (name in DESIGN_SKILL_RUNNERS
                and any(_name(piece) in DESIGN_SKILL_PROGRAMS for word in rest if not word.startswith("-")
                        for piece in re.split(r"[,;'\"]+", word)))
            or any(DESIGN_SKILL_SCRIPT.search(word) for word in words[i:])):
        return ("the design skills are markdown only: their launcher, detector, hooks, live mode and "
                "`npx impeccable` are never run (SEC-170). Reading their markdown is allowed.")
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
        if any(re.match(r"-c|--config-env|--config\b", word) for word in rest[:j]):
            return ("one-off git settings (`git -c`, `--config-env`) are blocked on every git command: they "
                    "could hand out Khalid's GitHub sign-in or push without saying push (SEC-102)")
        if sub[:1] == ["push"]:
            return "`git push` is blocked: Khalid pushes main himself, from his own terminal"
        if sub[:1] and sub[0].lower() in GIT_PUSH_PLUMBING:
            return f"`git {sub[0]}` is blocked: it pushes to a remote (SEC-102)"
        if sub[:1] == ["remote"] and _first_operand(sub[1:]) in {"add", "set-url", "rename", "remove", "rm"}:
            return "adding or changing a git remote is blocked"
        if sub[:1] == ["config"] and any(GIT_CONFIG_KEYS.match(word) for word in sub[1:]):
            return "git config of remote, push, branch, url or include settings is blocked"
        if sub[:1] == ["config"] and not _git_config_read(sub[1:]):
            return "changing git config is blocked (only --get and --list reads may run)"
        if sub[:1] and sub[0].lower().startswith("credential"):
            return "`git credential` is blocked: it would hand out Khalid's stored GitHub sign-in (SEC-93)"
        return None
    if name in {f"git-{sub}" for sub in GIT_PUSH_PLUMBING}:
        return f"`{name}` is blocked: it pushes to a remote (SEC-102)"
    if name.startswith("git-credential"):
        return "git's credential helpers are blocked: they would hand out Khalid's stored GitHub sign-in (SEC-93)"
    if name.startswith("python") and rest[:2] == ["-m", "twine"]:
        return "publishing packages is blocked"
    if (name, _first_operand(rest)) in PAIRS:
        return f"`{name} {_first_operand(rest)}` is blocked: nothing is published, pushed or deployed"
    return None


def reason(command, depth=0, powershell=False):
    """Why this Bash (or, with powershell=True, PowerShell) command is blocked, or None when it may run."""
    if depth > 5:
        return "command is nested too deeply to check"
    if why := _snafi_reason(command):
        return why
    slashed = command.replace("\\", "/")
    if GIT_CONFIG_FILES.search(slashed.lower()):
        return "git's config files (.git/config, .gitconfig) are not touched from a session"
    if GIT_FOLDER.search(slashed):
        return "the .git folder (config, hooks, commondir) is not touched from a session (SEC-90, SEC-91)"
    if PROFILES.search(slashed):
        return "shell and PowerShell profiles are not touched from a session (SEC-92)"
    if PERSISTENT_ENV.search(slashed):
        return "setting persistent environment variables is blocked (SEC-92)"
    for pattern in RISKY_SETTERS:
        for match in pattern.finditer(command):
            if match.group("name").upper() not in HARMLESS_ENV:
                return (f"setting {match.group('name')} is blocked: git, Git Credential Manager or the shell would "
                        "use it to change where git connects or to reveal Khalid's GitHub sign-in (SEC-102)")
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
    if re.search(r"(^|\\)(\.git\\config|\.gitconfig)$", _win(path)):
        return "git's config files (.git/config, .gitconfig) are not written from a session"
    if ".git" in _win(path).split("\\"):
        return "the .git folder is not written from a session (SEC-90, SEC-91)"
    if re.search(PROFILE_NAME + r"$", _win(path), re.I):
        return "shell and PowerShell profiles are not written from a session (SEC-92)"
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
