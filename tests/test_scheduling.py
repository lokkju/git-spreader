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
