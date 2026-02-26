"""Fast-export/fast-import rewrite backend."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from git_spreader.models import ScheduledCommit


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

    def create_backup(self, repo_path: Path, commit_range: str) -> str:
        """Create a backup ref pointing to current HEAD."""
        timestamp = int(time.time())
        ref_name = f"refs/spreader-backup/{timestamp}"
        _run_git(repo_path, "update-ref", ref_name, "HEAD")
        return ref_name

    def rewrite(
        self,
        repo_path: Path,
        commit_range: str,
        schedule: list[ScheduledCommit],
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> str:
        """Rewrite commit timestamps via fast-export | transform | fast-import.

        Commits in the fast-export stream are in topological order, matching
        our schedule list by position.
        """
        # Build a map from original SHA to new dates
        sha_to_schedule: dict[str, ScheduledCommit] = {
            sc.commit.sha: sc for sc in schedule
        }

        # Get the branch name
        branch = _run_git(repo_path, "rev-parse", "--abbrev-ref", "HEAD").strip()

        # Export the commit range
        export_stream = _run_git(
            repo_path,
            "fast-export",
            "--signed-tags=strip",
            "--no-data",
            "--reencode=yes",
            commit_range,
        )

        # Transform the stream
        modified_stream = self._transform_stream(
            export_stream,
            sha_to_schedule,
            schedule,
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
        sha_map: dict[str, ScheduledCommit],
        schedule: list[ScheduledCommit],
        author_name: str | None,
        author_email: str | None,
    ) -> str:
        """Transform a fast-export stream, rewriting author/committer dates.

        Matches commits by position in topological order since fast-export
        outputs in the same order as our schedule.
        """
        lines = stream.split("\n")
        result_lines: list[str] = []
        commit_idx = 0

        # Pattern for author/committer lines:
        # author Name <email> timestamp timezone
        # committer Name <email> timestamp timezone
        author_pattern = re.compile(
            r"^(author|committer)\s+(.+?)\s+<(.+?)>\s+(\d+)\s+([+-]\d{4})$"
        )

        for line in lines:
            match = author_pattern.match(line)
            if match and commit_idx < len(schedule):
                role = match.group(1)
                name = match.group(2)
                email = match.group(3)

                sc = schedule[commit_idx]
                if role == "author":
                    new_date = sc.new_author_date
                    if author_name:
                        name = author_name
                    if author_email:
                        email = author_email
                else:  # committer
                    new_date = sc.new_committer_date
                    if author_name:
                        name = author_name
                    if author_email:
                        email = author_email

                # Convert datetime to unix timestamp + timezone offset
                ts = int(new_date.timestamp())
                # Use UTC offset from the datetime or default to +0000
                if new_date.tzinfo:
                    utc_offset = new_date.utcoffset()
                    if utc_offset is not None:
                        total_seconds = int(utc_offset.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (abs(total_seconds) % 3600) // 60
                        tz_str = f"{hours:+03d}{minutes:02d}"
                    else:
                        tz_str = "+0000"
                else:
                    tz_str = "+0000"

                result_lines.append(f"{role} {name} <{email}> {ts} {tz_str}")

                # Advance commit index after processing the committer line
                if role == "committer":
                    commit_idx += 1
            else:
                result_lines.append(line)

        return "\n".join(result_lines)
