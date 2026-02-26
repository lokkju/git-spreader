"""Tests for the CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from git_spreader.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "git-spreader" in result.output


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    # Typer returns exit code 0 or 2 for help display
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "git-spreader" in result.output


def test_preview_in_temp_repo(temp_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_repo)
    result = runner.invoke(
        app,
        ["preview", "HEAD~3..HEAD", "--start", "2025-03-01", "--seed", "42"],
    )
    assert result.exit_code == 0
    assert "Preview" in result.output or "Score" in result.output


def test_config_show(temp_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_repo)
    result = runner.invoke(app, ["config", "--show"])
    assert result.exit_code == 0
    assert "09:00" in result.output


def test_config_reset(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # Need to also be in a valid git repo for config --reset
    result = runner.invoke(app, ["config", "--reset"])
    assert result.exit_code == 0
    assert "reset" in result.output.lower() or "defaults" in result.output.lower()
