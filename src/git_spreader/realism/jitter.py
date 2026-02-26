"""Jitter modifier — adds random time offset to all timestamps."""

from __future__ import annotations

import random
from datetime import timedelta

from git_spreader.models import ScheduledCommit, SpreaderConfig
from git_spreader.realism import register_schedule


@register_schedule
class JitterModifier:
    """Adds random ±offset to all timestamps to avoid suspiciously round times."""

    def is_enabled(self, config: SpreaderConfig) -> bool:
        return config.jitter_min_offset_minutes != 0 or config.jitter_max_offset_minutes != 0

    def modify_schedule(
        self,
        scheduled: list[ScheduledCommit],
        config: SpreaderConfig,
        rng: random.Random,
    ) -> list[ScheduledCommit]:
        result = list(scheduled)
        for sc in result:
            offset_minutes = rng.uniform(
                config.jitter_min_offset_minutes,
                config.jitter_max_offset_minutes,
            )
            offset = timedelta(minutes=offset_minutes)
            # Also add random seconds for naturalness
            offset += timedelta(seconds=rng.randint(0, 59))
            sc.new_author_date = sc.new_author_date + offset
            sc.new_committer_date = sc.new_committer_date + offset

        # Ensure chronological order is maintained
        for i in range(1, len(result)):
            if result[i].new_author_date <= result[i - 1].new_author_date:
                result[i].new_author_date = result[i - 1].new_author_date + timedelta(seconds=30)
                result[i].new_committer_date = result[i].new_author_date

        return result
