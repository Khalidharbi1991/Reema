"""No code path can reach the Anthropic API, except the one Khalid asked for (Nov 13, 2026): the Snafi
worker's Claude brain. Strict: any reference, declaration or import outside ALLOWED fails the suite.

ALLOWED lists the exact files and the exact kinds of reference each may hold: the brain adapter may name
the endpoint and the key; the secret list and the one-time setup may name the key. No file may import the
anthropic package or declare it, and the allowed files are themselves checked to hold nothing more.

The scan covers code, configuration and packaging files that Git tracks or would add. Ignored files,
Markdown, docs/ history and src/knowledge/ source material are skipped. A fresh process with every
`anthropic` import blocked must still load all of REEMA, its scripts and every command's help, and
the test suite itself cannot reach the network (tests/conftest.py).
"""

import ast
import importlib.util
import re
import socket
import subprocess
import sys
import tomllib
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
ALLOWED = {
    "src/snafi_worker/brain/claude_api.py": {"endpoint", "key"},
    "src/snafi_worker/secret_store.py": {"key"},
    "src/snafi_worker/set_secrets.py": {"key"},
    "tests/test_snafi_worker_claude.py": {"endpoint", "key"},
}
SCRIPTS = ["claude_code_generate.py", "claude_code_review.py", "claude_code_revise.py", "evaluate_agents.py"]


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


def test_no_file_references_the_anthropic_api():
    found = scan()
    outside = {name: kinds for name, kinds in found.items() if name not in ALLOWED}
    assert outside == {}
    too_much = {name: kinds for name, kinds in found.items() if name in ALLOWED and not set(kinds) <= ALLOWED[name]}
    assert too_much == {}  # e.g. an import or a package line in an allowed file still fails


def test_the_only_anthropic_endpoint_is_in_the_snafi_claude_brain():
    found = scan()
    assert [name for name, kinds in found.items() if "endpoint" in kinds and not name.startswith("tests/")] == [
        "src/snafi_worker/brain/claude_api.py"]


def test_anthropic_is_neither_declared_nor_installed():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = project["dependencies"] + [d for extra in project.get("optional-dependencies", {}).values() for d in extra]
    assert not [d for d in declared if re.match(r"\s*anthropic\b", d, re.I)]
    assert importlib.util.find_spec("anthropic") is None


LOAD_EVERYTHING = r'''
import importlib, importlib.abc, importlib.util, pkgutil, sys
from pathlib import Path

class Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] == "anthropic":
            raise ImportError("anthropic import attempted: " + name)

sys.meta_path.insert(0, Blocked())
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
import src
modules = [m.name for m in pkgutil.walk_packages(src.__path__, "src.")]
for name in modules:
    importlib.import_module(name)
for script in sys.argv[2:]:
    spec = importlib.util.spec_from_file_location(Path(script).stem, root / "scripts" / script)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
import typer.main
from typer.testing import CliRunner
from src.main import app

def paths(command, prefix=()):
    yield prefix
    for name, child in getattr(command, "commands", {}).items():
        yield from paths(child, prefix + (name,))

runner, count = CliRunner(), 0
for path in paths(typer.main.get_command(app)):
    result = runner.invoke(app, [*path, "--help"])
    assert result.exit_code == 0, (path, result.output)
    count += 1
assert "anthropic" not in sys.modules
print(len(modules), count)
'''


def test_everything_loads_with_anthropic_blocked():
    result = subprocess.run([sys.executable, "-c", LOAD_EVERYTHING, str(ROOT), *SCRIPTS],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr[-2000:]
    modules, commands = map(int, result.stdout.split()[-2:])
    assert modules >= 30 and commands >= 20


def test_the_suite_cannot_reach_the_network():
    with socket.socket() as connection, pytest.raises(AssertionError, match="Network access is forbidden"):
        connection.connect(("127.0.0.1", 9))
