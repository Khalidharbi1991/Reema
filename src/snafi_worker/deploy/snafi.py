"""Snafi worker launcher, copied to C:\\SnafiWorker\\app\\snafi.py by the deploy script and
run with Python's isolated mode (-I), so no stray file in the working folder, no
PYTHONPATH and no user site-packages can be loaded with the worker's keys (SEC-19).

    snafi.cmd worker           run until stopped (the scheduled task uses this)
    snafi.cmd check            settings and which secrets are stored (names only)
    snafi.cmd once             answer the jobs waiting now, then stop
    snafi.cmd backup-now
    snafi.cmd reset-brain      clear a safety pause after you have looked
    snafi.cmd set-secrets      store the worker's secrets (asks; never shows keys)
    snafi.cmd connect-google   connect your Google account once (--status, --disconnect)
    snafi.cmd prove            the live lockdown proof for the brain
    snafi.cmd restore BACKUP --verify | --to-sql OUT.sql | --to-database [...]
"""

import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
COMMANDS = ("worker", "check", "once", "backup-now", "reset-brain", "set-secrets", "connect-google", "prove", "restore")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv.pop(0) if argv else "worker"
    if command not in COMMANDS:
        print(__doc__)
        return 2
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))  # -I leaves the script's own folder off sys.path; add only this one
    if command == "set-secrets":
        from src.snafi_worker.set_secrets import main as run
        return run(argv)
    if command == "connect-google":
        from src.snafi_worker.google.connect import main as run
        return run(argv)
    if command == "prove":
        from src.snafi_worker.brain.agy_proof import main as run
        return run(argv)
    if command == "restore":
        from src.snafi_worker.restore import main as run
        return run(argv)
    from src.snafi_worker.__main__ import main as run
    flag = {"worker": [], "check": ["--check"], "once": ["--once"], "backup-now": ["--backup-now"],
            "reset-brain": ["--reset-brain"]}[command]
    return run(flag + argv)


if __name__ == "__main__":
    sys.exit(main())
