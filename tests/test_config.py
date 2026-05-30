"""Tests for the configuration system."""

from __future__ import annotations

from pathlib import Path

import tomli_w

from git_spreader.config import (
    _flatten_toml,
    load_config,
    show_config,
    write_default_config,
)
from git_spreader.models import SpreaderConfig


def test_defaults():
    config = load_config()
    assert config.working_hours_start == "09:00"
    assert config.working_hours_end == "17:00"
    assert config.min_gap_minutes == 10.0
    assert config.curve == "sqrt"


def test_cli_overrides():
    config = load_config(cli_overrides={"min_gap_minutes": 20, "curve": "linear"})
    assert config.min_gap_minutes == 20
    assert config.curve == "linear"


def test_cli_none_values_ignored():
    config = load_config(cli_overrides={"min_gap_minutes": None, "curve": "linear"})
    assert config.min_gap_minutes == 10.0  # Default, not None
    assert config.curve == "linear"


def test_flatten_toml_schedule():
    data = {
        "schedule": {
            "working_hours": {"start": "08:00", "end": "16:00"},
            "working_days": ["Mon", "Tue", "Wed"],
            "timezone": "Europe/London",
        }
    }
    flat = _flatten_toml(data)
    assert flat["working_hours_start"] == "08:00"
    assert flat["working_hours_end"] == "16:00"
    assert flat["working_days"] == ("Mon", "Tue", "Wed")
    assert flat["timezone"] == "Europe/London"


def test_flatten_toml_complexity():
    data = {
        "complexity": {
            "weights": {"lines": 0.7, "files": 0.2, "bytes": 0.1},
            "min_gap_minutes": 15,
            "max_gap_minutes": 300,
            "curve": "log",
        }
    }
    flat = _flatten_toml(data)
    assert flat["weight_lines"] == 0.7
    assert flat["min_gap_minutes"] == 15
    assert flat["curve"] == "log"


def test_flatten_toml_realism():
    data = {
        "realism": {
            "late_night_probability": 0.1,
            "jitter": {"min_offset_minutes": -10, "max_offset_minutes": 20},
            "holidays": {"calendar": "UK", "additional": ["2025-12-24"]},
        }
    }
    flat = _flatten_toml(data)
    assert flat["late_night_probability"] == 0.1
    assert flat["jitter_min_offset_minutes"] == -10
    assert flat["holiday_calendar"] == "UK"
    assert flat["holiday_additional"] == ("2025-12-24",)


def test_repo_config_overrides_global(tmp_path: Path):
    # Create a fake repo config
    repo_config = tmp_path / ".git-spreader.toml"
    toml_data = {"complexity": {"curve": "log", "min_gap_minutes": 25}}
    with open(repo_config, "wb") as f:
        tomli_w.dump(toml_data, f)

    config = load_config(repo_path=tmp_path)
    assert config.curve == "log"
    assert config.min_gap_minutes == 25


def test_write_default_config(tmp_path: Path):
    path = tmp_path / "config.toml"
    result = write_default_config(path)
    assert result == path
    assert path.exists()

    # Should be valid TOML that produces default config
    import tomllib

    with open(path, "rb") as f:
        data = tomllib.load(f)
    assert "schedule" in data
    assert "complexity" in data


def test_show_config():
    config = SpreaderConfig()
    output = show_config(config)
    assert "working_hours" in output
    assert "09:00" in output


def test_author_round_trips_through_show_config():
    """An author override must survive serialization back to TOML.

    Regression: _config_to_toml dropped the [author] section, so config --show
    never reflected an author override.
    """
    config = SpreaderConfig(author_name="Ada Lovelace", author_email="ada@example.com")
    output = show_config(config)
    assert "Ada Lovelace" in output
    assert "ada@example.com" in output


def test_show_config_omits_author_when_unset():
    """No [author] section is emitted when author fields are None (tomli_w
    cannot serialize None)."""
    output = show_config(SpreaderConfig())
    assert "[author]" not in output
