"""Data models for git-spreader."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class CommitInfo:
    """Raw commit information extracted from git."""

    sha: str
    author_name: str
    author_email: str
    author_date: datetime
    committer_name: str
    committer_email: str
    committer_date: datetime
    subject: str
    lines_changed: int  # insertions + deletions
    files_touched: int
    diff_bytes: int
    parent_shas: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScoredCommit:
    """A commit with its normalized complexity score and computed gap."""

    commit: CommitInfo
    score: float  # 0.0 to 1.0
    gap_minutes: float


@dataclass
class ScheduledCommit:
    """A commit with its new timestamps assigned by the scheduling engine."""

    commit: CommitInfo
    score: float
    gap_minutes: float
    new_author_date: datetime
    new_committer_date: datetime


@dataclass(frozen=True)
class TimeSlot:
    """A continuous block of available working time."""

    start: datetime
    end: datetime

    @property
    def duration_minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60


def _detect_local_timezone() -> str:
    """Detect the system's local IANA timezone name.

    Tries in order: $TZ env var, /etc/timezone, /etc/localtime symlink.
    Falls back to UTC if detection fails.
    """
    # 1. TZ environment variable
    tz_env = os.environ.get("TZ")
    if tz_env and "/" in tz_env:
        return tz_env

    # 2. /etc/timezone (Debian/Ubuntu)
    etc_timezone = Path("/etc/timezone")
    if etc_timezone.is_file():
        try:
            name = etc_timezone.read_text().strip()
            if name:
                return name
        except OSError:
            pass

    # 3. /etc/localtime symlink (most Linux, macOS)
    try:
        link = os.readlink("/etc/localtime")
        parts = link.split("zoneinfo/")
        if len(parts) > 1:
            return parts[-1]
    except OSError:
        pass

    return "UTC"


@dataclass(frozen=True)
class SpreaderConfig:
    """All configuration for a git-spreader run."""

    # Schedule
    working_hours_start: str = "09:00"
    working_hours_end: str = "17:00"
    working_days: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri")
    timezone: str = field(default_factory=_detect_local_timezone)

    # Complexity scoring
    weight_lines: float = 0.5
    weight_files: float = 0.3
    weight_bytes: float = 0.2
    min_gap_minutes: float = 10.0
    max_gap_minutes: float = 480.0
    curve: str = "sqrt"  # "sqrt", "linear", "log"

    # Realism
    late_night_probability: float = 0.05
    weekend_probability: float = 0.08
    random_day_off_probability: float = 0.10
    flow_state_clustering: bool = True
    avoid_holidays: bool = True
    holiday_calendar: str = "US"
    holiday_additional: tuple[str, ...] = ()

    # Jitter
    jitter_min_offset_minutes: float = -5.0
    jitter_max_offset_minutes: float = 10.0

    # Author override
    author_name: str | None = None
    author_email: str | None = None
