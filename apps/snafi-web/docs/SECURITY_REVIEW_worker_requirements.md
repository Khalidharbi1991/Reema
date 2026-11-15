# Security review: Snafi worker requirements fix (branch `fix/snafi-worker-requirements`)

Reviewer: Agent 16. Date: 2026-11-15. Scope: `apps/snafi-web/.reema/security_diff_worker_requirements.patch`
(one commit on main 722d031). This is a manual read-only review: no scanner and no tests were run, and it is not a
certification. Khalid decides.

Files read: the diff; `uv.lock` (the `cffi`, `cryptography` and `pycparser` entries); `src/snafi_worker/deploy/deploy.ps1`;
`src/snafi_worker/prompt.py`; the top of `src/snafi_worker/proactive/webpush.py`.

## Checks done

**The hashes match uv.lock's wheels for these exact versions.** Each one was checked by eye against `uv.lock`:

| Pin | Hash in requirements-worker.txt | uv.lock wheel (line) |
| --- | --- | --- |
| cryptography==50.0.1 | `aed8db4f…0648` | `cryptography-50.0.1-cp311-abi3-win_amd64.whl` (431) |
| cryptography==50.0.1 | `55d16b1e…13f2` | `cryptography-50.0.1-cp39-abi3-win_amd64.whl` (457) |
| cffi==2.1.1 | `f53e442b…339a` | `cffi-2.1.1-cp312-cp312-win_amd64.whl` (155) |
| pycparser==3.0 | `b7274141…a992` | `pycparser-3.0-py3-none-any.whl` (1084) |

All four match uv.lock's version, and all four are wheels that pip can install on CPython 3.12 for 64-bit Windows. I did not re-check the
pyyaml and tzdata pins (they were already there and the diff does not change them). The new test checks them.

**The dependency chain is complete for CPython 3.12 on Windows.** In uv.lock, cryptography 50.0.1 depends only on
`cffi` (marker `platform_python_implementation != 'PyPy'`, true here). It has no `typing-extensions`. cffi 2.1.1 depends
only on `pycparser` (marker `implementation_name != 'PyPy'`, true). pycparser 3.0 has no dependencies. Nothing is missing.

**`--require-hashes --only-binary=:all: --no-deps` cannot pull in anything unpinned.** `--no-deps` stops pip from resolving
anything beyond the five listed packages. `--only-binary=:all:` refuses source distributions, so pip never fetches or runs
a build backend (setuptools and the like). `--require-hashes` means each file pip installs must match one of its listed
hashes. A wrong or missing wheel makes the install fail, so nothing extra gets installed. The trade-off is that `--no-deps`
also means pip never notices a missing dependency. The new test is now the control for that (see SEC-134 to SEC-136 for its limits).

**Whether the test can pass vacuously.** `ast.walk` covers the whole tree, so imports inside functions, `if` blocks and
`try/except ImportError` blocks are all counted. An optional import is treated as required, which is the cautious direction.
`test_the_check_catches_the_step_5_bug` is a real negative control: it rebuilds the old file and expects
`cryptography` from `proactive/webpush.py`. `test_snafi_worker_deploy.py` now requires the exact five-package list and
6 hashes, so a package added quietly is caught too. The gaps I found are below. None of them is a security bypass. Each one
would show up as an import error when the deployed worker starts.

**Whether the REPO_ONLY exception is sound.** It is sound today. In `prompt.py` the only `src.agents.secretary_agent` import is inside
`build_base_text()` (line 28), not at the top of the module. The deployed worker reads `ahmad_base.txt`, which `deploy.ps1` requires
(line 59) and copies. `base_text()` (lines 41-45) falls back to `build_base_text()` only if that file is missing. In that case
`src.agents` does not exist in `C:\SnafiWorker` (only `src\__init__.py` and `src\snafi_worker` are copied), so it fails with
an import error and runs no other code. The weakness is how the exception is matched (SEC-136).

## Findings

| ID | Severity | File:line | What an attacker (or a mistake) could do | Fix |
| --- | --- | --- | --- | --- |
| SEC-134 | Low | tests/test_snafi_worker_requirements.py:111 (and 103-127) | The scan skips every relative import (`node.level == 0` only). A relative import that climbs out of the worker, such as `from ...agents import x` in `src/snafi_worker/brain/`, resolves to `src.agents`, so the test passes and the deployed worker fails. String-based imports (`importlib.import_module("pkg")`, `__import__`) are not seen either. The result is availability only (an import error in `C:\SnafiWorker`), with no unpinned code installed. | Resolve each relative import against the file's package and flag any that land outside `src.snafi_worker`. Also flag calls to `importlib.import_module`/`__import__` whose argument is a string constant naming something other than the worker or the standard library. |
| SEC-135 | Low | tests/test_snafi_worker_requirements.py:117 | `sys.stdlib_module_names` comes from the Python running the tests, not the worker's 3.12.10. On 3.11 it still lists modules that 3.12 removed (`distutils`, `imp`, `asyncore`, `asynchat`, `smtpd`), so the test would count them as standard library and the deployed worker would fail. | Skip or fail the test unless `sys.version_info[:2] == (3, 12)`, or subtract a fixed set of modules removed in 3.12. |
| SEC-136 | Low | tests/test_snafi_worker_requirements.py:76-79, 123 | The exception matches on (file, module name), not on where the import sits. A later top-level `from src.agents.secretary_agent import ...` in `prompt.py` would also be excused, and the deployed worker would then fail on every import of `prompt`. | Excuse the import only when the `ImportFrom` node is inside the `FunctionDef` named `build_base_text`, for example by walking that function's body instead of the whole tree. |
| SEC-137 | Info | tests/test_snafi_worker_requirements.py:74 | `WHEEL_TAG` accepts any `cp3NN-abi3` (including cp313/cp314-abi3, which 3.12 cannot install) and tag pairings like `cp312-cp312-any`. A wrong pin would pass the test and then fail at install, so the install still fails safely. | Limit abi3 to `cp3(?:[0-9]\|1[0-2])-abi3`, and require `win_amd64` for cp tags and `any` for `py3-none`. |
| SEC-138 | Info | src/snafi_worker/deploy/deploy.ps1:23-24 | The header still says deploy installs "exactly pyyaml 6.0.3 and tzdata 2026.6". This is a stale description for Khalid, not a behaviour problem. | Reword to "exactly the packages in requirements-worker.txt, as wheels whose SHA-256 must match it". |
| SEC-139 | Info | src/snafi_worker/deploy/deploy.ps1:104 | This existed before the diff. `-I` isolates Python but not pip: pip still reads `PIP_*` environment variables and `%APPDATA%\pip\pip.ini`, so a changed index URL or proxy would decide where wheels are downloaded from. The hashes still pin the content, so no other code can be installed. | Add pip's `--isolated` flag (ignores environment variables and user config), and optionally `--index-url https://pypi.org/simple`. |

## Summary

**Open Critical: 0. Open High: 0.** Nothing blocks the merge.

For Khalid to decide: Low SEC-134, SEC-135 and SEC-136 (making the test stricter; all three are about availability), and Info
SEC-137, SEC-138 and SEC-139.

## Not reviewed

- I ran no tests. The figures of 1391 Python and 169 web tests passing are Ahmad's, not mine.
- I did not compare the wheel files on PyPI with uv.lock, or check that uv.lock itself is right (no network). I also did not
  confirm that the bundled pip prefers the cp311-abi3 wheel over the cp39-abi3 one. Either one installs on 3.12, and both are hash-pinned.
- I did not re-check the pyyaml and tzdata pins against uv.lock by eye.
- I did not read every file under `src/snafi_worker/` to look for dynamic imports (SEC-134) or other third-party imports. I relied on the
  test's scan for that.
- I did not re-review `webpush.py` beyond its imports, the deployed `C:\SnafiWorker` copy, `snafi.cmd` and `snafi.py`. I also did not
  re-check items still open in earlier reviews.

## After this check (Nov 15, by Ahmad as the coding agent; not re-checked by Agent 16)

- **SEC-134 (fixed, awaiting re-check):** the scan now refuses a relative import that climbs above `src/snafi_worker` (its level is more than the file's depth). Imports named as text (`importlib.import_module`, `__import__`) are still not scanned; none exist in the worker today.
- **SEC-135 (fixed, awaiting re-check):** a test requires the suite to run on Python 3.12, the worker's own version, so the standard-library list is the right one.
- **SEC-136 (fixed, awaiting re-check):** the REPO_ONLY exception now names the one function it may sit in (`build_base_text`); the same import anywhere else in `prompt.py` is refused. A test with sample files covers SEC-134 and SEC-136.
- **SEC-138 (fixed):** the deploy.ps1 header comment now names all five packages (comment only; no command changed).
- Both suites pass after these (Python 1393, web 169).

**Still for Khalid:** Info SEC-137 (tighter wheel-name pattern in the test) and SEC-139 (add pip's `--isolated` to deploy.ps1 so `PIP_*` settings and `pip.ini` cannot change where wheels come from; the hashes already decide what is installed). Open Critical 0, open High 0.
