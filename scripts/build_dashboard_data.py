"""Reduce the raw batch runs (data/interesting_levels_<n>b.json plus the
matching shrunk_levels_<n>b.json) to the single small file the dashboard
renders from: data/dashboard_data.json.

The step exists so the dashboard never sees raw records. The raw files are
~1 MB each and hold every shot of every playthrough; a chart needs
distributions and a handful of example seeds. Keeping the reduction here,
in a script over tested `metrics/` functions, also means the numbers on
the dashboard can be re-derived and diffed rather than being typed into
the page by hand (which is how the first version of this dashboard was
built, and why it silently went stale).

Reads every run in `game.interesting_levels.RUNS` and writes them all into
one file, so the dashboard can switch between them client-side without
refetching -- see docs/data_schema.md for the exact output schema, which
must be updated in the same commit as any change to what is written here.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from sphere_merger.game.interesting_levels import RUNS, RunConfig, load_run
from sphere_merger.metrics.aggregate import (
    describe,
    group_by_quartile,
    histogram,
    shared_histograms,
)
from sphere_merger.metrics.archetypes import Archetype, tag_batch
from sphere_merger.metrics.level_metrics import LevelMetrics

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "dashboard_data.json"

GAP_BIN = 10.0
SCORE_BIN = 15.0
PAYOFF_BIN = 0.1
SKILL_BIN = 2.0
HIGHLIGHTS_PER_ARCHETYPE = 10

# What each archetype's highlight list is sorted by -- the dimension that
# made the tag apply, so the top of each list is the clearest example of
# that kind of level rather than an arbitrary pick among the tagged.
HIGHLIGHT_SORT_KEY = {
    Archetype.AHA: lambda m: (m.depth_gap, m.payoff_conc or 0.0),
    Archetype.SPECTACLE: lambda m: (m.max_combo, m.lookahead_score),
    Archetype.FAIR_HARD: lambda m: (m.skill_gain or 0.0,),
    Archetype.LUCK: lambda m: (m.luck_share,),
}


def _highlight(metrics: LevelMetrics, tags: set[Archetype]) -> dict[str, Any]:
    """One level as the dashboard's example table shows it -- enough to
    recognise it and to look it up in `scripts/browse_batch_shrink.py`."""
    return {
        "seed": metrics.seed,
        "gap": metrics.depth_gap,
        "greedy_score": metrics.greedy_score,
        "lookahead_score": metrics.lookahead_score,
        "random_mean": round(metrics.random_mean, 1),
        "payoff_conc": None if metrics.payoff_conc is None else round(metrics.payoff_conc, 2),
        "skill_gain": None if metrics.skill_gain is None else round(metrics.skill_gain, 1),
        "max_combo": metrics.max_combo,
        "tags": sorted(tag.value for tag in tags),
    }


def build_dataset(config: RunConfig) -> dict[str, Any]:
    """Everything the dashboard shows for one run."""
    run = load_run(path=config.interesting_path)
    metrics = [LevelMetrics.from_record(record) for record in run["levels"]]
    tags = tag_batch(metrics)

    shrunk = load_run(path=config.shrunk_path)
    removed_by_seed = {entry["seed"]: entry["spheres_removed"] for entry in shrunk["levels"]}
    removed = [float(removed_by_seed[m.seed]) for m in metrics if m.seed in removed_by_seed]

    gaps = [float(m.depth_gap) for m in metrics]
    # Levels that scored nothing have no payoff shape to speak of (see
    # `payoff_concentration`), so they are dropped here rather than
    # counted as zero -- which would read as "front-loaded" and is a
    # different claim entirely.
    payoffs = [m.payoff_conc for m in metrics if m.payoff_conc is not None]
    skills = [m.skill_gain for m in metrics if m.skill_gain is not None]

    score_series = shared_histograms(
        {
            "random": [m.random_mean for m in metrics],
            "greedy": [float(m.greedy_score) for m in metrics],
            "lookahead": [float(m.lookahead_score) for m in metrics],
        },
        bin_width=SCORE_BIN,
    )

    # The mechanistic finding worth putting on the page: high-gap levels
    # are back-loaded (nearly all points on the last shot), which is
    # exactly the shape greedy walks into by scoring early.
    paired = [(m.payoff_conc, float(m.depth_gap)) for m in metrics if m.payoff_conc is not None]
    payoff_by_gap = group_by_quartile(
        [p for p, _ in paired], [g for _, g in paired], labels=("Q1", "Q2", "Q3", "Q4")
    )

    archetype_counts = {tag.value: 0 for tag in Archetype}
    for level_tags in tags.values():
        for tag in level_tags:
            archetype_counts[tag.value] += 1
    archetype_counts["untagged"] = sum(1 for level_tags in tags.values() if not level_tags)

    highlights: dict[str, list[dict[str, Any]]] = {}
    for tag in Archetype:
        tagged = [m for m in metrics if tag in tags[m.seed]]
        tagged.sort(key=HIGHLIGHT_SORT_KEY[tag], reverse=True)
        highlights[tag.value] = [
            _highlight(m, tags[m.seed]) for m in tagged[:HIGHLIGHTS_PER_ARCHETYPE]
        ]

    return {
        "name": config.name,
        "sphere_count": config.sphere_count,
        "level_count": len(metrics),
        "meta": {
            "shot_count": run["meta"]["shot_count"],
            "target_score": run["meta"]["target_score"],
            "shot_speed": run["meta"]["shot_speed"],
            "level_range": run["meta"]["level_range"],
            "random_samples_per_level": len(run["levels"][0]["random_scores"]),
            "found_at": run["meta"].get("found_at"),
        },
        "summary": {
            "gap": describe(gaps),
            "greedy_score": describe([float(m.greedy_score) for m in metrics]),
            "lookahead_score": describe([float(m.lookahead_score) for m in metrics]),
            "random_mean": describe([m.random_mean for m in metrics]),
            "random_std": describe([m.random_std for m in metrics]),
            "skill_gain": describe(skills),
            "payoff_conc": describe(payoffs),
            "max_combo": describe([float(m.max_combo) for m in metrics]),
            "spheres_removed": describe(removed),
        },
        "histograms": {
            "gap": vars(histogram(gaps, bin_width=GAP_BIN)),
            "scores": {
                "labels": score_series["lookahead"].labels,
                "series": {name: hist.counts for name, hist in score_series.items()},
            },
            "payoff_conc": vars(histogram(payoffs, bin_width=PAYOFF_BIN, bins=10)),
            "skill_gain": vars(histogram(skills, bin_width=SKILL_BIN)),
        },
        "archetypes": archetype_counts,
        "payoff_by_gap_quartile": {
            label: describe(values)["median"] for label, values in payoff_by_gap.items()
        },
        "highlights": highlights,
    }


if __name__ == "__main__":
    datasets = [build_dataset(config) for config in RUNS]

    OUTPUT_PATH.write_text(
        json.dumps(
            {"generated_at": date.today().isoformat(), "datasets": datasets},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    for dataset in datasets:
        counts = dataset["archetypes"]
        print(
            f"{dataset['name']}: {dataset['level_count']} Level, "
            f"Gap median {dataset['summary']['gap']['median']:.0f}, "
            + ", ".join(f"{k}={v}" for k, v in counts.items())
        )
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"\n-> {OUTPUT_PATH.name} ({size_kb:.0f} KB)")
