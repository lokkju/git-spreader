"""CLI interface for git-spreader."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="git-spreader",
    help="Redistribute git commit timestamps across a realistic working schedule.",
    no_args_is_help=True,
)
