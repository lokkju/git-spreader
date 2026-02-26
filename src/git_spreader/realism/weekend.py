"""Weekend modifier — adds occasional commits on weekend days."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from git_spreader.models import ScheduledCommit, SpreaderConfig
from git_spreader.realism import register_schedule


@register_schedule
class WeekendModifier:
    """Adds 1-3 commits to weekend days with shifted hours (10:00-15:00)."""

    WEEKEND_START_HOUR = 10
    WEEKEND_END_HOUR = 15

    def is_enabled(self, config: SpreaderConfig) -> bool:
        return config.weekend_probability > 0

    def modify_schedule(
        self,
        scheduled: list[ScheduledCommit],
        config: SpreaderConfig,
        rng: random.Random,
    ) -> list[ScheduledCommit]:
        if not scheduled:
            return scheduled

        result = list(scheduled)

        # Find the date range
        min_date = min(sc.new_author_date for sc in result).date()
        max_date = max(sc.new_author_date for sc in result).date()

        # Find weekend days in range
        current = min_date
        while current <= max_date:
            if current.weekday() in (5, 6):  # Saturday, Sunday
                if rng.random() < config.weekend_probability:
                    # Move 1-3 low-score commits to this weekend day
                    n_to_move = rng.randint(1, min(3, len(result)))
                    # Pick from lower-scoring commits
                    candidates = sorted(range(len(result)), key=lambda i: result[i].score)
                    to_move = candidates[:n_to_move]

                    for idx in to_move:
                        hour = rng.randint(self.WEEKEND_START_HOUR, self.WEEKEND_END_HOUR - 1)
                        minute = rng.randint(0, 59)
                        tz = result[idx].new_author_date.tzinfo
                        new_time = datetime(
                            current.year,
                            current.month,
                            current.day,
                            hour,
                            minute,
                            rng.randint(0, 59),
                            tzinfo=tz,
                        )
                        result[idx].new_author_date = new_time
                        result[idx].new_committer_date = new_time

            current += timedelta(days=1)

        return result
