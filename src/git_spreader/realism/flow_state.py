"""Flow-state clustering modifier — groups related commits into tight bursts."""

from __future__ import annotations

import random
from datetime import timedelta

from git_spreader.models import ScheduledCommit, SpreaderConfig
from git_spreader.realism import register_schedule


@register_schedule
class FlowStateModifier:
    """Clusters 2-4 related commits into tight 5-15min bursts."""

    CLUSTER_PROBABILITY = 0.20  # ~20% of eligible sequences get clustered
    MIN_CLUSTER = 2
    MAX_CLUSTER = 4
    MIN_BURST_MINUTES = 5
    MAX_BURST_MINUTES = 15

    def is_enabled(self, config: SpreaderConfig) -> bool:
        return config.flow_state_clustering

    def modify_schedule(
        self,
        scheduled: list[ScheduledCommit],
        config: SpreaderConfig,
        rng: random.Random,
    ) -> list[ScheduledCommit]:
        if len(scheduled) < self.MIN_CLUSTER:
            return scheduled

        result = list(scheduled)
        i = 0
        while i < len(result) - 1:
            if rng.random() < self.CLUSTER_PROBABILITY:
                cluster_size = min(
                    rng.randint(self.MIN_CLUSTER, self.MAX_CLUSTER),
                    len(result) - i,
                )
                if cluster_size >= self.MIN_CLUSTER:
                    # Check if commits touch similar files (simple heuristic)
                    if self._are_related(result[i : i + cluster_size]):
                        self._compress_cluster(result, i, cluster_size, rng)
                        i += cluster_size
                        continue
            i += 1

        return result

    def _are_related(self, commits: list[ScheduledCommit]) -> bool:
        """Check if commits are related (touch overlapping files)."""
        # Simple heuristic: always consider sequential commits potentially related
        # A real implementation could compare file lists
        return True

    def _compress_cluster(
        self,
        scheduled: list[ScheduledCommit],
        start_idx: int,
        size: int,
        rng: random.Random,
    ) -> None:
        """Compress a cluster of commits into tight bursts."""
        anchor = scheduled[start_idx].new_author_date
        for j in range(1, size):
            idx = start_idx + j
            burst_gap = timedelta(minutes=rng.uniform(self.MIN_BURST_MINUTES, self.MAX_BURST_MINUTES))
            new_time = anchor + burst_gap * j
            scheduled[idx].new_author_date = new_time
            scheduled[idx].new_committer_date = new_time
