"""Synthetic memory scenarios verify personalization context without paid calls."""

import sqlite3

import pytest
from typer.testing import CliRunner

from src.main import app
from src.utils.config import config_manager
from src.utils.tasks import TaskStore


def test_existing_preferences_survive_additive_schema(tmp_path):
    path = tmp_path / "work.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")
        connection.execute("INSERT INTO preferences VALUES ('tone', 'Brief', '2026-01-01')")
    store = TaskStore(tmp_path, "work")
    store.remember("role", "IT consultant", kind="profile")
    assert store.preferences() == {"tone": "Brief"}
    assert {row["kind"] for row in store.memories()} == {"preference", "profile"}
    assert store.memories(kind="profile")[0]["value"] == "IT consultant"


def test_memory_edit_delete_and_scope_do_not_collide(tmp_path):
    store = TaskStore(tmp_path, "work")
    store.remember("goal", "Area preference")
    store.remember("goal", "Original", kind="project", project="Alpha")
    store.remember("goal", "Separate", kind="project", project="Beta")
    store.remember("goal", "Updated", kind="project", project="Alpha")
    store.remember("language", "العربية", kind="profile")
    reloaded = TaskStore(tmp_path, "work")
    assert reloaded.memories(project="Alpha")[0]["value"] == "Updated"
    assert reloaded.memories(kind="profile")[0]["value"] == "العربية"
    assert reloaded.preferences() == {"goal": "Area preference"}
    reloaded.forget("goal", kind="project", project="Alpha")
    assert reloaded.memories(project="Alpha") == []
    assert reloaded.memories(project="Beta")[0]["value"] == "Separate"
    assert TaskStore(tmp_path, "personal").memories() == []
    with pytest.raises(ValueError, match="not found"):
        reloaded.forget("goal", kind="project", project="Alpha")


@pytest.mark.parametrize("kwargs", [
    {"kind": "unknown"}, {"kind": "project"},
    {"kind": "profile", "project": "Alpha"},
    {"kind": "preference", "project": "Alpha"},
    {"kind": "project", "project": "a" * 121},
    {"kind": "lesson", "project": "Alpha\x00"},
])
def test_invalid_memory_scope_does_not_save(tmp_path, kwargs):
    store = TaskStore(tmp_path, "work")
    with pytest.raises(ValueError):
        store.remember("key", "value", **kwargs)
    assert store.memories() == []


@pytest.mark.parametrize("key,value", [("", "value"), ("a" * 81, "value"),
                                      ("key", ""), ("key", "a" * 4001),
                                      ("key", "value\x00")])
def test_invalid_memory_text_does_not_save(tmp_path, key, value):
    store = TaskStore(tmp_path, "work")
    with pytest.raises(ValueError):
        store.remember(key, value, kind="lesson")
    assert store.memories() == []


def test_cli_project_memory_and_legacy_preferences_are_compatible(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager.system_config, "task_data_dir", tmp_path)
    runner = CliRunner()
    commands = [
        ["memory", "set", "tone", "Brief", "--area", "work"],
        ["memory", "set", "role", "IT consultant", "--kind", "profile", "--area", "work"],
        ["memory", "set", "goal", "Roll out MFA", "--kind", "project", "--project", "Alpha", "--area", "work"],
    ]
    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code == 0, result.output
    listing = runner.invoke(app, ["memory", "list", "--area", "work", "--project", "Alpha"])
    assert listing.exit_code == 0 and "Roll out MFA" in listing.output
    assert "IT consultant" not in listing.output
    deleted = runner.invoke(app, ["memory", "forget", "goal", "--kind", "project", "--project", "Alpha", "--area", "work"])
    assert deleted.exit_code == 0, deleted.output
    invalid = runner.invoke(app, ["memory", "set", "goal", "No scope", "--kind", "project", "--area", "work"])
    assert invalid.exit_code == 2 and "requires --project" in invalid.output


