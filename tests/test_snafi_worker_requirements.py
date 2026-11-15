"""The deployed worker (C:\\SnafiWorker) installs ONLY src/snafi_worker/deploy/requirements-worker.txt, with
--require-hashes --only-binary=:all: --no-deps. So every package the worker imports, and every package
those need, must be listed there, at uv.lock's version, with a hash of one of uv.lock's wheels for the
worker's own Python 3.12 on 64-bit Windows. (Step 5 bug: set-secrets failed in C:\\SnafiWorker with
"No module named 'cryptography'" because it was only in the repository's .venv.)
"""

import ast
import re
import sys
import tomllib
from pathlib import Path

from packaging.markers import Marker

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "src" / "snafi_worker"
REQUIREMENTS = WORKER / "deploy" / "requirements-worker.txt"
# Import name -> package name, where they differ.
DISTRIBUTION = {"yaml": "pyyaml"}
# The worker's own Python (deploy.ps1: python.org's NuGet package of 3.12.10, 64-bit Windows).
WORKER_PYTHON = {"implementation_name": "cpython", "platform_python_implementation": "CPython",
                 "sys_platform": "win32", "os_name": "nt", "platform_system": "Windows",
                 "platform_machine": "AMD64", "python_version": "3.12", "python_full_version": "3.12.10",
                 "implementation_version": "3.12.10", "platform_release": "", "platform_version": "",
                 "extra": ""}
WHEEL_TAG = re.compile(r"-(cp312-cp312|cp3\d+-abi3|(py2\.)?py3-none)-(win_amd64|any)\.whl$")
# Absolute `src.` imports outside src/snafi_worker that never run in C:\SnafiWorker, each with why:
REPO_ONLY = {
    ("prompt.py", "src.agents.secretary_agent"):
        "build_base_text runs only in the repository (prompt --write); deploy.ps1 refuses without ahmad_base.txt",
}


def pinned(path: Path = REQUIREMENTS):
    """{name: (version, [hashes])} from requirements-worker.txt."""
    text = path.read_text(encoding="utf-8").replace("\\\r\n", " ").replace("\\\n", " ")
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        found = re.match(r"^([A-Za-z0-9_.-]+)==([^\s]+)\s+(.*)$", line)
        assert found, f"every line pins a version and hashes: {line!r}"
        hashes = re.findall(r"--hash=sha256:([0-9a-f]{64})", found.group(3))
        assert hashes, f"{found.group(1)} has no hash"
        out[found.group(1).lower()] = (found.group(2), hashes)
    return out


def lock():
    data = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    return {p["name"].lower(): p for p in data["package"]}


def third_party_imports():
    """Top-level names the worker's own code imports that are not the standard library or itself."""
    found = {}
    for path in WORKER.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                if top in sys.stdlib_module_names:
                    continue
                if top == "src":  # the worker's own package, deployed as src/snafi_worker
                    rel = path.relative_to(WORKER).as_posix()
                    if name == "src.snafi_worker" or name.startswith("src.snafi_worker."):
                        continue
                    if (rel, name) not in REPO_ONLY:
                        found.setdefault(f"{name} (outside src/snafi_worker)", set()).add(rel)
                    continue
                found.setdefault(top, set()).add(str(path.relative_to(WORKER)))
    return found


def test_the_worker_imports_nothing_from_outside_its_own_folder():
    """deploy.ps1 copies only src/snafi_worker; another `src.` import would fail in C:\\SnafiWorker."""
    outside = {k: v for k, v in third_party_imports().items() if "outside src/snafi_worker" in k}
    assert outside == {}


def missing_imports(path: Path = REQUIREMENTS):
    have = pinned(path)
    return {DISTRIBUTION.get(name, name).lower(): sorted(files) for name, files in third_party_imports().items()
            if DISTRIBUTION.get(name, name).lower() not in have}


def test_every_package_the_worker_imports_is_pinned():
    missing = missing_imports()
    assert missing == {}, f"add these to requirements-worker.txt (with hashes): {missing}"


def test_the_check_catches_the_step_5_bug(tmp_path):
    """The file as it was (pyyaml and tzdata only) is caught: cryptography, imported by webpush.py."""
    old = tmp_path / "requirements-worker.txt"
    lines = REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    keep, skip = [], False
    for line in lines:
        if re.match(r"^(cryptography|cffi|pycparser)==", line):
            skip = True
        elif skip and not line.startswith(" "):
            skip = False
        if not skip:
            keep.append(line)
    old.write_text("\n".join(keep) + "\n", encoding="utf-8")
    assert sorted(pinned(old)) == ["pyyaml", "tzdata"]
    assert missing_imports(old) == {"cryptography": ["proactive\\webpush.py" if sys.platform == "win32"
                                                     else "proactive/webpush.py"]}


def test_zoneinfo_has_its_time_zone_data_on_windows():
    """Windows has no system time zone database; zoneinfo needs tzdata."""
    uses = any("zoneinfo" in p.read_text(encoding="utf-8") for p in WORKER.rglob("*.py"))
    assert uses and "tzdata" in pinned()


def test_every_pin_matches_uv_lock_and_a_windows_python_312_wheel():
    locked = lock()
    for name, (version, hashes) in pinned().items():
        assert name in locked, f"{name} is not in uv.lock"
        assert locked[name]["version"] == version, f"{name}=={version} but uv.lock has {locked[name]['version']}"
        wheels = {w["hash"].split(":", 1)[1]: w["url"].rsplit("/", 1)[1] for w in locked[name].get("wheels", [])}
        for h in hashes:
            assert h in wheels, f"{name}: hash {h[:12]}… is not one of uv.lock's wheels"
            assert WHEEL_TAG.search(wheels[h]), f"{name}: {wheels[h]} is not for Python 3.12 on 64-bit Windows"


def test_every_dependency_of_a_pinned_package_is_pinned_too():
    """--no-deps installs nothing by itself, so the whole chain must be listed (cryptography -> cffi -> pycparser)."""
    locked, have = lock(), pinned()
    missing = []
    for name in have:
        for dep in locked[name].get("dependencies", []):
            marker = dep.get("marker")
            if marker and not Marker(marker).evaluate(WORKER_PYTHON):
                continue
            if dep["name"].lower() not in have:
                missing.append(f"{dep['name']} (needed by {name})")
    assert missing == []


def test_the_web_push_chain_is_pinned():
    have = pinned()
    assert {"cryptography", "cffi", "pycparser"} <= set(have)
    assert have["cryptography"][0] == lock()["cryptography"]["version"]
