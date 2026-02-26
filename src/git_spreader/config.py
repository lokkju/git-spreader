"""Configuration loading and management for git-spreader."""

from __future__ import annotations

import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any

import tomli_w

from git_spreader.models import SpreaderConfig

DEFAULTS = SpreaderConfig()

GLOBAL_CONFIG_DIR = Path.home() / ".config" / "git-spreader"
GLOBAL_CONFIG_PATH = GLOBAL_CONFIG_DIR / "config.toml"
REPO_CONFIG_NAME = ".git-spreader.toml"


def _flatten_toml(data: dict[str, Any]) -> dict[str, Any]:
    """Map nested TOML structure to flat SpreaderConfig field names."""
    flat: dict[str, Any] = {}

    schedule = data.get("schedule", {})
    if "working_hours" in schedule:
        wh = schedule["working_hours"]
        if "start" in wh:
            flat["working_hours_start"] = wh["start"]
        if "end" in wh:
            flat["working_hours_end"] = wh["end"]
    if "working_days" in schedule:
        flat["working_days"] = tuple(schedule["working_days"])
    if "timezone" in schedule:
        flat["timezone"] = schedule["timezone"]

    realism = data.get("realism", {})
    for key in (
        "late_night_probability",
        "weekend_probability",
        "random_day_off_probability",
        "flow_state_clustering",
        "avoid_holidays",
        "holiday_calendar",
    ):
        if key in realism:
            flat[key] = realism[key]

    holidays_section = realism.get("holidays", {})
    if "calendar" in holidays_section:
        flat["holiday_calendar"] = holidays_section["calendar"]
    if "additional" in holidays_section:
        flat["holiday_additional"] = tuple(holidays_section["additional"])

    jitter = realism.get("jitter", {})
    if "min_offset_minutes" in jitter:
        flat["jitter_min_offset_minutes"] = jitter["min_offset_minutes"]
    if "max_offset_minutes" in jitter:
        flat["jitter_max_offset_minutes"] = jitter["max_offset_minutes"]

    complexity = data.get("complexity", {})
    weights = complexity.get("weights", {})
    if "lines" in weights:
        flat["weight_lines"] = weights["lines"]
    if "files" in weights:
        flat["weight_files"] = weights["files"]
    if "bytes" in weights:
        flat["weight_bytes"] = weights["bytes"]
    if "min_gap_minutes" in complexity:
        flat["min_gap_minutes"] = complexity["min_gap_minutes"]
    if "max_gap_minutes" in complexity:
        flat["max_gap_minutes"] = complexity["max_gap_minutes"]
    if "curve" in complexity:
        flat["curve"] = complexity["curve"]

    author = data.get("author", {})
    if "name" in author:
        flat["author_name"] = author["name"]
    if "email" in author:
        flat["author_email"] = author["email"]

    return flat


def _load_toml_file(path: Path) -> dict[str, Any]:
    """Load and flatten a TOML config file, returning empty dict if not found."""
    if not path.is_file():
        return {}
    with open(path, "rb") as f:
        return _flatten_toml(tomllib.load(f))


def _config_to_toml(config: SpreaderConfig) -> dict[str, Any]:
    """Convert a SpreaderConfig to nested TOML structure."""
    return {
        "schedule": {
            "working_hours": {
                "start": config.working_hours_start,
                "end": config.working_hours_end,
            },
            "working_days": list(config.working_days),
            "timezone": config.timezone,
        },
        "realism": {
            "late_night_probability": config.late_night_probability,
            "weekend_probability": config.weekend_probability,
            "random_day_off_probability": config.random_day_off_probability,
            "flow_state_clustering": config.flow_state_clustering,
            "avoid_holidays": config.avoid_holidays,
            "jitter": {
                "min_offset_minutes": config.jitter_min_offset_minutes,
                "max_offset_minutes": config.jitter_max_offset_minutes,
            },
            "holidays": {
                "calendar": config.holiday_calendar,
                "additional": list(config.holiday_additional),
            },
        },
        "complexity": {
            "weights": {
                "lines": config.weight_lines,
                "files": config.weight_files,
                "bytes": config.weight_bytes,
            },
            "min_gap_minutes": config.min_gap_minutes,
            "max_gap_minutes": config.max_gap_minutes,
            "curve": config.curve,
        },
    }


def load_config(
    repo_path: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
    profile_overrides: dict[str, Any] | None = None,
) -> SpreaderConfig:
    """Load config with precedence: CLI > profile > repo config > global config > defaults."""
    base = asdict(DEFAULTS)

    # Layer 1: global config
    global_overrides = _load_toml_file(GLOBAL_CONFIG_PATH)
    base.update(global_overrides)

    # Layer 2: repo config
    if repo_path is not None:
        repo_config_path = repo_path / REPO_CONFIG_NAME
        repo_overrides = _load_toml_file(repo_config_path)
        base.update(repo_overrides)

    # Layer 3: profile overrides
    if profile_overrides:
        base.update({k: v for k, v in profile_overrides.items() if v is not None})

    # Layer 4: CLI overrides
    if cli_overrides:
        # Filter out None values (unset CLI flags)
        base.update({k: v for k, v in cli_overrides.items() if v is not None})

    # Convert tuple fields
    if isinstance(base.get("working_days"), list):
        base["working_days"] = tuple(base["working_days"])
    if isinstance(base.get("holiday_additional"), list):
        base["holiday_additional"] = tuple(base["holiday_additional"])

    return SpreaderConfig(**base)


def write_default_config(path: Path | None = None) -> Path:
    """Write default config to the given path (or global config path)."""
    target = path or GLOBAL_CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    toml_data = _config_to_toml(DEFAULTS)
    with open(target, "wb") as f:
        tomli_w.dump(toml_data, f)
    return target


def show_config(config: SpreaderConfig) -> str:
    """Return the current config as a TOML string."""
    toml_data = _config_to_toml(config)
    return tomli_w.dumps(toml_data)
