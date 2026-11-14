"""Daily backup of every Snafi table into one dated, compressed file on this PC.

No AI call and no token cost: it only copies rows from the database. Files go to
teams/coordination/snafi-backups/ (ignored by Git; no Claude Code session may read it),
named snafi-backup-YYYYMMDD-HHMM.json.gz in Jeddah time. Each file carries a manifest with
every table's row count and SHA-256, so restore can prove nothing changed. The newest 30
days are kept; older files are deleted only after a new backup succeeds, and only files
that match the backup naming pattern. The result is written to worker_status.

Each manifest is signed (SEC-17): an HMAC-SHA256 over the manifest, which holds every
table's SHA-256, with a key kept in Windows Credential Manager. Restore refuses a file
whose signature does not match, so a planted or edited backup cannot be loaded quietly.
"""

import gzip
import hashlib
import hmac
import json
import logging
import os
import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from . import VERSION
from .store import TABLES

log = logging.getLogger("snafi_worker")
FORMAT = "snafi-backup/1"
SCHEMA = 5  # database layout version (Snafi step 5: notifications, cards, user_settings)
NAME = re.compile(r"^snafi-backup-(\d{8})-(\d{4})\.json\.gz$")
PAGE = 1000


def canonical(rows: List[Dict]) -> bytes:
    return json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def digest(rows: List[Dict]) -> str:
    return hashlib.sha256(canonical(rows)).hexdigest()


def sign(manifest: Dict, key: str) -> str:
    body = json.dumps({k: v for k, v in manifest.items() if k != "signature"}, sort_keys=True,
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()


def signature_ok(manifest: Dict, key: str) -> bool:
    given = manifest.get("signature")
    return isinstance(given, str) and hmac.compare_digest(given, sign(manifest, key))


def export_tables(store) -> Dict[str, List[Dict]]:
    data = {}
    for table in TABLES:
        rows, offset = [], 0
        while True:
            page = store.page(table, offset, PAGE)
            rows.extend(page)
            if len(page) < PAGE:
                break
            offset += PAGE
        data[table] = rows
    return data


def backup_files(folder: Path) -> List[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and NAME.match(p.name))


def file_date(path: Path) -> date:
    return datetime.strptime(NAME.match(path.name).group(1), "%Y%m%d").date()


def prune(folder: Path, today: date, keep_days: int) -> List[str]:
    """Delete backups older than keep_days (by the date in their name). Returns the names removed."""
    oldest_kept = today - timedelta(days=keep_days - 1)
    removed = []
    for path in backup_files(folder):
        if file_date(path) < oldest_kept:
            path.unlink()
            removed.append(path.name)
    return removed


def write_backup(store, folder: Path, now: datetime, time_zone: str, signing_key: str) -> Dict:
    local = now.astimezone(ZoneInfo(time_zone))
    data = export_tables(store)
    manifest = {
        "format": FORMAT, "schema": SCHEMA, "worker_version": VERSION,
        "created_at": now.astimezone(timezone.utc).isoformat(), "time_zone": time_zone,
        "tables": {t: {"rows": len(rows), "sha256": digest(rows)} for t, rows in data.items()},
    }
    manifest["signature"] = sign(manifest, signing_key)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"snafi-backup-{local:%Y%m%d-%H%M}.json.gz"
    final, temp = folder / name, folder / (name + ".part")
    with gzip.open(temp, "wb") as out:
        out.write(json.dumps({"manifest": manifest, "tables": data}, ensure_ascii=False, default=str).encode("utf-8"))
    os.replace(temp, final)
    return {"file": name, "rows": {t: v["rows"] for t, v in manifest["tables"].items()}}


def run_backup(store, folder: Path, owner_id: str, worker_id: str, time_zone: str, keep_days: int,
               now: Optional[datetime] = None, signing_key: str = "") -> Dict:
    now = now or datetime.now(timezone.utc)
    if keep_days < 1:
        raise ValueError("keep_days must be at least 1")
    status = {"user_id": owner_id, "worker_id": worker_id, "last_backup_at": now.isoformat()}
    try:
        if not signing_key:
            raise ValueError("no backup signing key")
        result = write_backup(store, folder, now, time_zone, signing_key)
        removed = prune(folder, now.astimezone(ZoneInfo(time_zone)).date(), keep_days)
        status.update(last_backup_ok=True, last_backup_error=None, last_backup_file=result["file"])
        log.info("backup ok file=%s removed=%d", result["file"], len(removed))
        outcome = {"ok": True, **result, "removed": removed}
    except Exception as exc:  # the error is recorded without any row content
        for leftover in folder.glob("*.part") if folder.is_dir() else []:
            leftover.unlink(missing_ok=True)
        status.update(last_backup_ok=False, last_backup_error=f"{type(exc).__name__}: {str(exc)[:200]}")
        log.error("backup failed: %s", type(exc).__name__)
        outcome = {"ok": False, "error": status["last_backup_error"]}
    try:
        store.upsert("worker_status", status, "user_id")
    except Exception as exc:
        log.warning("could not record backup status: %s", type(exc).__name__)
    return outcome


def is_due(folder: Path, now: datetime, time_zone: str, at: str) -> bool:
    """Due once a day after the set time, or whenever the newest good backup is over 24 hours old."""
    local = now.astimezone(ZoneInfo(time_zone))
    files = backup_files(folder)
    if not files:
        return True
    newest = files[-1]
    stamp = datetime.strptime("".join(NAME.match(newest.name).groups()), "%Y%m%d%H%M").replace(tzinfo=ZoneInfo(time_zone))
    if local - stamp > timedelta(hours=24):
        return True
    hour, minute = (int(x) for x in at.split(":"))
    return local.time() >= local.replace(hour=hour, minute=minute).time() and stamp.date() < local.date()


class BackupScheduler(threading.Thread):
    def __init__(self, store, settings, owner_id, stop: threading.Event, signing_key: str, check_seconds: float = 60):
        super().__init__(name="backup", daemon=True)
        self.store, self.settings, self.owner_id, self.stop = store, settings, owner_id, stop
        self.signing_key = signing_key
        self.check_seconds = check_seconds

    def run(self):
        while not self.stop.is_set():
            s = self.settings
            try:
                if is_due(s.backup_folder, datetime.now(timezone.utc), s.time_zone, s.backup_time):
                    run_backup(self.store, s.backup_folder, self.owner_id, s.worker_id, s.time_zone, s.backup_keep_days,
                               signing_key=self.signing_key)
            except Exception as exc:
                log.error("backup scheduler error: %s", type(exc).__name__)
            self.stop.wait(self.check_seconds)
