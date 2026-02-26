"""Rewrite backend protocol and implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from git_spreader.models import ScheduledCommit


class RewriteBackend(Protocol):
    """Protocol for git history rewriting backends."""

    def create_backup(self, repo_path: Path, commit_range: str) -> str:
        """Create a backup ref before rewriting.

        Returns the backup ref name.
        """
        ...

    def rewrite(
        self,
        repo_path: Path,
        commit_range: str,
        schedule: list[ScheduledCommit],
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> str:
        """Rewrite commit timestamps according to the schedule.

        Returns the new HEAD SHA.
        """
        ...
