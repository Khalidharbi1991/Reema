"""Run the Snafi worker.

  python -m src.snafi_worker            run until stopped (lanes, heartbeat, daily backup)
  python -m src.snafi_worker --check    check worker.yaml and the stored secrets (names, never values)
  python -m src.snafi_worker --once     answer the jobs waiting now, then stop
  python -m src.snafi_worker --backup-now

Logs go to %APPDATA%\\REEMA\\snafi-worker\\logs\\worker.log: job ids and status only, never
message text or keys.
"""

import argparse
import logging
import re
import signal
import sys
import threading
from logging.handlers import RotatingFileHandler

from . import VERSION
from .backup import BackupScheduler, run_backup
from .config import ConfigError, Secrets, Settings, worker_data_dir
from .engine import Engine
from .runner import Heartbeat, Lane, run_job
from .services import build

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def setup_logging() -> None:
    folder = worker_data_dir() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(folder / "worker.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s"))
    root = logging.getLogger("snafi_worker")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if sys.stderr is not None:  # pythonw (the scheduled task) has no console
        root.addHandler(logging.StreamHandler(sys.stderr))


def owner(secrets: Secrets) -> str:
    value = secrets.get("SNAFI_OWNER_USER_ID").lower()
    if not UUID.match(value):
        raise ConfigError("SNAFI_OWNER_USER_ID must be your Snafi user id (a UUID)")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.snafi_worker")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--backup-now", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings, secrets = Settings.load(), Secrets.load()
        owner_id = owner(secrets)
        secrets.get("SNAFI_BACKUP_SIGNING_KEY")  # backups are signed (SEC-17)
        store, brain = build("store", settings, secrets), build("brain", settings, secrets)
    except ConfigError as exc:
        print(f"Snafi worker not started: {exc}", file=sys.stderr)
        return 2
    if args.check:
        print(f"Snafi worker {VERSION}: brain={settings.brain_provider} store={settings.store_provider} "
              f"secrets present={secrets.names()} backups={settings.backup_folder}")
        return 0
    setup_logging()
    engine = Engine(store, brain, settings.time_zone)
    if args.backup_now:
        outcome = run_backup(store, settings.backup_folder, owner_id, settings.worker_id, settings.time_zone,
                             settings.backup_keep_days, signing_key=secrets.get("SNAFI_BACKUP_SIGNING_KEY"))
        print("Backup " + ("OK: " + outcome["file"] if outcome["ok"] else "failed: " + outcome["error"]))
        return 0 if outcome["ok"] else 1
    if args.once:
        for lane, lane_settings in settings.lanes.items():
            while (job := store.claim_job(lane, settings.worker_id)):
                print(f"{job['kind']} -> {run_job(store, engine, job, lane_settings.timeout_seconds, lane_settings.retry_delay_seconds)}")
        return 0

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    lanes = {name: Lane(name, s, store, engine, settings.worker_id, stop) for name, s in settings.lanes.items()}
    threads = [*lanes.values(), Heartbeat(store, owner_id, settings.worker_id, lanes, settings.heartbeat_seconds, stop),
               BackupScheduler(store, settings, owner_id, stop, secrets.get("SNAFI_BACKUP_SIGNING_KEY"))]
    for thread in threads:
        thread.start()
    logging.getLogger("snafi_worker").info("worker %s started (brain=%s)", VERSION, settings.brain_provider)
    while not stop.wait(5):
        for name, lane in lanes.items():
            if not lane.is_alive():  # a lane that died is restarted
                lanes[name] = Lane(name, settings.lanes[name], store, engine, settings.worker_id, stop)
                lanes[name].start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
