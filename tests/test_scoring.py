"""Tests for the complexity scoring engine."""

from __future__ import annotations

from datetime import UTC, datetime

from git_spreader.models import CommitInfo, SpreaderConfig
from git_spreader.scoring import _apply_curve, score_commits


def _make_commit(
    sha: str = "abc123",
    lines: int = 0,
    files: int = 0,
    diff_bytes: int = 0,
    subject: str = "test",
) -> CommitInfo:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    return CommitInfo(
        sha=sha,
        author_name="Test",
        author_email="test@example.com",
        author_date=now,
        committer_name="Test",
        committer_email="test@example.com",
        committer_date=now,
        subject=subject,
        lines_changed=lines,
        files_touched=files,
        diff_bytes=diff_bytes,
    )


def test_empty_commits():
    result = score_commits([], SpreaderConfig())
    assert result == []


def test_single_commit():
    commits = [_make_commit(lines=100, files=5, diff_bytes=500)]
    result = score_commits(commits, SpreaderConfig())
    assert len(result) == 1
    assert result[0].score == 0.0
    assert result[0].gap_minutes == SpreaderConfig().min_gap_minutes


def test_two_commits_different_complexity():
    config = SpreaderConfig(curve="linear")
    commits = [
        _make_commit(sha="small", lines=10, files=1, diff_bytes=50),
        _make_commit(sha="big", lines=100, files=10, diff_bytes=500),
    ]
    result = score_commits(commits, config)
    assert len(result) == 2
    # The big commit should have a higher score
    assert result[1].score > result[0].score
    # The big commit should have a longer gap
    assert result[1].gap_minutes > result[0].gap_minutes
    # The biggest commit should score ~1.0 (all metrics are max)
    assert abs(result[1].score - 1.0) < 0.01


def test_all_same_size():
    config = SpreaderConfig(curve="linear")
    commits = [_make_commit(sha=f"c{i}", lines=50, files=3, diff_bytes=200) for i in range(5)]
    result = score_commits(commits, config)
    # All should have the same score
    scores = {r.score for r in result}
    assert len(scores) == 1


def test_zero_metrics():
    """Empty commits (no diff) should get min_gap."""
    config = SpreaderConfig()
    commits = [
        _make_commit(sha="empty1", lines=0, files=0, diff_bytes=0),
        _make_commit(sha="empty2", lines=0, files=0, diff_bytes=0),
    ]
    result = score_commits(commits, config)
    for r in result:
        assert r.score == 0.0
        assert r.gap_minutes == config.min_gap_minutes


def test_sqrt_curve():
    assert _apply_curve(0.0, "sqrt") == 0.0
    assert _apply_curve(1.0, "sqrt") == 1.0
    # sqrt(0.25) = 0.5
    assert abs(_apply_curve(0.25, "sqrt") - 0.5) < 0.01


def test_linear_curve():
    assert _apply_curve(0.5, "linear") == 0.5


def test_log_curve():
    assert _apply_curve(0.0, "log") == 0.0
    assert abs(_apply_curve(1.0, "log") - 1.0) < 0.01


def test_gap_bounds():
    config = SpreaderConfig(min_gap_minutes=5, max_gap_minutes=100, curve="linear")
    commits = [
        _make_commit(sha="c0", lines=1, files=1, diff_bytes=1),
        _make_commit(sha="c1", lines=1000, files=50, diff_bytes=50000),
    ]
    result = score_commits(commits, config)
    for r in result:
        assert r.gap_minutes >= config.min_gap_minutes
        assert r.gap_minutes <= config.max_gap_minutes


def test_custom_weights():
    # Weight only lines
    config = SpreaderConfig(weight_lines=1.0, weight_files=0.0, weight_bytes=0.0, curve="linear")
    commits = [
        _make_commit(sha="c0", lines=10, files=100, diff_bytes=10000),
        _make_commit(sha="c1", lines=100, files=1, diff_bytes=10),
    ]
    result = score_commits(commits, config)
    # c1 should score higher because it has more lines
    assert result[1].score > result[0].score
