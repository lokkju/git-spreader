"""Built-in scheduling profiles for git-spreader."""

from __future__ import annotations

from typing import Any

PROFILES: dict[str, dict[str, Any]] = {
    "default": {
        "working_hours_start": "09:00",
        "working_hours_end": "17:00",
        "working_days": ("Mon", "Tue", "Wed", "Thu", "Fri"),
    },
    "night-owl": {
        "working_hours_start": "22:00",
        "working_hours_end": "04:00",
        "working_days": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        "late_night_probability": 0.0,
        "weekend_probability": 0.0,
        "random_day_off_probability": 0.15,
    },
    "side-project": {
        "working_hours_start": "18:00",
        "working_hours_end": "23:00",
        "working_days": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        "late_night_probability": 0.15,
        "weekend_probability": 0.0,
        "random_day_off_probability": 0.20,
    },
    "weekend-warrior": {
        "working_hours_start": "09:00",
        "working_hours_end": "18:00",
        "working_days": ("Sat", "Sun"),
        "late_night_probability": 0.10,
        "weekend_probability": 0.0,
        "random_day_off_probability": 0.05,
    },
}


def get_profile(name: str) -> dict[str, Any]:
    """Get a profile by name. Raises KeyError if not found."""
    if name not in PROFILES:
        available = ", ".join(sorted(PROFILES.keys()))
        msg = f"Unknown profile '{name}'. Available profiles: {available}"
        raise KeyError(msg)
    return dict(PROFILES[name])
