"""Shared test fixtures for git-spreader tests."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repository with some commits."""
    repo = tmp_path / "test-repo"
    repo.mkdir()

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test Author",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test Author",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }

    def run_git(*args: str, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            env=env,
            check=True,
            **kwargs,
        )

    run_git("init", "-b", "main")
    run_git("config", "user.name", "Test Author")
    run_git("config", "user.email", "test@example.com")

    # Create initial commits with known timestamps
    for i in range(5):
        filepath = repo / f"file{i}.txt"
        filepath.write_text(f"content {i}\n" + ("extra line\n" * (i * 10)))
        run_git("add", ".")
        ts = datetime(2025, 2, 15, 2 + i, 14, 33, tzinfo=timezone.utc)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S%z")
        env_with_date = {
            **env,
            "GIT_AUTHOR_DATE": ts_str,
            "GIT_COMMITTER_DATE": ts_str,
        }
        subprocess.run(
            ["git", "commit", "-m", f"commit {i}: add file{i}.txt"],
            cwd=repo,
            capture_output=True,
            text=True,
            env=env_with_date,
            check=True,
        )

    yield repo


@pytest.fixture
def fixed_seed() -> int:
    """Return a fixed seed for deterministic tests."""
    return 42
