# git-spreader: Project Plan

*A tool to redistribute git commit timestamps across a realistic working schedule.*

---

## Problem Statement

Intense bursts of development — weekend hackathons, hyperfocus sessions, deadline crunches — produce git histories that look implausible: 40 commits in 6 hours on a Saturday, or 200 lines changed at 3 AM every night for a week. This doesn't reflect how the work *would have been done* under normal conditions; it reflects how it *happened to get done* under abnormal ones.

**git-spreader** takes a compressed burst of commits and redistributes their timestamps across a configurable working schedule, making the history look like steady, sustainable effort. Commit complexity determines how much simulated "work time" each commit receives — a 500-line refactor gets hours, a typo fix gets minutes.

### Non-Goals

- This tool does **not** fabricate work that didn't happen. The commits, diffs, and messages are real.
- It is **not** designed to deceive employers or misrepresent effort. The primary use case is normalizing legitimate work into a presentable timeline (portfolios, client-facing repos, contribution graphs).
- It does **not** alter code content, only timestamps (and optionally author metadata).

---

## Core Concepts

### The Gap-Before-Commit Model

The central insight: a commit's complexity determines the **time gap before it**, not its absolute position. This simulates realistic work cadence:

```
Commit A (typo fix, score: 2)     → 15 min gap before
Commit B (new feature, score: 45) → 3.5 hr gap before
Commit C (config change, score: 5) → 25 min gap before
Commit D (major refactor, score: 80) → 6 hr gap before (spans lunch + afternoon)
```

Gaps are placed within available working hours. If a gap would cross a boundary (end of work day, weekend, holiday), it wraps into the next available time slot.

### Complexity Scoring

Each commit receives a weighted complexity score from three heuristics:

| Heuristic | Weight (default) | Rationale |
|-----------|-------------------|-----------|
| Lines changed (insertions + deletions) | 0.5 | Primary signal of effort |
| Files touched | 0.3 | Cross-file changes require context-switching |
| Diff size in bytes | 0.2 | Captures renames, binary changes, large moves |

The raw score is computed as:

```
score = (w_lines * normalized_lines) + (w_files * normalized_files) + (w_bytes * normalized_bytes)
```

Where each metric is normalized relative to the **maximum value in the commit range** (so the most complex commit always scores ~1.0). This is then mapped to a time gap via configurable min/max bounds:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_gap_minutes` | 10 | Minimum gap even for trivial commits |
| `max_gap_minutes` | 480 | Maximum gap (one full work day) |
| `complexity_weights` | `[0.5, 0.3, 0.2]` | Lines, files, bytes weights |

### Score → Gap Mapping

The mapping uses a **square-root curve** rather than linear, because perceived effort doesn't scale linearly with diff size — a 1000-line change isn't 10x harder than a 100-line change:

```
gap = min_gap + (max_gap - min_gap) * sqrt(normalized_score)
```

This clusters most commits in the lower-to-middle range and reserves long gaps for genuinely massive changes.

---

## Configuration Model

Configuration follows a three-tier precedence model:

```
CLI flags  >  config file  >  built-in defaults
```

### First-Run Interactive Setup

On first invocation (no config file found), the tool interactively prompts for key settings and writes `~/.config/git-spreader/config.toml`:

```
Welcome to git-spreader! Let's set up your working schedule.

What hours do you typically work? [09:00-17:00]:
What days do you work? [Mon-Fri]:
Your timezone? [America/Los_Angeles]:
Allow occasional late-night commits? [y/N]:
Allow rare weekend commits? [y/N]:

Config saved to ~/.config/git-spreader/config.toml
```

### Config File Format

```toml
[schedule]
working_hours = { start = "09:00", end = "17:00" }
working_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
timezone = "America/Los_Angeles"

[realism]
late_night_probability = 0.05       # 5% chance of commit between 21:00-01:00
weekend_probability = 0.08          # 8% chance of any given weekend day having commits
random_day_off_probability = 0.10   # 10% chance of skipping a workday entirely
flow_state_clustering = true        # cluster 2-4 commits close together sometimes
avoid_holidays = true
holiday_calendar = "US"             # or "UK", "CA", "custom", etc.

[realism.jitter]
min_offset_minutes = -5             # timestamps won't land on exact intervals
max_offset_minutes = 10

[complexity]
weights = { lines = 0.5, files = 0.3, bytes = 0.2 }
min_gap_minutes = 10
max_gap_minutes = 480
curve = "sqrt"                      # or "linear", "log"

[author]
# Optional: override author info on rewritten commits
# name = "Your Name"
# email = "your@email.com"
```

### Per-Repo Override

A `.git-spreader.toml` in the repo root can override global config (useful for repos where you want different working hours or complexity weights).

---

## Realism Engine

The realism engine takes the raw schedule (sequence of gaps mapped to working hours) and applies human-like perturbations.

### Late-Night Commits

With configurable probability (default 5%), a commit is placed between 21:00 and 01:00 instead of during working hours. These are drawn from the pool of **low-complexity commits** — you don't do major refactors at midnight, you fix typos and tweak configs.

### Flow-State Clustering

When enabled, the engine occasionally groups 2-4 sequential commits into a tight cluster (5-15 minute gaps) to simulate a productive burst. The total time allocated to the cluster equals the sum of individual gaps, but compressed:

```
Normal:    [--30min--] A [--45min--] B [--20min--] C
Clustered: [--85min--] A [--5min--] B [--5min--] C
```

Clustering is applied to ~20% of commits (configurable) and only to sequences of related commits (heuristic: same files touched).

### Random Days Off

With configurable probability (default 10%), entire workdays are skipped. This prevents the artificial "committed every single day" pattern.

### Holiday Avoidance

Built-in holiday calendars for common locales. No commits are placed on holidays. Custom dates can be added via config:

```toml
[realism.holidays]
calendar = "US"
additional = ["2025-12-24", "2025-12-26"]  # company shutdown
```

### Weekend Commits

With configurable probability (default 8%), a weekend day gets 1-3 commits. Weekend commits use a shifted schedule (e.g., 10:00-15:00) and skew toward low-to-medium complexity.

### Jitter

All timestamps receive random jitter (default ±5-10 minutes) to avoid landing on suspiciously round times.

---

## CLI Interface

### Commands

```
git-spreader spread <commit-range> --start <date> [--end <date>] [options]
git-spreader preview <commit-range> --start <date> [--end <date>] [options]
git-spreader init
git-spreader config [--show | --edit | --reset]
```

### `spread` — Rewrite Timestamps

```bash
# Spread last 20 commits over the past month
git-spreader spread HEAD~20..HEAD --start 2025-01-01 --end 2025-01-31

# Spread a branch's commits, auto-calculate end date
git-spreader spread main..feature-branch --start 2025-01-15

# Flatten merge commits
git-spreader spread HEAD~10..HEAD --start 2025-02-01 --topology=flatten

# Preserve branch structure
git-spreader spread HEAD~10..HEAD --start 2025-02-01 --topology=preserve

# Override author
git-spreader spread HEAD~5..HEAD --start 2025-02-01 --author="Name <email>"

# Only respace my commits in a multi-author repo
git-spreader spread HEAD~50..HEAD --start 2025-01-01 --only-author="me@example.com"
```

### `preview` — Dry Run

Same arguments as `spread`, but outputs a table showing the proposed schedule without modifying anything:

```
$ git-spreader preview HEAD~5..HEAD --start 2025-02-01

  #  Original Date          New Date                Score  Gap      Summary
  1  2025-02-15 02:14:33    2025-02-01 09:23:41     0.12   —        fix: typo in README
  2  2025-02-15 02:31:07    2025-02-01 09:48:15     0.08   25m      chore: update deps
  3  2025-02-15 03:45:22    2025-02-03 10:12:33     0.73   1d 25m   feat: add auth module
  4  2025-02-15 04:02:19    2025-02-03 14:45:08     0.45   4h 33m   feat: auth tests
  5  2025-02-15 04:15:41    2025-02-04 09:37:22     0.91   18h 52m  refactor: database layer

  Total simulated work time: 2d 1h 15m
  Available work time in range: 20d (Feb 1-28, minus weekends/holidays)
  Schedule density: 10.3%

  Run `git-spreader spread` with the same arguments to apply.
```

### `init` — Interactive First-Run

Creates `~/.config/git-spreader/config.toml` with guided prompts.

### `config` — Manage Settings

```bash
git-spreader config --show          # print current effective config
git-spreader config --edit          # open config in $EDITOR
git-spreader config --reset         # reset to defaults
```

### Key Flags

| Flag | Description |
|------|-------------|
| `--start DATE` | Required. Start date for redistribution. |
| `--end DATE` | Optional. End date. If omitted, auto-calculated from total work time. |
| `--topology flatten\|preserve` | How to handle merge commits. Per-run choice. |
| `--author "Name <email>"` | Override author/committer on rewritten commits. |
| `--only-author EMAIL` | In multi-author repos, only respace commits by this author. |
| `--working-hours 09:00-17:00` | Override config for this run. |
| `--seed INT` | Deterministic randomness for reproducible results. |
| `--verbose` | Show detailed scoring and scheduling decisions. |

---

## Algorithm: End-to-End Flow

```
1. PARSE commit range
   ├─ Enumerate commits in topological order
   ├─ If --only-author, filter to matching commits (preserve others' timestamps)
   └─ If --topology=flatten, linearize merge commits

2. SCORE each commit
   ├─ Compute lines changed, files touched, diff bytes
   ├─ Normalize each metric to [0, 1] relative to max in range
   └─ Weighted sum → raw score → curve mapping → gap in minutes

3. BUILD available time slots
   ├─ Generate calendar from --start to --end (or auto-extend)
   ├─ Remove non-working days (weekends, holidays)
   ├─ Remove non-working hours
   └─ Apply random day-off removals

4. APPLY realism perturbations
   ├─ Identify flow-state cluster candidates
   ├─ Select late-night commit candidates
   ├─ Select weekend commit slots
   └─ Add jitter to all timestamps

5. SCHEDULE commits into time slots
   ├─ Walk commits in order, consuming gap time from available slots
   ├─ If gap crosses day boundary, resume at start of next available day
   ├─ If total time exceeds available slots:
   │   ├─ If --end specified: WARN and compress gaps proportionally
   │   └─ If no --end: extend end date and report
   └─ Assign final timestamp to each commit

6. REWRITE (if not preview mode)
   ├─ Use git filter-branch or git filter-repo
   ├─ Set GIT_AUTHOR_DATE and GIT_COMMITTER_DATE
   ├─ Optionally set GIT_AUTHOR_NAME/EMAIL
   └─ Report success with new HEAD SHA
```

---

## Multi-Author Handling

When `--only-author` is specified:

1. Non-matching commits retain their original timestamps
2. Matching commits are extracted and rescheduled
3. New timestamps must maintain **topological ordering** — a rescheduled commit cannot be dated before a non-matching commit that it depends on
4. If a conflict arises (matching commit's new date would precede its non-matching parent), the matching commit is pushed forward to `parent_date + min_gap`

This is the trickiest part of the implementation and needs careful testing.

---

## Edge Cases & Safety

| Scenario | Behavior |
|----------|----------|
| More work time than available slots | Warn, then either compress or auto-extend |
| Commit range includes commits by other authors | Skip unless `--only-author` matches |
| Empty commits (no diff) | Assign `min_gap` |
| Single commit | Just restamp to `--start` + jitter |
| `--start` is in the future | Allow it (scheduling future work is valid) |
| Repository has unsigned commits being resigned | Out of scope — warn if GPG signatures detected |
| Shallow clone | Warn that not all history may be available |
| Submodule pointer changes | Treat as single-file change |
| Binary files in diff | Use byte-size heuristic only (lines = 0) |

### Safety Measures

- **`preview` is the default recommendation** — always preview before spreading
- **Operates on current branch** — user should work on a copy/branch if unsure
- **GPG signature warning** — signed commits will lose their signatures; warn prominently
- **Detects if commits have already been pushed** — warns that force-push will be required

---

## Implementation Phases

### Phase 1: MVP (Core Functionality)
- Commit enumeration and linear scheduling
- Basic complexity scoring (lines + files + bytes)
- Simple gap-to-timeslot mapping with working hours
- `preview` and `spread` commands
- Config file creation via `init`
- Single-author repos only
- `--topology=flatten` only

### Phase 2: Realism
- Jitter, late-night commits, weekend commits
- Flow-state clustering
- Holiday calendar integration
- Random day-off logic

### Phase 3: Advanced
- Multi-author support (`--only-author`)
- Branch topology preservation (`--topology=preserve`)
- Author rewriting
- Custom complexity weight profiles
- `--seed` for reproducibility

### Phase 4: Polish
- Per-repo `.git-spreader.toml` support
- Rich terminal output (progress bars, colored preview tables)
- Shell completions
- Man page / docs
- Package distribution (crates.io / PyPI)

---

## Language & Library Considerations

Final language choice is deferred, but here are the tradeoffs:

### Rust
- **Pros**: Fast, single binary distribution, `git2` crate (libgit2 bindings) is mature
- **Cons**: Higher development time, `git2` doesn't support `filter-branch`-style rewrites natively (would need to rebuild commit graph manually)
- **Rewrite strategy**: Build new commits with `git2::Commit::create()`, walking the DAG

### Python
- **Pros**: Faster to prototype, `GitPython` or `pygit2` available, rich CLI libs (typer/click/rich)
- **Cons**: Requires Python runtime, slower on huge repos
- **Rewrite strategy**: Shell out to `git filter-repo` (the modern replacement for `filter-branch`) or use its Python API directly — `git-filter-repo` is actually a Python script with a well-documented library interface

### Recommendation

**Start with Python + git-filter-repo for Phase 1-2**, then evaluate if performance on large repos warrants a Rust rewrite for Phase 3-4. `git-filter-repo` handles the hard parts of history rewriting (maintaining refs, handling octopus merges, etc.) and has a Python API that maps directly to the algorithm above. The realism engine and scoring logic are pure computation that ports easily.

---

## Competitive Analysis

### Existing Tools

| Tool | Stars | Language | Complexity-Aware | Business Hours | Realism Features | Config System |
|------|-------|----------|-----------------|----------------|------------------|---------------|
| **git-backdate** (rixx) | 334 | Python | ❌ | ✅ (binary on/off) | ❌ | ❌ (CLI only) |
| **git-redate** (PotatoLabs) | ~300 | Bash | ❌ | ❌ | ❌ | ❌ |
| **git-time-travel** (NPM) | ~50 | Node.js | ❌ | ❌ | ❌ | ❌ |
| **fake-git-history** | ~800 | Node.js | N/A (generates empty commits) | ❌ | Basic (random skip %) | ❌ |
| **git-spreader** (proposed) | — | TBD | ✅ weighted scoring | ✅ (configurable) | ✅ (full engine) | ✅ (TOML + interactive) |

### Deep Dive: git-backdate

git-backdate is the closest existing tool and the only serious comparison point. It's a well-crafted ~250-line single-file Python script under the WTFPL license (no restrictions). Key characteristics:

**What it does well:**
- Clean commit range parsing with good edge cases (ROOT, single commit, open-ended ranges)
- Human-readable date input via system `date` command (zero-dependency approach)
- Sets both author and committer date
- Respects commit ordering within the date range
- Idiomatic `git <subcommand>` installation pattern (drop file in PATH)
- Except-days support for vacations/illness

**What it does not do (git-spreader's differentiators):**

1. **No complexity-aware scheduling.** The core algorithm divides commits uniformly across available days: `commits_per_day = ceil(count / duration)`, then maps each commit's index linearly to a date. Commit #5 of 10 always goes to the midpoint regardless of whether it's a typo fix or a 2000-line refactor. This is the fundamental gap.

2. **No realism engine.** No jitter, no flow-state clustering, no probabilistic late-night/weekend commits, no holiday calendars. The distribution is mechanical — random within a day, but uniformly spaced across days.

3. **No multi-author awareness.** Cannot filter to "only my commits" in a shared repo.

4. **No topology handling.** Uses interactive rebase, which cannot preserve merge commits.

5. **No configuration persistence.** All settings are CLI flags; no config file, no per-repo overrides, no interactive setup.

6. **No dry-run/preview.** No way to see the proposed schedule before committing to the rewrite.

7. **No future scheduling.** Clamps timestamps to `datetime.now()`, preventing scheduling into the future.

**Architecture limitations:**
- The rewrite mechanism uses `git rebase -i` with a sed-generated `GIT_SEQUENCE_EDITOR`, then loops `git commit --amend` + `git rebase --continue` per commit. This is slow (one subprocess per commit) and fundamentally incompatible with merge commit preservation.
- No separation between scheduling logic and rewriting logic — everything lives in one function.
- No plugin points or extensibility architecture.

### Other Tools

- **git-redate** (PotatoLabs): Opens `$EDITOR` with commit dates for manual editing. No automation, no scheduling intelligence.
- **git-time-travel** (NPM): Splits commits into chunks and redates them. Primarily targets contribution graph manipulation rather than realistic scheduling.
- **fake-git-history**: Generates *fabricated* empty commits to paint a contribution graph. Fundamentally different use case — we're redistributing real work, not inventing fake activity.
- **git-timeline** (jrbeverly): Minimal bash script for bulk date modification. No scheduling logic.

---

## Architecture Decision: Start Fresh

### Decision

**Build git-spreader as a new standalone tool**, rather than forking or extending git-backdate.

### Rationale

The amount of reusable code from git-backdate is approximately 40-50 lines of utility functions (commit range parsing, date parsing). The ~150 lines of scheduling and rewriting logic — which constitute the tool's core — would be entirely replaced. Forking would create a repository that shares almost no functional code with its upstream but inherits misleading git history and issue tracker context.

Specific technical reasons:

1. **Scheduling engine replacement.** The uniform-distribution model (`commits_per_day = ceil(count / duration)`) is architecturally incompatible with the gap-before-commit model. This isn't a refactor — it's a complete replacement of the core algorithm.

2. **Rewriting backend replacement.** Interactive rebase (`git rebase -i` + sed + amend loop) cannot handle merge commits and is inherently slow. git-spreader will use `git filter-repo` (or direct commit graph reconstruction), which is a fundamentally different approach.

3. **New subsystems with no precedent in git-backdate.** The complexity scoring engine, realism engine, TOML configuration system, interactive init, dry-run preview, and multi-author filtering are all net-new code with no corresponding structure to extend.

4. **Dependency philosophy divergence.** git-backdate's value proposition is "zero dependencies, single file." git-spreader will need `git-filter-repo` (or equivalent), a TOML parser, and potentially `rich` for terminal output — a fundamentally different distribution model.

### What to Borrow

Despite starting fresh, several design elements from git-backdate are worth adopting:

| Element | From git-backdate | Adaptation for git-spreader |
|---------|-------------------|----------------------------|
| Commit range parsing | `get_commits()` handles ROOT, single commit, open ranges | Adopt similar logic, extend for `--only-author` filtering |
| Date parsing | System `date` command for human-readable input | Keep as fallback; add `python-dateutil` for richer parsing |
| Installation pattern | Drop `git-backdate` in PATH → `git backdate` | Same: `git-spreader` in PATH → `git spreader` |
| CLI ergonomics | Positional args for commits + dates | Adopt similar positional pattern, add subcommands |
| Safety caveats | Warns about force-push implications | Expand with GPG signature detection, push-status check |

### Community Positioning

- Acknowledge git-backdate in README as inspiration ("If you need simple, zero-dependency commit redating, check out git-backdate")
- Offer compatible CLI flags where reasonable (e.g., `--business-hours`, `--except-days`) so git-backdate users can migrate easily
- Position git-spreader as "git-backdate for people who want realistic schedules, not just redistributed timestamps"

---

## Open Questions

1. **Should the tool support `--amend-last` for quick single-commit redating?** (Common use case: "I just committed at 3 AM, make it look like 10 AM")
2. **Commit message rewriting** — any interest in normalizing commit message timestamps (e.g., "WIP 3am" → removing time references)?
3. **GitHub contribution graph awareness** — should it optimize for the contribution heatmap specifically (e.g., ensuring commits land on dates that fill gaps in the graph)?
4. **Interactive mode** — a TUI where you can drag commits to specific dates on a calendar?
