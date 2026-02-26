"""CLI interface for git-spreader."""

from __future__ import annotations

import random
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.table import Table

from git_spreader import __version__
from git_spreader.backend.fast_export import FastExportImportBackend
from git_spreader.config import load_config, show_config, write_default_config
from git_spreader.git_ops import (
    detect_gpg_signatures,
    detect_pushed_commits,
    enumerate_commits,
)
from git_spreader.models import ScheduledCommit, SpreaderConfig
from git_spreader.profiles import PROFILES, get_profile
from git_spreader.realism import apply_schedule_modifiers, apply_slot_modifiers
from git_spreader.scheduling import (
    auto_end_date,
    build_time_slots,
    compress_gaps,
    schedule_commits,
)
from git_spreader.scoring import score_commits

app = typer.Typer(
    name="git-spreader",
    help="Redistribute git commit timestamps across a realistic working schedule.",
    no_args_is_help=True,
)

console = Console()


def _get_repo_path() -> Path:
    """Get the root of the current git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        console.print("[red]Error: not inside a git repository.[/red]")
        raise typer.Exit(1)


def _parse_date(date_str: str, tz: ZoneInfo | None = None) -> datetime:
    """Parse a date string into a timezone-aware datetime.

    If the date string has no timezone info, uses the provided tz
    (from config) or falls back to UTC.
    """
    try:
        dt = datetime.fromisoformat(date_str)
    except ValueError:
        # Try just a date
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            console.print(f"[red]Error: cannot parse date '{date_str}'[/red]")
            raise typer.Exit(1)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz or UTC)
    return dt


def _parse_working_days(days_str: str) -> tuple[str, ...]:
    """Parse comma-separated day abbreviations into a tuple."""
    valid_days = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
    days = tuple(d.strip() for d in days_str.split(","))
    invalid = [d for d in days if d not in valid_days]
    if invalid:
        console.print(
            f"[red]Error: invalid day(s): {', '.join(invalid)}. "
            f"Use: Mon,Tue,Wed,Thu,Fri,Sat,Sun[/red]"
        )
        raise typer.Exit(1)
    return days


def _run_pipeline(
    commit_range: str,
    start: str,
    end: str | None,
    working_hours: str | None,
    working_days: str | None,
    profile: str | None,
    seed: int | None,
    verbose: bool,
) -> tuple[list[ScheduledCommit], SpreaderConfig, Path]:
    """Run the full spread pipeline and return scheduled commits."""
    repo_path = _get_repo_path()

    # Load profile overrides
    profile_overrides: dict | None = None
    if profile:
        try:
            profile_overrides = get_profile(profile)
        except KeyError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    # Build CLI overrides
    cli_overrides: dict = {}
    if working_hours:
        parts = working_hours.split("-")
        if len(parts) == 2:
            cli_overrides["working_hours_start"] = parts[0]
            cli_overrides["working_hours_end"] = parts[1]
    if working_days:
        cli_overrides["working_days"] = _parse_working_days(working_days)

    config = load_config(repo_path, cli_overrides, profile_overrides)
    rng = random.Random(seed)

    # Warn if configured timezone differs from local system timezone
    from git_spreader.models import _detect_local_timezone

    local_tz = _detect_local_timezone()
    if config.timezone != local_tz:
        console.print(
            f"[yellow]Warning: configured timezone '{config.timezone}' "
            f"differs from system timezone '{local_tz}'.[/yellow]"
        )

    # Enumerate commits
    if verbose:
        console.print(f"[dim]Enumerating commits in {commit_range}...[/dim]")
    commits = enumerate_commits(repo_path, commit_range)
    if not commits:
        console.print("[yellow]No commits found in range.[/yellow]")
        raise typer.Exit(0)

    if verbose:
        console.print(f"[dim]Found {len(commits)} commits.[/dim]")

    # Safety checks
    pushed = detect_pushed_commits(repo_path, commit_range)
    if pushed:
        console.print(
            f"[yellow]Warning: {len(pushed)} commit(s) have already been pushed. "
            f"You will need to force-push after spreading.[/yellow]"
        )

    signed = detect_gpg_signatures(repo_path, commit_range)
    if signed:
        console.print(
            f"[yellow]Warning: {len(signed)} commit(s) have GPG signatures "
            f"that will be lost after rewriting.[/yellow]"
        )

    # Score commits
    scored = score_commits(commits, config)
    if verbose:
        for sc in scored:
            console.print(
                f"[dim]  {sc.commit.sha[:8]} score={sc.score:.2f} "
                f"gap={sc.gap_minutes:.0f}m — {sc.commit.subject}[/dim]"
            )

    # Parse dates using configured timezone
    tz = ZoneInfo(config.timezone)
    start_dt = _parse_date(start, tz)
    if end:
        end_dt = _parse_date(end, tz)
    else:
        end_dt = auto_end_date(scored, start_dt, config)
        if verbose:
            console.print(f"[dim]Auto end date: {end_dt.date()}[/dim]")

    # Build time slots
    slots = build_time_slots(start_dt, end_dt, config)
    if verbose:
        console.print(f"[dim]{len(slots)} working day slots generated.[/dim]")

    # Apply slot modifiers (holidays, days off)
    slots = apply_slot_modifiers(slots, config, rng)
    if verbose:
        console.print(f"[dim]{len(slots)} slots after realism modifiers.[/dim]")

    if not slots:
        console.print("[red]Error: no available time slots in the given range.[/red]")
        raise typer.Exit(1)

    # Check if we need to compress
    total_slot_minutes = sum(s.duration_minutes for s in slots)
    total_gap_minutes = sum(sc.gap_minutes for sc in scored)
    if end and total_gap_minutes > total_slot_minutes:
        console.print(
            f"[yellow]Warning: total work time ({total_gap_minutes:.0f}m) exceeds "
            f"available time ({total_slot_minutes:.0f}m). Compressing gaps.[/yellow]"
        )
        scored = compress_gaps(scored, total_slot_minutes)

    # Schedule commits
    scheduled = schedule_commits(scored, slots, config, rng)

    # Apply schedule modifiers (flow state, late night, weekend, jitter)
    scheduled = apply_schedule_modifiers(scheduled, config, rng)

    return scheduled, config, repo_path


def _print_preview_table(scheduled: list[ScheduledCommit]) -> None:
    """Print a Rich table showing the proposed schedule."""
    table = Table(title="git-spreader Preview", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Original Date", style="cyan")
    table.add_column("New Date", style="green")
    table.add_column("Score", justify="right", style="yellow")
    table.add_column("Gap", justify="right")
    table.add_column("Summary", style="white", no_wrap=True, max_width=50)

    for i, sc in enumerate(scheduled):
        gap_str = "—"
        if i > 0:
            delta = sc.new_author_date - scheduled[i - 1].new_author_date
            total_minutes = delta.total_seconds() / 60
            if total_minutes >= 60 * 24:
                days = int(total_minutes // (60 * 24))
                hours = int((total_minutes % (60 * 24)) // 60)
                gap_str = f"{days}d {hours}h"
            elif total_minutes >= 60:
                hours = int(total_minutes // 60)
                mins = int(total_minutes % 60)
                gap_str = f"{hours}h {mins}m"
            else:
                gap_str = f"{int(total_minutes)}m"

        table.add_row(
            str(i + 1),
            sc.commit.author_date.strftime("%Y-%m-%d %H:%M:%S"),
            sc.new_author_date.strftime("%Y-%m-%d %H:%M:%S"),
            f"{sc.score:.2f}",
            gap_str,
            sc.commit.subject[:50],
        )

    console.print(table)

    # Summary stats
    if len(scheduled) >= 2:
        total_delta = scheduled[-1].new_author_date - scheduled[0].new_author_date
        days = total_delta.days
        hours = total_delta.seconds // 3600
        console.print(f"\n  Total simulated time span: {days}d {hours}h")
        console.print(f"  Commits: {len(scheduled)}")


@app.command()
def spread(
    commit_range: str = typer.Argument(help="Git revision range (e.g. HEAD~10..HEAD)"),
    start: str = typer.Option(..., "--start", help="Start date for redistribution"),
    end: str | None = typer.Option(None, "--end", help="End date (auto-calculated if omitted)"),
    working_hours: str | None = typer.Option(
        None, "--working-hours", help="Override working hours (e.g. 09:00-17:00)"
    ),
    working_days: str | None = typer.Option(
        None, "--working-days", help="Override working days (e.g. Mon,Wed,Fri,Sat,Sun)"
    ),
    profile: str | None = typer.Option(
        None, "--profile", help=f"Use a built-in profile ({', '.join(sorted(PROFILES))})"
    ),
    seed: int | None = typer.Option(None, "--seed", help="Random seed for reproducibility"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """Rewrite commit timestamps to spread across a realistic schedule."""
    scheduled, config, repo_path = _run_pipeline(
        commit_range, start, end, working_hours, working_days, profile, seed, verbose
    )

    # Show preview first
    _print_preview_table(scheduled)
    console.print()

    # Create backup and rewrite
    backend = FastExportImportBackend()
    backup_ref = backend.create_backup(repo_path, commit_range)
    console.print(f"[dim]Backup created: {backup_ref}[/dim]")

    try:
        new_head = backend.rewrite(
            repo_path,
            commit_range,
            scheduled,
            config.author_name,
            config.author_email,
        )
        console.print(f"\n[green]Successfully rewrote {len(scheduled)} commits.[/green]")
        console.print(f"[green]New HEAD: {new_head}[/green]")
        console.print(f"\n[dim]To undo: git reset --hard {backup_ref}[/dim]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error during rewrite: {e.stderr}[/red]")
        console.print(f"[yellow]Restore with: git reset --hard {backup_ref}[/yellow]")
        raise typer.Exit(1)


@app.command()
def preview(
    commit_range: str = typer.Argument(help="Git revision range (e.g. HEAD~10..HEAD)"),
    start: str = typer.Option(..., "--start", help="Start date for redistribution"),
    end: str | None = typer.Option(None, "--end", help="End date (auto-calculated if omitted)"),
    working_hours: str | None = typer.Option(
        None, "--working-hours", help="Override working hours (e.g. 09:00-17:00)"
    ),
    working_days: str | None = typer.Option(
        None, "--working-days", help="Override working days (e.g. Mon,Wed,Fri,Sat,Sun)"
    ),
    profile: str | None = typer.Option(
        None, "--profile", help=f"Use a built-in profile ({', '.join(sorted(PROFILES))})"
    ),
    seed: int | None = typer.Option(None, "--seed", help="Random seed for reproducibility"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """Preview the proposed schedule without modifying anything."""
    scheduled, config, repo_path = _run_pipeline(
        commit_range, start, end, working_hours, working_days, profile, seed, verbose
    )
    _print_preview_table(scheduled)
    console.print("\n[dim]Run `git-spreader spread` with the same arguments to apply.[/dim]")


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Print current effective config"),
    reset: bool = typer.Option(False, "--reset", help="Reset config to defaults"),
) -> None:
    """Manage git-spreader configuration."""
    if reset:
        path = write_default_config()
        console.print(f"[green]Config reset to defaults at {path}[/green]")
    elif show:
        repo_path = _get_repo_path()
        cfg = load_config(repo_path)
        console.print(show_config(cfg))
    else:
        console.print("Use --show or --reset. See git-spreader config --help.")


@app.command()
def version() -> None:
    """Show the version."""
    console.print(f"git-spreader {__version__}")


if __name__ == "__main__":
    app()
