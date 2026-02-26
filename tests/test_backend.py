"""Tests for the rewrite backend."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from git_spreader.backend.fast_export import FastExportImportBackend
from git_spreader.git_ops import enumerate_commits
from git_spreader.models import ScheduledCommit


@pytest.fixture
def backend():
    return FastExportImportBackend()


def test_create_backup(temp_repo: Path, backend: FastExportImportBackend):
    ref = backend.create_backup(temp_repo, "HEAD~2..HEAD")
    assert ref.startswith("refs/spreader-backup/")
    # Verify the ref exists
    result = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=temp_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_rewrite_changes_timestamps(temp_repo: Path, backend: FastExportImportBackend):
    commits = enumerate_commits(temp_repo, "HEAD~3..HEAD")
    assert len(commits) == 3

    # Create a schedule with new dates
    new_dates = [
        datetime(2025, 3, 1, 10, 0, 0, tzinfo=UTC),
        datetime(2025, 3, 1, 14, 30, 0, tzinfo=UTC),
        datetime(2025, 3, 2, 9, 15, 0, tzinfo=UTC),
    ]
    schedule = [
        ScheduledCommit(
            commit=c,
            score=0.5,
            gap_minutes=30,
            new_author_date=d,
            new_committer_date=d,
        )
        for c, d in zip(commits, new_dates)
    ]

    backend.create_backup(temp_repo, "HEAD~3..HEAD")
    new_head = backend.rewrite(temp_repo, "HEAD~3..HEAD", schedule)
    assert new_head

    # Verify the new timestamps
    result = subprocess.run(
        ["git", "log", "--format=%aI", "-3"],
        cwd=temp_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    dates = result.stdout.strip().split("\n")
    assert len(dates) == 3
    # Most recent first in git log
    for date_str in dates:
        parsed = datetime.fromisoformat(date_str)
        assert parsed.year == 2025
        assert parsed.month == 3


def test_rewrite_preserves_content(temp_repo: Path, backend: FastExportImportBackend):
    """Verify that file content is unchanged after rewriting."""
    # Check content before
    before_files = set()
    for f in temp_repo.iterdir():
        if f.name.startswith("file"):
            before_files.add((f.name, f.read_text()))

    commits = enumerate_commits(temp_repo, "HEAD~2..HEAD")
    new_date = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    schedule = [
        ScheduledCommit(
            commit=c,
            score=0.5,
            gap_minutes=30,
            new_author_date=new_date,
            new_committer_date=new_date,
        )
        for c in commits
    ]

    backend.create_backup(temp_repo, "HEAD~2..HEAD")
    backend.rewrite(temp_repo, "HEAD~2..HEAD", schedule)

    # Check content after
    after_files = set()
    for f in temp_repo.iterdir():
        if f.name.startswith("file"):
            after_files.add((f.name, f.read_text()))

    assert before_files == after_files
