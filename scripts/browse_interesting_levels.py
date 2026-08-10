"""Launch the side-by-side level-compare view (see
rendering.level_compare) on the most interesting seeds of one batch run --
the ones that best show what shrinking and the greedy/lookahead gap
actually do, picked across *several* categories rather than by sorting on
a single metric.

The picks are derived from the run's own metrics instead of being a
hand-maintained seed list: a hardcoded list goes stale the moment a run
is repeated (seeds are drawn fresh each time) and silently shows levels
from a dataset that no longer exists. Each category contributes its top
`TOP_PER_CATEGORY` levels, not just its single best -- one example only
shows the category's most extreme case, which is a poor guide to whether
the category is a real pattern or a fluke; a short ranking shows whether
the next few still look like the first. The reason strings carry the
numbers that made each one qualify plus its rank, so the sidebar is
readable without cross-referencing the data.

Command-line argument selects the run (`... browse_interesting_levels.py
8b`); default is the newest entry in `RUNS`.

Pure data loading, no agents/executor needed -- shrink_top_levels.py
already recorded everything a replay needs.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from sphere_merger.game.interesting_levels import RUNS, RunConfig, load_run, select_runs
from sphere_merger.game.level import generate_full_mergeable_level, generate_random_level
from sphere_merger.metrics.archetypes import Archetype, tag_batch
from sphere_merger.metrics.level_metrics import LevelMetrics
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.level_compare import CompareEntry, run_level_compare


def _shot_tuples(raw: list[list[float]]) -> list[tuple[float, float]]:
    return [(angle, speed) for angle, speed in raw]


TOP_PER_CATEGORY = 6
"""How many levels each category contributes to the sidebar.

One per category answers "what does this kind of level look like" with a
single example, which is enough to be misled by: the top level of a
category is by construction its most extreme, and an extreme is a bad
guide to whether the category describes a real pattern. A short ranking
shows whether the second and sixth still look like the first.
"""


SortKey = float | tuple[float, float]


def _top(
    metrics: list[LevelMetrics],
    key: Callable[[LevelMetrics], SortKey],
    reason: Callable[[LevelMetrics, int], str],
    candidates: list[LevelMetrics] | None = None,
    count: int = TOP_PER_CATEGORY,
) -> list[tuple[int, str]]:
    """The best `count` levels by `key` (highest wins), each with its reason.

    Empty when nothing qualifies -- a category no level in this run matches
    is skipped rather than filled with weak examples. `reason` gets the
    level's rank within the category so the sidebar shows where in the
    ranking a row sits.
    """
    pool = metrics if candidates is None else candidates
    ranked = sorted(pool, key=key, reverse=True)[:count]
    return [(m.seed, reason(m, rank)) for rank, m in enumerate(ranked, start=1)]


def curate(
    metrics: list[LevelMetrics],
    shrunk: dict[int, dict[str, Any]],
    shot_count: int,
) -> list[tuple[int, str]]:
    """The top `TOP_PER_CATEGORY` levels of every category, deduplicated.

    A level that ranks in two categories is listed once, under whichever
    came first -- showing the same seed twice would waste a sidebar row
    another kind of level could have had.
    """
    tags = tag_batch(metrics)
    tagged = {tag: [m for m in metrics if tag in tags[m.seed]] for tag in Archetype}
    removed = {seed: entry["spheres_removed"] for seed, entry in shrunk.items()}
    increase = {seed: entry["gap_increase"] for seed, entry in shrunk.items()}

    groups = [
        _top(
            metrics,
            key=lambda m: m.depth_gap,
            reason=lambda m, rank: (
                f"Hoechster Gap #{rank} ({m.depth_gap}): Greedy {m.greedy_score}, "
                f"Lookahead {m.lookahead_score}"
            ),
        ),
        _top(
            metrics,
            key=lambda m: -m.depth_gap,
            candidates=[m for m in metrics if m.depth_gap < 0],
            reason=lambda m, rank: (
                f"Lookahead VERLIERT #{rank} ({m.depth_gap}): bei {shot_count} Schuessen "
                f"reicht sein 2-Ply-Blick nicht bis zum Rundenende"
            ),
        ),
        _top(
            tagged[Archetype.SPECTACLE],
            key=lambda m: (m.max_combo, m.lookahead_score),
            candidates=tagged[Archetype.SPECTACLE],
            reason=lambda m, rank: (
                f"Laengste Combo-Kette #{rank} ({m.max_combo} Merges in einem Schuss), "
                f"Endscore {m.lookahead_score}"
            ),
        ),
        _top(
            metrics,
            key=lambda m: (m.payoff_conc or 0.0, m.depth_gap),
            candidates=[m for m in tagged[Archetype.AHA] if m.payoff_conc is not None],
            reason=lambda m, rank: (
                f"Reine Falle #{rank}: {(m.payoff_conc or 0.0):.0%} des Scores faellt erst "
                f"im letzten Schuss, Gap {m.depth_gap}"
            ),
        ),
        _top(
            metrics,
            key=lambda m: m.skill_gain or 0.0,
            candidates=[m for m in tagged[Archetype.FAIR_HARD] if m.skill_gain is not None],
            reason=lambda m, rank: (
                f"Fair-schwer #{rank}: {(m.skill_gain or 0.0):.1f} Sigma ueber dem Zufall "
                f"({m.random_mean:.0f}), aber enge Streuung"
            ),
        ),
        _top(
            metrics,
            key=lambda m: m.luck_share,
            candidates=tagged[Archetype.LUCK],
            reason=lambda m, rank: (
                f"Gluecksspiel #{rank}: {m.luck_share:.0%} der Zufallsversuche erreichen "
                f"Lookaheads {m.lookahead_score} auch so"
            ),
        ),
        _top(
            metrics,
            key=lambda m: removed.get(m.seed, 0),
            reason=lambda m, rank: (
                f"Aggressivstes Shrinking #{rank}: {removed[m.seed]} Kugeln entfernt, "
                f"Gap {m.depth_gap}"
            ),
        ),
        _top(
            metrics,
            key=lambda m: increase.get(m.seed, 0),
            reason=lambda m, rank: (
                f"Groesste Gap-Zunahme durch Shrink #{rank} (+{increase[m.seed]})"
            ),
        ),
        _top(
            metrics,
            key=lambda m: -abs(increase.get(m.seed, 0)) - abs(removed.get(m.seed, 0) - 2),
            candidates=[m for m in metrics if m.seed in removed and removed[m.seed] > 0],
            reason=lambda m, rank: (
                f"Typischer Fall #{rank}: {removed[m.seed]} Kugeln weg, "
                f"Gap {m.depth_gap} unveraendert"
            ),
        ),
    ]

    ordered: list[tuple[int, str]] = []
    seen: set[int] = set()
    for group in groups:
        for seed, reason in group:
            if seed not in seen:
                seen.add(seed)
                ordered.append((seed, reason))
    return ordered


def _build_entry(record: dict[str, Any], meta: dict[str, Any], reason: str) -> CompareEntry:
    field = meta["field"]
    boundary = Boundary(
        x_min=field["x_min"], x_max=field["x_max"], y_min=field["y_min"], y_max=field["y_max"]
    )
    spawn_position = Vector2(
        boundary.x_min + meta["spawn_margin"], boundary.y_min + meta["spawn_margin"]
    )
    generator = (
        generate_full_mergeable_level if meta.get("full_mergeable") else generate_random_level
    )
    original_level = generator(
        seed=record["seed"],
        boundary=boundary,
        spawn_position=spawn_position,
        target_score=meta["target_score"],
        initial_sphere_count=meta["initial_sphere_count"],
        shot_count=meta["shot_count"],
        level_range=tuple(meta["level_range"]),
    )
    kept = record["kept_sphere_indices"]
    shrunk_spheres = [original_level.initial_spheres[i] for i in kept]
    shrunk_level = replace(original_level, initial_spheres=shrunk_spheres)

    return CompareEntry(
        seed=record["seed"],
        reason=reason,
        original_gap=record["original_gap"],
        shrunk_gap=record["shrunk_gap"],
        spheres_removed=record["spheres_removed"],
        original_level=original_level,
        shrunk_level=shrunk_level,
        original_greedy_shots=_shot_tuples(record["original_greedy_shots"]),
        original_lookahead_shots=_shot_tuples(record["original_lookahead_shots"]),
        shrunk_greedy_shots=_shot_tuples(record["shrunk_greedy_shots"]),
        shrunk_lookahead_shots=_shot_tuples(record["shrunk_lookahead_shots"]),
        original_greedy_score=record["original_greedy_score"],
        original_lookahead_score=record["original_lookahead_score"],
        shrunk_greedy_score=record["shrunk_greedy_score"],
        shrunk_lookahead_score=record["shrunk_lookahead_score"],
    )


def entries_for(run: RunConfig) -> list[CompareEntry]:
    """The curated compare entries for `run`, ready for `run_level_compare`."""
    source = load_run(path=run.interesting_path)
    shrunk_run = load_run(path=run.shrunk_path)
    shrunk_by_seed = {entry["seed"]: entry for entry in shrunk_run["levels"]}

    metrics = [LevelMetrics.from_record(record) for record in source["levels"]]
    picks = curate(metrics, shrunk_by_seed, shot_count=run.shot_count)
    return [
        _build_entry(shrunk_by_seed[seed], shrunk_run["meta"], reason)
        for seed, reason in picks
        if seed in shrunk_by_seed
    ]


if __name__ == "__main__":
    selected = select_runs(sys.argv[1:]) if sys.argv[1:] else (RUNS[-1],)
    for config in selected:
        entries = entries_for(config)
        print(f"\n{config.name}: {len(entries)} kuratierte Level")
        for entry in entries:
            print(f"  seed {entry.seed:>10}  {entry.reason}")
        run_level_compare(entries)
