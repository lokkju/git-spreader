"""Tests for the CLI."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

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


def test_working_days_flag(temp_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_repo)
    result = runner.invoke(
        app,
        [
            "preview",
            "HEAD~3..HEAD",
            "--start",
            "2025-03-01",
            "--seed",
            "42",
            "--working-days",
            "Mon,Tue,Wed",
        ],
    )
    assert result.exit_code == 0


def test_working_days_invalid(temp_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_repo)
    result = runner.invoke(
        app,
        [
            "preview",
            "HEAD~3..HEAD",
            "--start",
            "2025-03-01",
            "--working-days",
            "Mon,Xyz",
        ],
    )
    assert result.exit_code == 1
    assert "invalid day" in result.output.lower()


def test_profile_side_project(temp_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_repo)
    result = runner.invoke(
        app,
        [
            "preview",
            "HEAD~3..HEAD",
            "--start",
            "2025-03-01",
            "--seed",
            "42",
            "--profile",
            "side-project",
        ],
    )
    assert result.exit_code == 0


def test_profile_unknown(temp_repo: Path, monkeypatch):
    monkeypatch.chdir(temp_repo)
    result = runner.invoke(
        app,
        [
            "preview",
            "HEAD~3..HEAD",
            "--start",
            "2025-03-01",
            "--profile",
            "nonexistent",
        ],
    )
    assert result.exit_code == 1
    assert "unknown profile" in result.output.lower()


def test_default_timezone_is_local():
    """Default timezone should be the system's local timezone, not hardcoded.

    Regression: default was America/Los_Angeles regardless of system timezone.
    """
    from git_spreader.models import SpreaderConfig, _detect_local_timezone

    config = SpreaderConfig()
    # The default should match the system's detected local timezone
    ZoneInfo(config.timezone)  # must be a valid IANA name
    assert config.timezone == _detect_local_timezone()


def test_timezone_mismatch_warning(temp_repo: Path, monkeypatch):
    """When config timezone differs from local, a warning should be shown."""
    config_path = temp_repo / ".git-spreader.toml"
    config_path.write_text(
        '[schedule]\ntimezone = "Asia/Tokyo"\n'
        'working_hours = { start = "09:00", end = "17:00" }\n'
    )
    monkeypatch.chdir(temp_repo)
    result = runner.invoke(
        app,
        [
            "preview",
            "HEAD~3..HEAD",
            "--start",
            "2025-03-01",
            "--seed",
            "42",
        ],
    )
    assert result.exit_code == 0
    assert "timezone" in result.output.lower()


def test_timestamps_use_configured_timezone(temp_repo: Path, monkeypatch):
    """Timestamps should use the configured timezone, not hardcoded UTC.

    Regression: all timestamps were written with +0000 (UTC) regardless of
    the timezone setting in config.
    """
    # Write a repo config with America/Los_Angeles timezone
    config_path = temp_repo / ".git-spreader.toml"
    config_path.write_text(
        '[schedule]\ntimezone = "America/Los_Angeles"\n'
        'working_hours = { start = "09:00", end = "17:00" }\n'
    )
    monkeypatch.chdir(temp_repo)
    # Import internals to test the pipeline directly
    from git_spreader.cli import _run_pipeline

    scheduled, config, repo_path = _run_pipeline(
        commit_range="HEAD~3..HEAD",
        start="2025-03-01",
        end=None,
        working_hours=None,
        working_days=None,
        profile=None,
        seed=42,
        verbose=False,
    )
    assert config.timezone == "America/Los_Angeles"
    pst = ZoneInfo("America/Los_Angeles")
    for sc in scheduled:
        # Timestamps should carry the configured timezone, not UTC
        assert sc.new_author_date.tzinfo is not None
        offset = sc.new_author_date.utcoffset()
        assert offset is not None
        # PST is -8h, PDT is -7h; either way, not +0000
        assert offset.total_seconds() != 0, (
            f"Timestamp {sc.new_author_date} has UTC offset, "
            f"expected {pst} offset"
        )
