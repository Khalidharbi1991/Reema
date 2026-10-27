"""Local work and personal task lists. No model or external service is used."""

import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

AREAS = ("work", "personal")
PRIORITIES = ("low", "normal", "high", "urgent")
STATUSES = ("open", "done", "archived")
MEMORY_KINDS = ("preference", "profile", "project", "lesson", "example")
_UNSET = object()


def _text(value, name, limit, *, required=False):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    result = value.strip()
    if len(result) > limit or any(ord(char) < 32 and char not in "\n\t" for char in result):
        raise ValueError(f"{name} exceeds {limit} characters or contains invalid characters")
    if required and not result:
        raise ValueError(f"{name} is required")
    return result


def _due(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Due date must be YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Due date must be a real calendar date") from error
    return value


def memory_scope(kind, project=""):
    """Validate explicit memory scope; project names never become file paths."""
    if kind not in MEMORY_KINDS:
        raise ValueError("Memory kind must be preference, profile, project, lesson, or example")
    project = _text(project, "Project", 120)
    if kind == "project" and not project:
        raise ValueError("Project memory requires --project NAME")
    if kind in {"preference", "profile"} and project:
        raise ValueError("Preferences and profile memory are area-wide; omit --project")
    return project


class TaskStore:
    """A single-area task store, with a distinct local database per area."""

    def __init__(self, directory: Path, area: str, timezone: str = "Asia/Riyadh"):
        if area not in AREAS:
            raise ValueError("Area must be work or personal")
        self.area = area
        self.directory = Path(directory)
        self.path = self.directory / f"{area}.sqlite3"
        self.timezone = ZoneInfo(timezone)

    def _connect(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        connection = sqlite3.connect(self.path, timeout=10)
        self.path.chmod(0o600)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA secure_delete = ON")
        connection.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, project TEXT NOT NULL,
            details TEXT NOT NULL, priority TEXT NOT NULL, due TEXT,
            status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS assistant_memory (
            kind TEXT NOT NULL, project TEXT NOT NULL, key TEXT NOT NULL,
            value TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY (kind, project, key)
        )""")
        connection.commit()
        return connection

    def add(self, title, *, project="", details="", priority="normal", due=None):
        title = _text(title, "Title", 240, required=True)
        project = _text(project, "Project", 120)
        details = _text(details, "Details", 4000)
        if priority not in PRIORITIES:
            raise ValueError("Priority must be low, normal, high, or urgent")
        due = _due(due)
        stamp = datetime.now(self.timezone).isoformat(timespec="seconds")
        record = (uuid4().hex, title, project, details, priority, due, "open", stamp, stamp)
        connection = self._connect()
        try:
            connection.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", record)
            connection.commit()
        finally:
            connection.close()
        return self.get(record[0])

    def get(self, task_id):
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise ValueError("Task not found in this area")
            return dict(row) | {"area": self.area}
        finally:
            connection.close()

    def list(self, *, status="open", due_through=None, project=None):
        if status not in (*STATUSES, "all"):
            raise ValueError("Status must be open, done, archived, or all")
        due_through = _due(due_through)
        where, values = [], []
        if status != "all":
            where.append("status = ?")
            values.append(status)
        if due_through:
            where.append("due IS NOT NULL AND due <= ?")
            values.append(due_through)
        if project is not None:
            where.append("project = ?")
            values.append(_text(project, "Project", 120, required=True))
        clause = " WHERE " + " AND ".join(where) if where else ""
        connection = self._connect()
        try:
            rows = connection.execute("SELECT * FROM tasks" + clause +
                " ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, "
                "CASE WHEN due IS NULL THEN 1 ELSE 0 END, due, created_at", values).fetchall()
            return [dict(row) | {"area": self.area} for row in rows]
        finally:
            connection.close()

    def change(self, task_id, *, status=_UNSET, priority=_UNSET, due=_UNSET,
               title=_UNSET, project=_UNSET, details=_UNSET):
        updates = {}
        if status is not _UNSET:
            if status not in STATUSES:
                raise ValueError("Status must be open, done, or archived")
            updates["status"] = status
        if priority is not _UNSET:
            if priority not in PRIORITIES:
                raise ValueError("Priority must be low, normal, high, or urgent")
            updates["priority"] = priority
        if due is not _UNSET:
            updates["due"] = _due(due)
        for name, value, limit, required in (("title", title, 240, True),
                                             ("project", project, 120, False),
                                             ("details", details, 4000, False)):
            if value is not _UNSET:
                updates[name] = _text(value, name.title(), limit, required=required)
        if not updates:
            raise ValueError("No task changes supplied")
        updates["updated_at"] = datetime.now(self.timezone).isoformat(timespec="seconds")
        connection = self._connect()
        try:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            result = connection.execute(f"UPDATE tasks SET {assignments} WHERE id = ?",
                                        [*updates.values(), task_id])
            if result.rowcount != 1:
                raise ValueError("Task not found in this area")
            connection.commit()
        finally:
            connection.close()
        return self.get(task_id)

    def today(self, *, project=None):
        return self.list(due_through=datetime.now(self.timezone).date().isoformat(), project=project)

    def upcoming(self, days=7, *, project=None):
        if not isinstance(days, int) or not 1 <= days <= 90:
            raise ValueError("Days must be between 1 and 90")
        deadline = datetime.now(self.timezone).date() + timedelta(days=days)
        return self.list(due_through=deadline.isoformat(), project=project)

    def remember(self, key, value, *, kind="preference", project=""):
        project = memory_scope(kind, project)
        if kind != "preference":
            key = _text(key, "Memory name", 80, required=True)
            value = _text(value, "Memory value", 4000, required=True)
            stamp = datetime.now(self.timezone).isoformat(timespec="seconds")
            connection = self._connect()
            try:
                connection.execute("""INSERT INTO assistant_memory VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(kind, project, key) DO UPDATE SET
                    value=excluded.value, updated_at=excluded.updated_at""",
                    (kind, project, key, value, stamp))
                connection.commit()
            finally:
                connection.close()
            return {"area": self.area, "kind": kind, "project": project,
                    "key": key, "value": value, "updated_at": stamp}
        key = _text(key, "Preference name", 80, required=True)
        value = _text(value, "Preference value", 1000, required=True)
        stamp = datetime.now(self.timezone).isoformat(timespec="seconds")
        connection = self._connect()
        try:
            connection.execute("""INSERT INTO preferences (key, value, updated_at)
                VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET
                value=excluded.value, updated_at=excluded.updated_at""", (key, value, stamp))
            connection.commit()
        finally:
            connection.close()
        return {"area": self.area, "key": key, "value": value}

    def memories(self, *, kind=None, project=None):
        """Inspect saved memories, including legacy preferences, without model calls.

        No project filter lists all projects; an empty project lists area-wide
        entries only. Conversation selection is deliberately separate.
        """
        if kind is not None and kind not in MEMORY_KINDS:
            raise ValueError("Memory kind must be preference, profile, project, lesson, or example")
        if project is not None:
            project = _text(project, "Project", 120)
        connection = self._connect()
        try:
            records = [dict(row) | {"area": self.area} for row in connection.execute(
                "SELECT kind, project, key, value, updated_at FROM assistant_memory "
                "ORDER BY kind, project, key")]
            records += [dict(row) | {"area": self.area, "kind": "preference", "project": ""}
                        for row in connection.execute(
                            "SELECT key, value, updated_at FROM preferences ORDER BY key")]
            return sorted((item for item in records
                           if (kind is None or item["kind"] == kind)
                           and (project is None or item["project"] == project)),
                          key=lambda item: (item["kind"], item["project"], item["key"]))
        finally:
            connection.close()

    def preferences(self):
        connection = self._connect()
        try:
            return {row["key"]: row["value"] for row in
                    connection.execute("SELECT key, value FROM preferences ORDER BY key")}
        finally:
            connection.close()

    def forget(self, key, *, kind="preference", project=""):
        project = memory_scope(kind, project)
        key = _text(key, "Preference name", 80, required=True)
        connection = self._connect()
        try:
            if kind == "preference":
                result = connection.execute("DELETE FROM preferences WHERE key = ?", (key,))
            else:
                result = connection.execute(
                    "DELETE FROM assistant_memory WHERE kind = ? AND project = ? AND key = ?",
                    (kind, project, key))
            if result.rowcount != 1:
                raise ValueError("Preference not found in this area" if kind == "preference"
                                 else "Memory not found in this area and project")
            connection.commit()
        finally:
            connection.close()
