"""Late-night modifier — moves low-complexity commits to evening hours."""

from __future__ import annotations

import random
from datetime import timedelta

from git_spreader.models import ScheduledCommit, SpreaderConfig
from git_spreader.realism import register_schedule


@register_schedule
class LateNightModifier:
    """Moves low-complexity commits to 21:00-01:00 window."""

    LATE_NIGHT_START_HOUR = 21
    LATE_NIGHT_END_HOUR = 25  # 01:00 next day, represented as 25 for math

    def is_enabled(self, config: SpreaderConfig) -> bool:
        return config.late_night_probability > 0

    def modify_schedule(
        self,
        scheduled: list[ScheduledCommit],
        config: SpreaderConfig,
        rng: random.Random,
    ) -> list[ScheduledCommit]:
        if not scheduled:
            return scheduled

        # Find low-complexity commits (bottom 30% by score)
        scores = sorted(sc.score for sc in scheduled)
        threshold = scores[max(0, len(scores) * 30 // 100)]

        result = list(scheduled)
        for i, sc in enumerate(result):
            if sc.score <= threshold and rng.random() < config.late_night_probability:
                # Move to late night on the same date
                hour = rng.randint(self.LATE_NIGHT_START_HOUR, self.LATE_NIGHT_END_HOUR - 1)
                minute = rng.randint(0, 59)

                new_time = sc.new_author_date.replace(hour=0, minute=0, second=0)
                if hour >= 24:
                    new_time += timedelta(days=1)
                    hour -= 24
                new_time = new_time.replace(
                    hour=hour,
                    minute=minute,
                    second=rng.randint(0, 59),
                )
                result[i].new_author_date = new_time
                result[i].new_committer_date = new_time

        # Enforce monotonicity: push forward any inversions
        for i in range(1, len(result)):
            if result[i].new_author_date < result[i - 1].new_author_date:
                new_time = result[i - 1].new_author_date + timedelta(seconds=30)
                result[i].new_author_date = new_time
                result[i].new_committer_date = new_time

        return result
