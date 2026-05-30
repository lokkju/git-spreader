"""Fast-export/fast-import rewrite backend."""

from __future__ import annotations

import re
import subprocess
import time
from datetime import timedelta
from pathlib import Path

from git_spreader.models import ScheduledCommit


def _format_tz_offset(utc_offset: timedelta) -> str:
    """Format a UTC offset as a git-style ``+HHMM`` / ``-HHMM`` string.

    Computes the sign once from the total seconds and formats the magnitude,
    so half-hour zones west of UTC (e.g. ``-03:30``) are not rolled down to
    the next whole hour by floor division.
    """
    total_seconds = int(utc_offset.total_seconds())
    sign = "-" if total_seconds < 0 else "+"
    mag = abs(total_seconds)
    return f"{sign}{mag // 3600:02d}{(mag % 3600) // 60:02d}"


def _run_git(repo_path: Path, *args: str, input_data: str | None = None) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        input=input_data,
        check=True,
    )
    return result.stdout


class FastExportImportBackend:
    """Rewrite backend using git fast-export and fast-import."""

    def create_bundle(self, repo_path: Path, bundle_path: Path | None = None) -> Path:
        """Create a standalone git bundle of all refs as a durable backup.

        Unlike a backup ref, a bundle is a self-contained file: it survives
        ``git gc``, ``git reset --hard``, and even deletion of the repo, and can
        be moved off-machine. Defaults to
        ``<git-dir>/spreader-backups/<unix-ts>.bundle``.

        Args:
            repo_path: Path to the git repository.
            bundle_path: Optional explicit destination for the bundle file.

        Returns:
            The path to the created bundle.
        """
        if bundle_path is None:
            git_dir = Path(_run_git(repo_path, "rev-parse", "--absolute-git-dir").strip())
            bundle_path = git_dir / "spreader-backups" / f"{int(time.time())}.bundle"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        _run_git(repo_path, "bundle", "create", str(bundle_path), "--all")
        return bundle_path

    def rewrite(
        self,
        repo_path: Path,
        commit_range: str,
        schedule: list[ScheduledCommit],
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> str:
        """Rewrite commit timestamps via fast-export | transform | fast-import.

        Commits in the stream are matched to the schedule by SHA (via
        ``original-oid``), so the schedule order does not matter.
        """
        # Build a map from original SHA to new dates
        sha_to_schedule: dict[str, ScheduledCommit] = {sc.commit.sha: sc for sc in schedule}

        # Export the commit range.
        #   --show-original-ids       emits `original-oid <sha>` so we can match
        #                             commits by identity rather than position.
        #   --reference-excluded-parents emits a `from <sha>` on the first
        #                             in-range commit, so ancestor history before
        #                             the range base is preserved (without it,
        #                             fast-import re-roots the branch and drops
        #                             every commit before the range).
        export_stream = _run_git(
            repo_path,
            "fast-export",
            "--signed-tags=strip",
            "--no-data",
            "--reencode=yes",
            "--show-original-ids",
            "--reference-excluded-parents",
            commit_range,
        )

        # Transform the stream
        modified_stream = self._transform_stream(
            export_stream,
            sha_to_schedule,
            author_name,
            author_email,
        )

        # Import the modified stream
        # First, delete the branch ref so fast-import can recreate it
        _run_git(repo_path, "fast-import", "--force", "--quiet", input_data=modified_stream)

        # Get new HEAD
        new_head = _run_git(repo_path, "rev-parse", "HEAD").strip()
        return new_head

    def _transform_stream(
        self,
        stream: str,
        sha_to_schedule: dict[str, ScheduledCommit],
        author_name: str | None,
        author_email: str | None,
    ) -> str:
        """Transform a fast-export stream, rewriting author/committer dates.

        Commits are matched by SHA via the ``original-oid <sha>`` lines emitted
        by ``--show-original-ids``, so the schedule's ordering is irrelevant.
        A commit whose SHA is not in the schedule is passed through unchanged.
        """
        lines = stream.split("\n")
        result_lines: list[str] = []
        current_sc: ScheduledCommit | None = None

        # Pattern for author/committer lines:
        # author Name <email> timestamp timezone
        # committer Name <email> timestamp timezone
        author_pattern = re.compile(r"^(author|committer)\s+(.+?)\s+<(.+?)>\s+(\d+)\s+([+-]\d{4})$")

        for line in lines:
            if line.startswith("original-oid "):
                sha = line[len("original-oid ") :].strip()
                current_sc = sha_to_schedule.get(sha)
                result_lines.append(line)
                continue

            match = author_pattern.match(line)
            if match and current_sc is not None:
                role = match.group(1)
                name = match.group(2)
                email = match.group(3)

                if role == "author":
                    new_date = current_sc.new_author_date
                else:  # committer
                    new_date = current_sc.new_committer_date
                if author_name:
                    name = author_name
                if author_email:
                    email = author_email

                # Convert datetime to unix timestamp + timezone offset
                ts = int(new_date.timestamp())
                # Use UTC offset from the datetime or default to +0000
                utc_offset = new_date.utcoffset() if new_date.tzinfo else None
                tz_str = _format_tz_offset(utc_offset) if utc_offset is not None else "+0000"

                result_lines.append(f"{role} {name} <{email}> {ts} {tz_str}")
            else:
                result_lines.append(line)

        return "\n".join(result_lines)
