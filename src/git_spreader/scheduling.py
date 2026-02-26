"""Time slot generation and commit scheduling for git-spreader."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from git_spreader.models import ScheduledCommit, ScoredCommit, SpreaderConfig, TimeSlot

DAY_ABBREVS = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' into (hour, minute)."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


def build_time_slots(
    start: datetime,
    end: datetime,
    config: SpreaderConfig,
) -> list[TimeSlot]:
    """Generate working-hour time slots between start and end dates.

    Creates one TimeSlot per working day within the date range,
    spanning the configured working hours.

    Args:
        start: Start of the scheduling range.
        end: End of the scheduling range.
        config: Configuration with working hours and days.

    Returns:
        List of TimeSlot objects for each working day.
    """
    work_start_h, work_start_m = _parse_time(config.working_hours_start)
    work_end_h, work_end_m = _parse_time(config.working_hours_end)

    # Detect midnight-crossing ranges (e.g. 22:00-04:00)
    start_minutes = work_start_h * 60 + work_start_m
    end_minutes = work_end_h * 60 + work_end_m
    crosses_midnight = end_minutes <= start_minutes

    working_day_nums = {DAY_ABBREVS[d] for d in config.working_days}

    slots: list[TimeSlot] = []
    current_date = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end.replace(hour=23, minute=59, second=59, microsecond=0)

    while current_date <= end_date:
        if current_date.weekday() in working_day_nums:
            slot_start = current_date.replace(hour=work_start_h, minute=work_start_m, second=0)
            if crosses_midnight:
                # End time is on the next day
                next_day = current_date + timedelta(days=1)
                slot_end = next_day.replace(hour=work_end_h, minute=work_end_m, second=0)
            else:
                slot_end = current_date.replace(hour=work_end_h, minute=work_end_m, second=0)
            if slot_start >= start and slot_end <= end + timedelta(days=1):
                slots.append(TimeSlot(start=slot_start, end=slot_end))
        current_date += timedelta(days=1)

    return slots


def schedule_commits(
    scored: list[ScoredCommit],
    slots: list[TimeSlot],
    config: SpreaderConfig,
    rng: random.Random,
) -> list[ScheduledCommit]:
    """Place scored commits into time slots by consuming gap time.

    Walks commits in order, consuming gap_minutes from available
    time slots. When a gap crosses a slot boundary, the commit
    wraps to the start of the next available slot.

    Args:
        scored: Scored commits with gap_minutes.
        slots: Available time slots.
        config: Configuration.
        rng: Random number generator for determinism.

    Returns:
        List of ScheduledCommit with new timestamps.
    """
    if not scored or not slots:
        return []

    scheduled: list[ScheduledCommit] = []
    slot_idx = 0
    cursor = slots[0].start  # current position in time

    for i, sc in enumerate(scored):
        if i == 0:
            # First commit: place at start of first slot with small offset
            offset = timedelta(minutes=rng.uniform(0, min(15, sc.gap_minutes)))
            commit_time = cursor + offset
            cursor = commit_time
        else:
            # Advance cursor by gap_minutes
            remaining_gap = timedelta(minutes=sc.gap_minutes)

            while remaining_gap > timedelta(0):
                if slot_idx >= len(slots):
                    # No more slots — place at end of last slot
                    cursor = slots[-1].end
                    remaining_gap = timedelta(0)
                    break

                current_slot = slots[slot_idx]

                # If cursor is before this slot, jump to slot start
                if cursor < current_slot.start:
                    cursor = current_slot.start

                # If cursor is past this slot, move to next
                if cursor >= current_slot.end:
                    slot_idx += 1
                    continue

                # How much time is left in this slot?
                time_left = current_slot.end - cursor
                if time_left >= remaining_gap:
                    cursor += remaining_gap
                    remaining_gap = timedelta(0)
                else:
                    remaining_gap -= time_left
                    slot_idx += 1
                    if slot_idx < len(slots):
                        cursor = slots[slot_idx].start

            commit_time = cursor

        scheduled.append(
            ScheduledCommit(
                commit=sc.commit,
                score=sc.score,
                gap_minutes=sc.gap_minutes,
                new_author_date=commit_time,
                new_committer_date=commit_time,
            )
        )

    return scheduled


def auto_end_date(
    scored: list[ScoredCommit],
    start: datetime,
    config: SpreaderConfig,
) -> datetime:
    """Estimate the end date needed to fit all commits.

    Calculates total gap time and estimates the number of working days
    needed, then adds buffer for weekends and realism modifiers.

    Args:
        scored: Scored commits with gap_minutes.
        start: Start date for scheduling.
        config: Configuration with working hours.

    Returns:
        Estimated end date.
    """
    if not scored:
        return start

    total_gap_minutes = sum(sc.gap_minutes for sc in scored)
    work_start_h, work_start_m = _parse_time(config.working_hours_start)
    work_end_h, work_end_m = _parse_time(config.working_hours_end)
    start_minutes = work_start_h * 60 + work_start_m
    end_minutes = work_end_h * 60 + work_end_m
    if end_minutes <= start_minutes:
        # Midnight-crossing range (e.g. 22:00-04:00 = 360 minutes)
        minutes_per_day = (24 * 60 - start_minutes) + end_minutes
    else:
        minutes_per_day = end_minutes - start_minutes

    if minutes_per_day <= 0:
        return start + timedelta(days=30)

    working_days_needed = total_gap_minutes / minutes_per_day
    # Add 30% buffer for days off, holidays, etc.
    calendar_days = int(working_days_needed * 1.3 * (7 / 5)) + 2
    return start + timedelta(days=calendar_days)


def compress_gaps(
    scored: list[ScoredCommit],
    available_minutes: float,
) -> list[ScoredCommit]:
    """Proportionally compress gaps to fit within available time.

    When total gap time exceeds available working time (and --end is set),
    all gaps are scaled down proportionally.

    Args:
        scored: Original scored commits.
        available_minutes: Total available working minutes.

    Returns:
        New list of ScoredCommit with compressed gap_minutes.
    """
    total = sum(sc.gap_minutes for sc in scored)
    if total <= 0 or total <= available_minutes:
        return scored

    ratio = available_minutes / total
    return [
        ScoredCommit(
            commit=sc.commit,
            score=sc.score,
            gap_minutes=sc.gap_minutes * ratio,
        )
        for sc in scored
    ]
