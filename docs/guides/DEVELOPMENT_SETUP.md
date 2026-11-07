# Project-local development setup

Use Python 3.11–3.14 to bootstrap from the repository root:

```bash
python3 scripts/dev.py bootstrap
python3 scripts/dev.py doctor
python3 scripts/dev.py test -q -rs
python3 scripts/dev.py run list-processes
python3 scripts/dev.py smoke --output teams/documentation/output/local-smoke-new
```

On Windows, use `python` if `python3` is unavailable. The bootstrap creates ignored
`.venv/`, installs binary wheels with `--require-hashes` from the existing
`requirements-dev.lock`, checks dependencies and records the lock digest. It does
not install into global Python, activate a shell or change shell configuration.
Re-running it updates an existing project environment; it installs but never
uninstalls, so after a lock drops a package, uninstall it from `.venv/` too (the
no-API guard fails if `anthropic` is installed). A changed lock requires a new
bootstrap; doctor checks installed package versions against the applicable lock
entries and imports the actual PDF formatter. The locks are made with `uv`: `uv lock`
for `uv.lock`, then the `uv export` command in each `requirements*.lock` header;
don't hand-edit them.

Normal commands use the project Python with the repository as working directory.
The launcher removes inherited `PYTHONPATH`/`PYTHONHOME`, so temporary test packages
are unnecessary. `run` forwards arguments to the existing REEMA CLI, `test` to
pytest, `smoke` to the synthetic four-format export script, and `python` forwards
Python arguments for other project scripts:

```bash
python3 scripts/dev.py python -m scripts.verify_document_package --output teams/documentation/output/qa/new-example
python3 scripts/dev.py run task list --area work
```

Use a fresh smoke output directory to preserve earlier files. REEMA makes no model
call and needs no API key; source permissions still apply. Tests block every network
connection.

## Native PDF libraries

On macOS the launcher checks Homebrew's reported prefix, the base Python library
directory and common Intel/Apple Silicon Homebrew locations. It adds only existing
directories containing Pango/GObject libraries to the child process's library
search path. A native library path does not have to be entered for each command.
Linux keeps normal system-library discovery; Windows preserves configured native
DLL discovery. No native libraries are downloaded or installed automatically.

The verified macOS host has native libraries in `/opt/homebrew/lib`. The clean workflow
above passed with project Python 3.14.2 and locked WeasyPrint 70.0. Native packages
must be installed separately on other hosts if doctor reports them missing. This
local result does not claim that all supported OS/Python combinations were tested.

On the verified Windows 11 host, Pango comes from MSYS2: `C:\msys64\mingw64\bin`, named in
the user environment variable `WEASYPRINT_DLL_DIRECTORIES`; the workflow passed with
Python 3.12.10. Run `git config core.autocrlf false` in this repository once: Git for
Windows converts line endings on checkout by default, which changes the bytes of the
locks and other files REEMA checks by SHA-256.

## Offline dependency installation

Bootstrap can use a complete pre-populated wheel directory:

```bash
python3 scripts/dev.py bootstrap --wheelhouse /absolute/path/to/wheels
```

That adds `--no-index` while retaining hash checks. Without `--wheelhouse`, pip may
use the configured package index and cached wheels; network permission is needed
if packages are missing. Subsequent cache writes belong in ignored
`.dev-cache/pip/`. Wheels must match the lock and target Python/platform. Missing
binary wheels fail explicitly; bootstrap does not silently build source packages,
change pins or install global packages.

The environment and caches can be recreated from the lock. They are development
files, not customer-data storage or a signed audit ledger. Keep credentials in
the existing private configuration locations, never in bootstrap files.
