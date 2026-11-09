"""Restore a Snafi backup into an empty database.

  python -m src.snafi_worker.restore BACKUP --verify
  python -m src.snafi_worker.restore BACKUP --to-sql OUT.sql [--map-user OLD=NEW]
  python -m src.snafi_worker.restore BACKUP --to-database [--map-user OLD=NEW]

Checks, in order: every table's row count and SHA-256, then the manifest's signature (an
HMAC made with the signing key in Windows Credential Manager, SEC-17). A file that fails
either is refused. --accept-unsigned loads a file whose signature cannot be checked (for
example on another PC); use it only for a backup you made yourself.

Nothing restored can run by itself (SEC-17): queued or running jobs are cancelled, pending,
approved or executing approval cards are expired, and pending Undo requests are cleared.

--to-sql writes plain SQL that loads into any Postgres after the Snafi migrations have run
(useful when moving to another database). --to-database loads into the database the worker
is set up for, through its store adapter, and refuses unless every Snafi table is empty.
User accounts are managed by the database's sign-in service and are not in the backup:
create the owner there first, then map the old user id to the new one with --map-user.
"""

import argparse
import gzip
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .backup import FORMAT, digest, signature_ok

# Parents before children (foreign keys).
ORDER = ("jobs", "approvals", "messages", "action_log", "notes", "reminders", "facts", "worker_status")
JSON_COLUMNS = {"payload", "result", "args", "meta", "undo", "lanes"}
COLUMN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
LIVE_JOBS = {"queued", "claimed", "running"}
OPEN_CARDS = {"pending", "approved", "executing"}


class RestoreError(Exception):
    pass


def load(path: Path, signing_key: Optional[str] = None, accept_unsigned: bool = False) -> Dict[str, List[Dict]]:
    try:
        with gzip.open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise RestoreError(f"cannot read backup: {type(exc).__name__}") from None
    manifest, tables = data.get("manifest") or {}, data.get("tables") or {}
    if manifest.get("format") != FORMAT:
        raise RestoreError("not a Snafi backup file")
    for name, info in manifest.get("tables", {}).items():
        rows = tables.get(name)
        if rows is None or len(rows) != info["rows"] or digest(rows) != info["sha256"]:
            raise RestoreError(f"table {name} does not match its checksum; the backup was changed or is damaged")
    unknown = set(tables) - set(ORDER)
    if unknown or set(manifest.get("tables", {})) != set(tables):
        raise RestoreError("backup tables do not match the manifest")
    if not accept_unsigned:
        if not signing_key:
            raise RestoreError("no signing key to check this backup with; see --accept-unsigned")
        if not signature_ok(manifest, signing_key):
            raise RestoreError("the backup's signature does not match; it was not made by this worker or was changed")
    return tables


def neutralise(tables: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """Restored data never acts by itself: no live jobs, no open approval cards, no pending Undo."""
    out = dict(tables)
    out["jobs"] = [({**j, "status": "cancelled", "error": "cancelled by restore"} if j.get("status") in LIVE_JOBS else j)
                   for j in tables.get("jobs", [])]
    out["approvals"] = [({**a, "status": "expired"} if a.get("status") in OPEN_CARDS else a)
                        for a in tables.get("approvals", [])]
    out["action_log"] = [({**a, "undo_requested_at": None} if a.get("undo_requested_at") and not a.get("undone_at") else a)
                         for a in tables.get("action_log", [])]
    return out


def map_users(tables: Dict[str, List[Dict]], mapping: Dict[str, str]) -> Dict[str, List[Dict]]:
    for old, new in mapping.items():
        if not (UUID.match(old) and UUID.match(new)):
            raise RestoreError("--map-user needs OLD=NEW user ids")
    return {t: [{**r, "user_id": mapping.get(r.get("user_id"), r.get("user_id"))} for r in rows]
            for t, rows in tables.items()}


def literal(value, column: str) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if column in JSON_COLUMNS or isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
        return "'" + text.replace("'", "''") + "'::jsonb"
    text = str(value)
    if "\x00" in text:
        raise RestoreError("backup contains a NUL character")
    return "'" + text.replace("'", "''") + "'"


def to_sql(tables: Dict[str, List[Dict]]) -> str:
    tables = neutralise(tables)
    lines = ["-- Snafi restore. Run after the Snafi migrations, into empty tables.", "begin;"]
    for table in ORDER:
        rows = tables.get(table) or []
        if not rows:
            continue
        columns = sorted({c for row in rows for c in row})
        for c in columns:
            if not COLUMN.match(c):
                raise RestoreError(f"unexpected column name in {table}")
        col_list = ", ".join(columns)
        for row in rows:
            values = ", ".join(literal(row.get(c), c) for c in columns)
            lines.append(f"insert into public.{table} ({col_list}) values ({values});")
    lines.append("commit;")
    return "\n".join(lines) + "\n"


def to_database(tables: Dict[str, List[Dict]], store) -> Dict[str, int]:
    tables = neutralise(tables)
    for table in ORDER:
        if store.page(table, 0, 1):
            raise RestoreError(f"the target database already has {table} rows; restore only into empty tables")
    counts = {}
    for table in ORDER:
        for row in tables.get(table) or []:
            store.insert(table, row)
        counts[table] = len(tables.get(table) or [])
    return counts


def main(argv=None, secrets=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.snafi_worker.restore", description=__doc__.split("\n\n")[0])
    parser.add_argument("backup", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--to-sql", type=Path)
    mode.add_argument("--to-database", action="store_true")
    parser.add_argument("--map-user", action="append", default=[], metavar="OLD=NEW")
    parser.add_argument("--accept-unsigned", action="store_true")
    args = parser.parse_args(argv)
    try:
        from .config import ConfigError, Secrets
        try:
            secrets = secrets or Secrets.load()
            key = secrets.get("SNAFI_BACKUP_SIGNING_KEY") if secrets.has("SNAFI_BACKUP_SIGNING_KEY") else None
        except ConfigError:
            key = None
        tables = load(args.backup, key, args.accept_unsigned)
        mapping = dict(item.split("=", 1) for item in args.map_user)
        tables = map_users(tables, mapping)
        if args.verify:
            print("Backup OK: " + ", ".join(f"{t} {len(r)}" for t, r in tables.items()))
        elif args.to_sql:
            args.to_sql.write_text(to_sql(tables), encoding="utf-8")
            print(f"Wrote {args.to_sql}")
        else:
            from .config import Settings
            from .services import build
            counts = to_database(tables, build("store", Settings.load(), secrets))
            print("Restored: " + ", ".join(f"{t} {n}" for t, n in counts.items()))
        return 0
    except (RestoreError, ValueError) as exc:
        print(f"Restore refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
