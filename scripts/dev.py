"""Project-local locked setup/launcher; no global Python or shell changes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".venv"
LOCK = ROOT / "requirements-dev.lock"


def python_path():
    return ENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def native_environment(base=None, platform=None, candidates=None):
    environment = dict(os.environ if base is None else base)
    # A project launch must not inherit temporary/global Python import overrides.
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    platform = platform or sys.platform
    if platform == "darwin":
        paths = list(candidates or [])
        if candidates is None:
            brew = shutil.which("brew")
            if brew:
                try:
                    prefix = subprocess.check_output([brew, "--prefix"], text=True, timeout=5).strip()
                    paths.append(Path(prefix) / "lib")
                except (subprocess.SubprocessError, OSError):
                    pass
            paths += [Path(sys.base_prefix) / "lib", Path("/opt/homebrew/lib"), Path("/usr/local/lib")]
        found = [str(p) for p in paths if (Path(p) / "libgobject-2.0.dylib").is_file()
                 and (Path(p) / "libpango-1.0.dylib").is_file()]
        existing = environment.get("DYLD_FALLBACK_LIBRARY_PATH", "").split(os.pathsep)
        if found:
            environment["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join(dict.fromkeys(found + [p for p in existing if p]))
    return environment


def run(arguments, **kwargs):
    return subprocess.run([str(python_path()), *arguments], cwd=ROOT, env=native_environment(), check=True, **kwargs)


def bootstrap(wheelhouse=None):
    if not (3, 11) <= sys.version_info[:2] <= (3, 14):
        raise ValueError("Use Python 3.11 through 3.14")
    if ENV.is_symlink():
        raise ValueError("Project environment must not be a symlink")
    if not python_path().exists():
        venv.EnvBuilder(with_pip=True).create(ENV)
    arguments = ["-m", "pip", "install", "--cache-dir", str(ROOT / ".dev-cache" / "pip"), "--require-hashes", "--only-binary=:all:", "-r", str(LOCK)]
    if wheelhouse:
        arguments += ["--no-index", "--find-links", str(Path(wheelhouse).resolve())]
    run(arguments)
    run(["-m", "pip", "check"])
    (ENV / "reema-lock.json").write_text(json.dumps({"lock_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest()}, indent=2) + "\n")
    run([str(Path(__file__).resolve()), "_doctor"])


def doctor():
    from importlib.metadata import version, PackageNotFoundError
    from packaging.requirements import Requirement
    if Path(sys.prefix).resolve() != ENV.resolve():
        raise ValueError("Doctor must use the project environment")
    stamp = ENV / "reema-lock.json"
    if not stamp.exists() or json.loads(stamp.read_text()).get("lock_sha256") != hashlib.sha256(LOCK.read_bytes()).hexdigest():
        raise ValueError("Environment lock stamp missing/changed; run python3 scripts/dev.py bootstrap")
    mismatches = []
    for line in LOCK.read_text().splitlines():
        if not re.match(r"^[A-Za-z0-9_-]+==", line):
            continue
        requirement = Requirement(line.rstrip().removesuffix("\\").strip())
        if requirement.marker and not requirement.marker.evaluate():
            continue
        try:
            actual = version(requirement.name)
        except PackageNotFoundError:
            actual = None
        if actual is None or not requirement.specifier.contains(actual):
            mismatches.append(requirement.name)
    if mismatches:
        raise ValueError("Locked dependencies missing/changed: " + ", ".join(mismatches))
    from src.formatters.pdf_formatter import PDFFormatter
    PDFFormatter()
    print("Project environment matches requirements-dev.lock; PDF native imports available.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["bootstrap", "doctor", "test", "run", "smoke", "python", "_doctor"])
    parser.add_argument("--wheelhouse", type=Path, help="Install offline from a hash-verified wheel directory")
    args, forwarded = parser.parse_known_args()
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]
    if args.command == "bootstrap":
        bootstrap(args.wheelhouse)
    elif args.command == "_doctor":
        # Direct execution of this helper has scripts/ on sys.path.
        sys.path.insert(0, str(ROOT))
        doctor()
    else:
        if ENV.is_symlink():
            raise ValueError("Project environment must not be a symlink")
        if not python_path().is_file():
            raise ValueError("Run python3 scripts/dev.py bootstrap first")
        stamp = ENV / "reema-lock.json"
        if not stamp.exists() or json.loads(stamp.read_text()).get("lock_sha256") != hashlib.sha256(LOCK.read_bytes()).hexdigest():
            raise ValueError("Project lock changed; rerun bootstrap")
        if args.command == "doctor":
            run([str(Path(__file__).resolve()), "_doctor"])
        elif args.command == "test":
            run(["-m", "pytest", *(forwarded or ["-q", "-rs"])])
        elif args.command == "run":
            run(["-m", "src.main", *forwarded])
        elif args.command == "python":
            run(forwarded)
        else:
            run(["-m", "scripts.verify_exports", *forwarded])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, ImportError, subprocess.CalledProcessError) as error:
        print(f"Development setup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
