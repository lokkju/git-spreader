"""Tests for the realism engine modifiers."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from git_spreader.models import ScheduledCommit, SpreaderConfig, TimeSlot
from git_spreader.realism.days_off import RandomDaysOffModifier
from git_spreader.realism.flow_state import FlowStateModifier
from git_spreader.realism.holidays import HolidayModifier
from git_spreader.realism.jitter import JitterModifier
from git_spreader.realism.late_night import LateNightModifier
from git_spreader.realism.weekend import WeekendModifier
from tests.test_scoring import _make_commit


def _make_scheduled(
    sha: str = "abc",
    dt: datetime | None = None,
    score: float = 0.5,
) -> ScheduledCommit:
    if dt is None:
        dt = datetime(2025, 2, 3, 10, 0, tzinfo=UTC)
    return ScheduledCommit(
        commit=_make_commit(sha=sha, lines=10, files=1, diff_bytes=100),
        score=score,
        gap_minutes=30,
        new_author_date=dt,
        new_committer_date=dt,
    )


def _make_slots(start_date: datetime, n_days: int = 5) -> list[TimeSlot]:
    slots = []
    for i in range(n_days):
        day = start_date + timedelta(days=i)
        slots.append(
            TimeSlot(
                start=day.replace(hour=9, minute=0),
                end=day.replace(hour=17, minute=0),
            )
        )
    return slots


class TestHolidayModifier:
    def test_enabled_by_default(self):
        mod = HolidayModifier()
        assert mod.is_enabled(SpreaderConfig())

    def test_disabled(self):
        mod = HolidayModifier()
        assert not mod.is_enabled(SpreaderConfig(avoid_holidays=False))

    def test_removes_us_holidays(self):
        mod = HolidayModifier()
        rng = random.Random(42)
        config = SpreaderConfig(holiday_calendar="US")
        # Jan 1 is New Year's Day
        slots = _make_slots(datetime(2025, 1, 1, tzinfo=UTC), n_days=3)
        result = mod.modify_slots(slots, config, rng)
        dates = {s.start.date() for s in result}
        from datetime import date

        assert date(2025, 1, 1) not in dates


class TestRandomDaysOff:
    def test_enabled(self):
        mod = RandomDaysOffModifier()
        assert mod.is_enabled(SpreaderConfig(random_day_off_probability=0.1))

    def test_disabled_when_zero(self):
        mod = RandomDaysOffModifier()
        assert not mod.is_enabled(SpreaderConfig(random_day_off_probability=0.0))

    def test_preserves_first_slot(self):
        mod = RandomDaysOffModifier()
        rng = random.Random(42)
        config = SpreaderConfig(random_day_off_probability=0.99)
        slots = _make_slots(datetime(2025, 2, 3, tzinfo=UTC), n_days=10)
        result = mod.modify_slots(slots, config, rng)
        # First slot always preserved
        assert result[0].start == slots[0].start
        # Should have removed some slots
        assert len(result) < len(slots)

    def test_single_slot_unchanged(self):
        mod = RandomDaysOffModifier()
        rng = random.Random(42)
        config = SpreaderConfig(random_day_off_probability=0.99)
        slots = _make_slots(datetime(2025, 2, 3, tzinfo=UTC), n_days=1)
        result = mod.modify_slots(slots, config, rng)
        assert len(result) == 1


class TestFlowState:
    def test_enabled_by_default(self):
        mod = FlowStateModifier()
        assert mod.is_enabled(SpreaderConfig())

    def test_disabled(self):
        mod = FlowStateModifier()
        assert not mod.is_enabled(SpreaderConfig(flow_state_clustering=False))

    def test_clusters_commits(self):
        mod = FlowStateModifier()
        rng = random.Random(42)
        config = SpreaderConfig()
        # Create 10 commits spaced 60 minutes apart
        base = datetime(2025, 2, 3, 9, 0, tzinfo=UTC)
        scheduled = [
            _make_scheduled(sha=f"c{i}", dt=base + timedelta(minutes=60 * i)) for i in range(10)
        ]
        result = mod.modify_schedule(scheduled, config, rng)
        assert len(result) == 10
        # Some gaps should be compressed (< 60 min)
        gaps = [
            (result[i].new_author_date - result[i - 1].new_author_date).total_seconds() / 60
            for i in range(1, len(result))
        ]
        assert any(g < 60 for g in gaps)


class TestJitter:
    def test_enabled_with_nonzero_offsets(self):
        mod = JitterModifier()
        assert mod.is_enabled(SpreaderConfig())

    def test_disabled_when_both_zero(self):
        mod = JitterModifier()
        assert not mod.is_enabled(
            SpreaderConfig(jitter_min_offset_minutes=0, jitter_max_offset_minutes=0)
        )

    def test_maintains_order(self):
        mod = JitterModifier()
        rng = random.Random(42)
        config = SpreaderConfig()
        base = datetime(2025, 2, 3, 9, 0, tzinfo=UTC)
        scheduled = [
            _make_scheduled(sha=f"c{i}", dt=base + timedelta(minutes=5 * i)) for i in range(10)
        ]
        result = mod.modify_schedule(scheduled, config, rng)
        for i in range(1, len(result)):
            assert result[i].new_author_date > result[i - 1].new_author_date

    def test_timestamps_change(self):
        mod = JitterModifier()
        rng = random.Random(42)
        config = SpreaderConfig()
        base = datetime(2025, 2, 3, 9, 0, tzinfo=UTC)
        original_dates = [base, base + timedelta(hours=1)]
        scheduled = [
            _make_scheduled(sha="c0", dt=original_dates[0]),
            _make_scheduled(sha="c1", dt=original_dates[1]),
        ]
        result = mod.modify_schedule(scheduled, config, rng)
        # At least one timestamp should have changed from the original
        changed = any(result[i].new_author_date != original_dates[i] for i in range(len(result)))
        assert changed


class TestLateNight:
    def test_enabled(self):
        mod = LateNightModifier()
        assert mod.is_enabled(SpreaderConfig())

    def test_disabled_when_zero(self):
        mod = LateNightModifier()
        assert not mod.is_enabled(SpreaderConfig(late_night_probability=0.0))


class TestWeekend:
    def test_enabled(self):
        mod = WeekendModifier()
        assert mod.is_enabled(SpreaderConfig())

    def test_disabled_when_zero(self):
        mod = WeekendModifier()
        assert not mod.is_enabled(SpreaderConfig(weekend_probability=0.0))
