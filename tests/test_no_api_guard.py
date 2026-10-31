"""No code path may reach the Anthropic API (guard for the no-API migration). No provider calls.

The scan covers code, configuration and packaging files that Git tracks or would add. Ignored files,
Markdown, docs/ history and src/knowledge/ source material are skipped. KNOWN lists what remains today;
each migration step removes its entries, and the test fails both when a new reference appears and when
a listed one is gone but still listed. The last step empties KNOWN.
"""

import ast
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".py", ".toml", ".lock", ".yaml", ".yml", ".json", ".example", ".cfg", ".ini", ".txt"}
NAMES = {"Dockerfile"}
SKIP = {"tests/test_no_api_guard.py"}
PATTERNS = {
    "key": re.compile(r"ANTHROPIC_API_KEY"),
    "endpoint": re.compile(r"api\.anthropic\.com"),
    "setting": re.compile(r"\banthropic_api_key\b"),
    "consent": re.compile(r"allow_external_ai|ALLOW_EXTERNAL_AI|allow-external-ai"),
    "package": re.compile(r"^\s*[\"']?anthropic\s*(==|>=|~=|<|\[|[\"'])", re.M),
}

# Remaining references: file -> kinds. Shrinks step by step; empty when the migration is done.
KNOWN = {
    ".env.example": ["consent", "key"],
    ".github/workflows/ci.yml": ["consent", "key"],
    "Dockerfile": ["consent"],
    "pyproject.toml": ["package"],
    "requirements-dev.lock": ["package"],
    "requirements.lock": ["package"],
    "scripts/archive/generate_workstation_patches.py": ["key"],
}


def _files():
    try:
        listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a Git checkout")
    for name in listed:
        path = ROOT / name
        if name in SKIP or name.startswith(("src/knowledge/", "docs/")) or not path.is_file():
            continue
        if path.suffix in SUFFIXES or path.name in NAMES:
            yield name, path


def _imports_anthropic(text):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "anthropic" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "anthropic":
            return True
    return False


def scan():
    found = {}
    for name, path in _files():
        text = path.read_text(encoding="utf-8", errors="replace")
        kinds = {kind for kind, pattern in PATTERNS.items() if pattern.search(text)}
        if path.suffix == ".py" and _imports_anthropic(text):
            kinds.add("import")
        if kinds:
            found[name] = sorted(kinds)
    return found


def test_api_references_match_the_known_remaining_list():
    found = scan()
    new = {name: kinds for name, kinds in found.items() if KNOWN.get(name) != kinds}
    cleared = sorted(set(KNOWN) - set(found))
    assert not new and not cleared, f"Changed or new API references: {new}; no longer present, drop from KNOWN: {cleared}"
