"""Tests for the scheduling engine."""

from __future__ import annotations

import random
from datetime import UTC, datetime

from git_spreader.models import ScoredCommit, SpreaderConfig, TimeSlot
from git_spreader.scheduling import (
    auto_end_date,
    build_time_slots,
    compress_gaps,
    schedule_commits,
)
from tests.test_scoring import _make_commit


def test_build_time_slots_weekdays_only():
    config = SpreaderConfig()
    start = datetime(2025, 2, 3, tzinfo=UTC)  # Monday
    end = datetime(2025, 2, 9, tzinfo=UTC)  # Sunday
    slots = build_time_slots(start, end, config)
    # Mon-Fri = 5 working days
    assert len(slots) == 5
    # All should be 9:00-17:00
    for s in slots:
        assert s.start.hour == 9
        assert s.end.hour == 17


def test_build_time_slots_empty_range():
    config = SpreaderConfig()
    start = datetime(2025, 2, 8, tzinfo=UTC)  # Saturday
    end = datetime(2025, 2, 9, tzinfo=UTC)  # Sunday
    slots = build_time_slots(start, end, config)
    assert len(slots) == 0


def test_schedule_commits_basic():
    config = SpreaderConfig()
    rng = random.Random(42)

    # Create a slot: one 8-hour day
    slot = TimeSlot(
        start=datetime(2025, 2, 3, 9, 0, tzinfo=UTC),
        end=datetime(2025, 2, 3, 17, 0, tzinfo=UTC),
    )

    scored = [
        ScoredCommit(commit=_make_commit(sha="c0"), score=0.1, gap_minutes=30),
        ScoredCommit(commit=_make_commit(sha="c1"), score=0.5, gap_minutes=60),
        ScoredCommit(commit=_make_commit(sha="c2"), score=0.2, gap_minutes=30),
    ]

    result = schedule_commits(scored, [slot], config, rng)
    assert len(result) == 3
    # All should be within the slot
    for sc in result:
        assert sc.new_author_date >= slot.start
        assert sc.new_author_date <= slot.end
    # Should be in chronological order
    for i in range(1, len(result)):
        assert result[i].new_author_date >= result[i - 1].new_author_date


def test_schedule_commits_wraps_across_days():
    config = SpreaderConfig()
    rng = random.Random(42)

    slots = [
        TimeSlot(
            start=datetime(2025, 2, 3, 9, 0, tzinfo=UTC),
            end=datetime(2025, 2, 3, 10, 0, tzinfo=UTC),  # Only 1 hour
        ),
        TimeSlot(
            start=datetime(2025, 2, 4, 9, 0, tzinfo=UTC),
            end=datetime(2025, 2, 4, 17, 0, tzinfo=UTC),
        ),
    ]

    # Total gap: 120 min > first slot's 60 min
    scored = [
        ScoredCommit(commit=_make_commit(sha="c0"), score=0.1, gap_minutes=10),
        ScoredCommit(commit=_make_commit(sha="c1"), score=0.5, gap_minutes=120),
    ]

    result = schedule_commits(scored, slots, config, rng)
    assert len(result) == 2
    # Second commit should be on the next day
    assert result[1].new_author_date.day == 4


def test_compress_gaps():
    scored = [
        ScoredCommit(commit=_make_commit(sha="c0"), score=0.5, gap_minutes=100),
        ScoredCommit(commit=_make_commit(sha="c1"), score=0.5, gap_minutes=100),
    ]
    compressed = compress_gaps(scored, 100)  # Only 100 min available for 200 total
    assert len(compressed) == 2
    total = sum(sc.gap_minutes for sc in compressed)
    assert abs(total - 100) < 0.01


def test_compress_gaps_no_compression_needed():
    scored = [
        ScoredCommit(commit=_make_commit(sha="c0"), score=0.5, gap_minutes=50),
    ]
    result = compress_gaps(scored, 100)
    assert result[0].gap_minutes == 50  # Unchanged


def test_auto_end_date():
    config = SpreaderConfig()
    start = datetime(2025, 2, 3, tzinfo=UTC)
    scored = [
        ScoredCommit(commit=_make_commit(sha="c0"), score=0.5, gap_minutes=480),
        ScoredCommit(commit=_make_commit(sha="c1"), score=0.5, gap_minutes=480),
    ]
    end = auto_end_date(scored, start, config)
    # Should be after start
    assert end > start


def test_build_time_slots_midnight_crossing():
    """Hours like 22:00-04:00 should produce slots that span into the next day."""
    config = SpreaderConfig(
        working_hours_start="22:00",
        working_hours_end="04:00",
        working_days=("Mon", "Tue", "Wed", "Thu", "Fri"),
    )
    start = datetime(2025, 2, 3, tzinfo=UTC)  # Monday
    end = datetime(2025, 2, 5, tzinfo=UTC)  # Wednesday
    slots = build_time_slots(start, end, config)
    assert len(slots) > 0
    for s in slots:
        assert s.end > s.start
        assert s.duration_minutes > 0
        # 22:00-04:00 = 6 hours = 360 minutes
        assert abs(s.duration_minutes - 360) < 1


def test_auto_end_date_midnight_crossing():
    """auto_end_date should compute positive minutes_per_day for midnight-crossing hours."""
    config = SpreaderConfig(
        working_hours_start="22:00",
        working_hours_end="04:00",
        working_days=("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    )
    start = datetime(2025, 2, 3, tzinfo=UTC)
    scored = [
        ScoredCommit(commit=_make_commit(sha="c0"), score=0.5, gap_minutes=120),
        ScoredCommit(commit=_make_commit(sha="c1"), score=0.5, gap_minutes=120),
    ]
    end = auto_end_date(scored, start, config)
    assert end > start
    # Should not return the 30-day fallback
    assert (end - start).days < 30


def test_build_time_slots_midnight_crossing_boundary():
    """Midnight-crossing slots on the last day of the range must not be excluded.

    Regression: 19:00-02:00 with --end Feb 26 produced slot_end = Feb 27 02:00
    which exceeded the boundary check (end + 1 day = Feb 27 00:00) and was dropped.
    """
    config = SpreaderConfig(
        working_hours_start="19:00",
        working_hours_end="02:00",
        working_days=("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    )
    start = datetime(2025, 2, 10, tzinfo=UTC)
    end = datetime(2025, 2, 26, tzinfo=UTC)
    slots = build_time_slots(start, end, config)
    # Should get a slot for every day in the range (17 days)
    assert len(slots) == 17
    # All slots should have 7 hours = 420 minutes of duration
    for s in slots:
        assert s.end > s.start
        assert abs(s.duration_minutes - 420) < 1


def test_midnight_crossing_no_negative_available_time():
    """With midnight-crossing hours and --end, available time must not be negative.

    Regression: 19:00-02:00 produced -15300m available time, compressing all commits.
    """
    config = SpreaderConfig(
        working_hours_start="19:00",
        working_hours_end="02:00",
        working_days=("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    )
    start = datetime(2025, 2, 10, tzinfo=UTC)
    end = datetime(2025, 2, 26, tzinfo=UTC)
    slots = build_time_slots(start, end, config)
    total_minutes = sum(s.duration_minutes for s in slots)
    # 17 days * 7 hours = 7140 minutes (all days must be included)
    assert total_minutes > 0
    assert total_minutes >= 17 * 420
