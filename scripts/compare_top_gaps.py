"""Launch the level-compare view (see rendering.level_compare) on the top
`COUNT` greedy/lookahead-gap levels of *every* regime at once, one
combined sidebar sectioned by regime name.

Complements `browse_interesting_levels.py`, which curates across several
categories for a single regime -- this instead fixes the category (gap)
and sweeps every regime, for comparing how the same kind of "interesting"
shows up as sphere count and shot count change (e.g. the gap ceiling
climbing from 92 at 8b to 184 at 10b_4s).

Usage: `python scripts/compare_top_gaps.py [regime ...]` -- without
arguments, every regime in `RUNS` that has data on disk.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from browse_interesting_levels import _build_entry  # noqa: E402

from sphere_merger.game.interesting_levels import (  # noqa: E402
    RUNS,
    RunConfig,
    load_run,
    select_runs,
)
from sphere_merger.metrics.level_metrics import LevelMetrics  # noqa: E402
from sphere_merger.rendering.level_compare import CompareEntry, run_level_compare  # noqa: E402

COUNT = 5


def top_gap_entries(run: RunConfig, count: int = COUNT) -> list[CompareEntry]:
    """`run`'s top `count` levels by greedy/lookahead gap, as compare entries."""
    try:
        source = load_run(path=run.interesting_path)
        shrunk_run = load_run(path=run.shrunk_path)
    except FileNotFoundError:
        return []
    if not source["levels"]:
        return []

    shrunk_by_seed = {entry["seed"]: entry for entry in shrunk_run["levels"]}
    metrics = [LevelMetrics.from_record(record) for record in source["levels"]]
    top = sorted(metrics, key=lambda m: m.depth_gap, reverse=True)[:count]

    entries = []
    for rank, m in enumerate(top, start=1):
        if m.seed not in shrunk_by_seed:
            continue
        reason = (
            f"[{run.name}] Gap #{rank} ({m.depth_gap}): Greedy {m.greedy_score}, "
            f"Lookahead {m.lookahead_score}"
        )
        entries.append(_build_entry(shrunk_by_seed[m.seed], shrunk_run["meta"], reason))
    return entries


if __name__ == "__main__":
    selected = select_runs(sys.argv[1:]) if sys.argv[1:] else RUNS
    combined: list[CompareEntry] = []
    for run in selected:
        entries = top_gap_entries(run)
        if entries:
            print(f"{run.name}: {len(entries)} Level")
            combined.extend(entries)

    print(f"\n{len(combined)} Level insgesamt im Compare-View")
    run_level_compare(combined)
