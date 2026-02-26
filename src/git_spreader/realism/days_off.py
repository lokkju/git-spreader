"""Random days off modifier — removes entire workdays by probability."""

from __future__ import annotations

import random

from git_spreader.models import SpreaderConfig, TimeSlot
from git_spreader.realism import register_slot


@register_slot
class RandomDaysOffModifier:
    """Randomly removes workday slots to prevent the 'committed every day' pattern."""

    def is_enabled(self, config: SpreaderConfig) -> bool:
        return config.random_day_off_probability > 0

    def modify_slots(
        self,
        slots: list[TimeSlot],
        config: SpreaderConfig,
        rng: random.Random,
    ) -> list[TimeSlot]:
        if len(slots) <= 1:
            return slots

        # Don't remove the first slot (need at least one to start)
        result = [slots[0]]
        for slot in slots[1:]:
            if rng.random() >= config.random_day_off_probability:
                result.append(slot)

        return result
