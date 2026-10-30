"""Warn before drafts and checkpoints land in a folder Git would not ignore."""

import shutil
import subprocess
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from src.utils.output_safety import unignored_output

ROOT = Path(__file__).resolve().parents[1]
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("output/\npartial/runs/\n")
    return root.resolve()


@needs_git
def test_ignored_output_folder_is_not_flagged(repo):
    assert unignored_output(repo / "output") is None
    assert unignored_output(repo / "output" / "my-docs") is None


@needs_git
def test_unignored_output_folder_is_flagged_even_before_it_exists(repo):
    assert not (repo / "my-docs").exists()
    assert unignored_output(repo / "my-docs") == repo
    assert not (repo / "my-docs").exists()


@needs_git
def test_partly_ignored_folder_is_flagged_for_exported_drafts(repo):
    # Checkpoints under runs/ are ignored, but exported Markdown would still be visible.
    assert unignored_output(repo / "partial") == repo


def test_folder_outside_a_repository_is_not_flagged(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    assert unignored_output(tmp_path / "plain") is None


def test_missing_git_is_not_flagged(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("git")
    monkeypatch.setattr(subprocess, "run", unavailable)
    assert unignored_output(tmp_path) is None


@needs_git
def test_shipped_default_output_folder_is_ignored():
    assert unignored_output(ROOT / "output") is None


@needs_git
@pytest.mark.parametrize("folder, warned", [("my-docs", True), ("output/my-docs", False)])
def test_generate_warns_before_preparing(repo, monkeypatch, folder, warned):
    from src import main
    monkeypatch.setattr(main, "console", Console(width=1000))
    result = CliRunner().invoke(main.app, ["generate", "Incident Management", "-f", "markdown",
                                           "--output", str(repo / folder)])
    assert result.exit_code == 0, result.output
    assert ("Warning: output folder" in result.output) == warned
    assert list((repo / folder / "claude_code").iterdir())
