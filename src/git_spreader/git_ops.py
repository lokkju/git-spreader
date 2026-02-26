"""Git subprocess helpers for git-spreader."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from git_spreader.models import CommitInfo


def _run_git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in the given repo and return the result."""
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )


def _parse_iso_date(date_str: str) -> datetime:
    """Parse a git ISO-strict date string into a datetime."""
    # git --date=iso-strict produces: 2025-02-15T02:14:33+00:00
    return datetime.fromisoformat(date_str)


def enumerate_commits(repo_path: Path, commit_range: str) -> list[CommitInfo]:
    """Enumerate commits in topological order with diff stats.

    Args:
        repo_path: Path to the git repository.
        commit_range: Git revision range (e.g. "HEAD~10..HEAD", "main..feature").

    Returns:
        List of CommitInfo in topological order (oldest first).
    """
    # Get commit metadata (NUL-separated fields)
    fmt = "%H%x00%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI%x00%s%x00%P"
    result = _run_git(
        repo_path,
        "log",
        "--reverse",
        "--topo-order",
        f"--format={fmt}",
        commit_range,
    )

    if not result.stdout.strip():
        return []

    commits: list[CommitInfo] = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split("\0")
        if len(parts) < 9:
            continue

        sha = parts[0]
        parent_shas = parts[8].split() if parts[8] else []

        # Get diff stats for this commit
        lines_changed, files_touched = _get_diff_stats(repo_path, sha)
        diff_bytes = _get_diff_bytes(repo_path, sha)

        commits.append(
            CommitInfo(
                sha=sha,
                author_name=parts[1],
                author_email=parts[2],
                author_date=_parse_iso_date(parts[3]),
                committer_name=parts[4],
                committer_email=parts[5],
                committer_date=_parse_iso_date(parts[6]),
                subject=parts[7],
                lines_changed=lines_changed,
                files_touched=files_touched,
                diff_bytes=diff_bytes,
                parent_shas=parent_shas,
            )
        )

    return commits


def _get_diff_stats(repo_path: Path, sha: str) -> tuple[int, int]:
    """Get lines changed and files touched for a commit."""
    try:
        result = _run_git(repo_path, "diff", "--numstat", f"{sha}^", sha)
    except subprocess.CalledProcessError:
        # Root commit — diff against empty tree
        result = _run_git(
            repo_path, "diff", "--numstat", "4b825dc642cb6eb9a060e54bf899d69f82cf7108", sha
        )

    lines = 0
    files = 0
    for stat_line in result.stdout.strip().split("\n"):
        if not stat_line:
            continue
        parts = stat_line.split("\t")
        if len(parts) < 3:
            continue
        files += 1
        # Binary files show "-" for insertions/deletions
        added = int(parts[0]) if parts[0] != "-" else 0
        deleted = int(parts[1]) if parts[1] != "-" else 0
        lines += added + deleted

    return lines, files


def _get_diff_bytes(repo_path: Path, sha: str) -> int:
    """Get the diff size in bytes for a commit."""
    try:
        result = _run_git(repo_path, "diff", "-p", f"{sha}^", sha)
    except subprocess.CalledProcessError:
        result = _run_git(
            repo_path, "diff", "-p", "4b825dc642cb6eb9a060e54bf899d69f82cf7108", sha
        )
    return len(result.stdout.encode("utf-8"))


def detect_pushed_commits(repo_path: Path, commit_range: str) -> list[str]:
    """Check which commits in the range exist on remote tracking branches.

    Returns list of SHAs that have been pushed.
    """
    # Get the upstream tracking branch
    try:
        result = _run_git(repo_path, "rev-parse", "--abbrev-ref", "@{upstream}")
        upstream = result.stdout.strip()
    except subprocess.CalledProcessError:
        return []  # No upstream configured

    # Get commits that are on the remote
    try:
        range_result = _run_git(
            repo_path, "log", "--format=%H", commit_range
        )
        range_shas = set(range_result.stdout.strip().split("\n"))

        remote_result = _run_git(
            repo_path, "log", "--format=%H", upstream
        )
        remote_shas = set(remote_result.stdout.strip().split("\n"))

        return [sha for sha in range_shas if sha in remote_shas]
    except subprocess.CalledProcessError:
        return []


def detect_gpg_signatures(repo_path: Path, commit_range: str) -> list[str]:
    """Check which commits in the range have GPG signatures.

    Returns list of SHAs with signatures.
    """
    result = _run_git(
        repo_path, "log", "--format=%H %G?", commit_range
    )
    signed = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[1] in ("G", "U", "X", "Y", "R", "E", "B"):
            signed.append(parts[0])
    return signed
