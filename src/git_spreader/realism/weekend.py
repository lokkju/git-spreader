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

        # Track commits already relocated so none is moved to two weekend days.
        moved: set[int] = set()

        # Find weekend days in range
        current = min_date
        while current <= max_date:
            if current.weekday() in (5, 6):  # Saturday, Sunday
                if rng.random() < config.weekend_probability:
                    # Only consider commits scheduled near this weekend (within a
                    # few days), so a commit lands close to where it would have
                    # been rather than being yanked across the whole range.
                    candidates = [
                        i
                        for i in range(len(result))
                        if i not in moved
                        and abs((result[i].new_author_date.date() - current).days) <= 3
                    ]
                    if not candidates:
                        current += timedelta(days=1)
                        continue
                    # Prefer lower-scoring commits (typos/configs, not refactors).
                    candidates.sort(key=lambda i: result[i].score)
                    n_to_move = rng.randint(1, min(3, len(candidates)))
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
                        moved.add(idx)

            current += timedelta(days=1)

        # Enforce monotonicity: push forward any inversions
        for i in range(1, len(result)):
            if result[i].new_author_date < result[i - 1].new_author_date:
                new_time = result[i - 1].new_author_date + timedelta(seconds=30)
                result[i].new_author_date = new_time
                result[i].new_committer_date = new_time

        return result
