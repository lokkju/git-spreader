"""Realism engine: modifier protocols, registry, and apply functions."""

from __future__ import annotations

import random
from datetime import timedelta
from typing import Protocol, runtime_checkable

from git_spreader.models import ScheduledCommit, SpreaderConfig, TimeSlot


@runtime_checkable
class SlotModifier(Protocol):
    """Modifies time slots before scheduling (e.g., remove holidays, days off)."""

    def is_enabled(self, config: SpreaderConfig) -> bool: ...

    def modify_slots(
        self,
        slots: list[TimeSlot],
        config: SpreaderConfig,
        rng: random.Random,
    ) -> list[TimeSlot]: ...


@runtime_checkable
class ScheduleModifier(Protocol):
    """Modifies scheduled commits after scheduling (e.g., jitter, clustering)."""

    def is_enabled(self, config: SpreaderConfig) -> bool: ...

    def modify_schedule(
        self,
        scheduled: list[ScheduledCommit],
        config: SpreaderConfig,
        rng: random.Random,
    ) -> list[ScheduledCommit]: ...


# Registries
_slot_modifiers: list[type] = []
_schedule_modifiers: list[type] = []


def register_slot(cls: type) -> type:
    """Decorator to register a SlotModifier class."""
    _slot_modifiers.append(cls)
    return cls


def register_schedule(cls: type) -> type:
    """Decorator to register a ScheduleModifier class."""
    _schedule_modifiers.append(cls)
    return cls


def apply_slot_modifiers(
    slots: list[TimeSlot],
    config: SpreaderConfig,
    rng: random.Random,
) -> list[TimeSlot]:
    """Apply all registered and enabled slot modifiers."""
    # Ensure modifiers are imported/registered
    _ensure_registered()
    for modifier_cls in _slot_modifiers:
        modifier = modifier_cls()
        if modifier.is_enabled(config):
            slots = modifier.modify_slots(slots, config, rng)
    return slots


def _enforce_monotonicity(scheduled: list[ScheduledCommit]) -> list[ScheduledCommit]:
    """Ensure timestamps are monotonically non-decreasing.

    If a commit's timestamp is earlier than the previous commit's,
    push it forward to 30 seconds after the previous commit.
    """
    for i in range(1, len(scheduled)):
        if scheduled[i].new_author_date < scheduled[i - 1].new_author_date:
            new_time = scheduled[i - 1].new_author_date + timedelta(seconds=30)
            scheduled[i].new_author_date = new_time
            scheduled[i].new_committer_date = new_time
    return scheduled


def apply_schedule_modifiers(
    scheduled: list[ScheduledCommit],
    config: SpreaderConfig,
    rng: random.Random,
) -> list[ScheduledCommit]:
    """Apply all registered and enabled schedule modifiers."""
    _ensure_registered()
    for modifier_cls in _schedule_modifiers:
        modifier = modifier_cls()
        if modifier.is_enabled(config):
            scheduled = modifier.modify_schedule(scheduled, config, rng)
    # Enforce monotonicity after all modifiers to prevent timestamp inversions
    scheduled = _enforce_monotonicity(scheduled)
    return scheduled


_registered = False


def _ensure_registered() -> None:
    """Import modifier modules to trigger registration."""
    global _registered
    if _registered:
        return
    _registered = True
    # Import all modifier modules to trigger @register_slot/@register_schedule
    import git_spreader.realism.days_off  # noqa: F401
    import git_spreader.realism.flow_state  # noqa: F401
    import git_spreader.realism.holidays  # noqa: F401
    import git_spreader.realism.jitter  # noqa: F401
    import git_spreader.realism.late_night  # noqa: F401
    import git_spreader.realism.weekend  # noqa: F401
