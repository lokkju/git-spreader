# git-spreader

[![Test](https://github.com/lokkju/git-spreader/actions/workflows/test.yml/badge.svg)](https://github.com/lokkju/git-spreader/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/git-spreader)](https://pypi.org/project/git-spreader/)
[![Python](https://img.shields.io/pypi/pyversions/git-spreader)](https://pypi.org/project/git-spreader/)

Redistribute git commit timestamps across a realistic working schedule.

Takes compressed bursts of commits (weekend hackathons, late-night sessions) and respaces them to look like steady, sustainable work during business hours — with realistic human touches like jitter, flow-state clustering, occasional late-night/weekend commits, and random days off.

## Installation

```bash
pip install git-spreader
# or
uv pip install git-spreader
```

## Usage

### Preview a schedule (dry run)

```bash
git-spreader preview HEAD~10..HEAD --start 2025-01-01 --seed 42
```

```
  #  Original Date          New Date                Score  Gap      Summary
  1  2025-02-15 02:14:33    2025-01-02 09:23:41     0.12   —        fix: typo in README
  2  2025-02-15 02:31:07    2025-01-02 09:48:15     0.08   25m      chore: update deps
  3  2025-02-15 03:45:22    2025-01-06 10:12:33     0.73   1d 25m   feat: add auth module
  4  2025-02-15 04:02:19    2025-01-06 14:45:08     0.45   4h 33m   feat: auth tests
  5  2025-02-15 04:15:41    2025-01-07 09:37:22     0.91   18h 52m  refactor: database layer
```

### Rewrite timestamps

```bash
git-spreader spread HEAD~10..HEAD --start 2025-01-01 --seed 42
```

### Set a fixed date range

```bash
git-spreader spread HEAD~20..HEAD --start 2025-01-01 --end 2025-01-31
```

### Override working hours

```bash
git-spreader spread HEAD~10..HEAD --start 2025-02-01 --working-hours 08:00-16:00
```

### Manage configuration

```bash
git-spreader config --show    # print effective config
git-spreader config --reset   # reset to defaults
```

## How It Works

### Complexity scoring

Each commit is scored by a weighted combination of lines changed (50%), files touched (30%), and diff size in bytes (20%). The score is mapped through a curve (sqrt by default) to a time gap:

```
gap = min_gap + (max_gap - min_gap) * sqrt(score)
```

A typo fix gets a 10-minute gap. A 500-line refactor gets hours.

### Scheduling

Gaps are placed within configurable working hours (default 09:00–17:00, Mon–Fri). When a gap crosses a day boundary, the commit wraps to the next available working day.

### Realism engine

Six modifiers make the schedule look human:

| Modifier | Phase | Effect |
|----------|-------|--------|
| **Holidays** | Pre-schedule | Removes holiday dates (US, UK, CA, etc.) |
| **Days off** | Pre-schedule | Randomly skips ~10% of workdays |
| **Flow state** | Post-schedule | Clusters 2–4 related commits into tight bursts |
| **Late night** | Post-schedule | Moves ~5% of low-complexity commits to 21:00–01:00 |
| **Weekend** | Post-schedule | Adds 1–3 commits to ~8% of weekend days |
| **Jitter** | Post-schedule | Random ±5–10 min offset on all timestamps |

All modifiers are individually configurable and can be disabled.

### Backup and undo

Before rewriting, a backup ref is created at `refs/spreader-backup/<timestamp>`. To undo:

```bash
git reset --hard refs/spreader-backup/<timestamp>
```

## Configuration

Configuration uses a three-tier precedence model: **CLI flags > repo `.git-spreader.toml` > global `~/.config/git-spreader/config.toml` > defaults**.

Example `.git-spreader.toml`:

```toml
[schedule]
working_hours = { start = "09:00", end = "17:00" }
working_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
timezone = "America/Los_Angeles"

[realism]
late_night_probability = 0.05
weekend_probability = 0.08
random_day_off_probability = 0.10
flow_state_clustering = true
avoid_holidays = true

[realism.jitter]
min_offset_minutes = -5
max_offset_minutes = 10

[realism.holidays]
calendar = "US"
additional = ["2025-12-24", "2025-12-26"]

[complexity]
weights = { lines = 0.5, files = 0.3, bytes = 0.2 }
min_gap_minutes = 10
max_gap_minutes = 480
curve = "sqrt"  # or "linear", "log"
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check src/ tests/
uv run pyright src/
```

## License

[Polyform Shield 1.0.0](LICENSE.md)
