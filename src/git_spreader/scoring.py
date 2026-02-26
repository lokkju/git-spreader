"""Complexity scoring and gap mapping for git-spreader."""

from __future__ import annotations

import math

from git_spreader.models import CommitInfo, ScoredCommit, SpreaderConfig


def _apply_curve(score: float, curve: str) -> float:
    """Apply a mapping curve to a normalized score."""
    if curve == "sqrt":
        return math.sqrt(score)
    elif curve == "log":
        # log(1 + score * (e-1)) maps [0,1] -> [0,1] with log shape
        return math.log(1 + score * (math.e - 1))
    else:  # linear
        return score


def score_commits(
    commits: list[CommitInfo],
    config: SpreaderConfig,
) -> list[ScoredCommit]:
    """Score commits by complexity and compute gap-before times.

    Each commit's metrics (lines, files, bytes) are normalized to [0,1]
    relative to the maximum in the batch, then combined with configured
    weights. The resulting score is mapped through a curve function to
    produce a gap in minutes.

    Args:
        commits: List of CommitInfo to score.
        config: Configuration with weights, gap bounds, and curve type.

    Returns:
        List of ScoredCommit with normalized scores and gap_minutes.
    """
    if not commits:
        return []

    if len(commits) == 1:
        return [
            ScoredCommit(
                commit=commits[0],
                score=0.0,
                gap_minutes=config.min_gap_minutes,
            )
        ]

    # Find max values for normalization
    max_lines = max(c.lines_changed for c in commits) or 1
    max_files = max(c.files_touched for c in commits) or 1
    max_bytes = max(c.diff_bytes for c in commits) or 1

    scored: list[ScoredCommit] = []
    for commit in commits:
        # Normalize each metric to [0, 1]
        norm_lines = commit.lines_changed / max_lines
        norm_files = commit.files_touched / max_files
        norm_bytes = commit.diff_bytes / max_bytes

        # Weighted sum
        raw_score = (
            config.weight_lines * norm_lines
            + config.weight_files * norm_files
            + config.weight_bytes * norm_bytes
        )

        # Clamp to [0, 1]
        raw_score = max(0.0, min(1.0, raw_score))

        # Apply curve
        curved = _apply_curve(raw_score, config.curve)

        # Map to gap minutes
        gap = config.min_gap_minutes + (config.max_gap_minutes - config.min_gap_minutes) * curved

        scored.append(
            ScoredCommit(
                commit=commit,
                score=raw_score,
                gap_minutes=gap,
            )
        )

    return scored
