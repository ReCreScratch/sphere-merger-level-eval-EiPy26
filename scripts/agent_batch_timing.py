"""Timing check: play LEVEL_COUNT random levels with random, greedy and
lookahead, each timed individually, to measure whether/how far a much
larger batch (the eventual goal: ~1000 levels) is practical. Random is the
difficulty baseline this project's core question needs (README: how hard
is a level, judged by how far above chance an informed agent gets) --
greedy/lookahead alone only measure the gap between two informed
strategies, not distance from chance. Saves seed + scores + greedy/lookahead
shots for every level played -- enough to revisit any of them later, not
just the standouts, without re-simulating (shots are cheap to store: at
most shot_count tuples each) -- to the interesting-levels store. Shots are
what `scripts/shrink_top_levels.py` reuses to skip re-running lookahead's
expensive 2-ply search on levels it already has an answer for. Afterwards,
replays the top TOP_N by greedy/lookahead score gap side by side.

Also saves each shot's cumulative score and merged levels (greedy/lookahead
only) -- `agents.runner.record_playthrough` already computes both per shot,
so this is free at record time and lets later analysis filter/rank on
things like "biggest single-shot score jump" or "shots that merged nothing"
without a second simulation pass.

Random gets RANDOM_SAMPLE_COUNT independent playthroughs per level instead
of one -- unlike greedy/lookahead it doesn't search candidates, so each
playthrough costs about as much as a single greedy candidate check,
cheap enough that a whole batch of them barely registers next to
greedy/lookahead's per-level cost. A lone random sample is a noisy
"how hard is this by chance" baseline; the full list of scores (not just
their mean) is saved so mean/std/min/max are all still available later
without re-simulating. Each sample's `RandomAgent` seed is derived from
the level's own seed (`seed * RANDOM_SAMPLE_COUNT + i`), so the whole
batch stays reproducible from the saved level seeds alone -- no separate
sample-seed bookkeeping needed.

Runs once per entry in `game.interesting_levels.RUNS`, each to its own
output file -- a run's sphere count and shot-queue length make it its own
difficulty regime, not rows of the same dataset, and a new `save_run`
replaces its target file wholesale rather than merging in. Command-line
arguments select which runs to play (`... agent_batch_timing.py 6b_3s`);
without any, all of them are replayed, discarding the stored results of
every regime.

Level seeds are drawn fresh (random, not range(LEVEL_COUNT)) each run so
repeated invocations sample different levels; each level's seed is still
saved per-record (as before), which is all a later re-run/comparison needs
-- `generate_random_level` is deterministic given seed + meta.

Progress bar (pygame, same pattern as demo_find_divergence_live.py) is
drawn once per level, not per simulation step -- negligible next to the
seconds-per-level agent search itself.

Set env var SPHERE_MERGER_NO_GRID=1 to skip the final interactive grid
replay (e.g. for unattended/headless batch runs) -- the data is already
saved by then, the grid is only for visual inspection.

The exact `meta`/`levels` schema saved here is documented in
docs/data_schema.md -- update that doc in the same commit as any change
to the `save_run(...)` call below (field added/removed/renamed).
"""

from __future__ import annotations

import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date
from typing import Literal

import pygame

from sphere_merger.agents.greedy_agent import GreedyAgent
from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.random_agent import RandomAgent
from sphere_merger.agents.runner import (
    ShotRecord,
    disable_contracts_in_worker,
    final_score,
    max_combo,
    prepare_native_batch_worker,
    record_playthrough,
    shots_of,
)
from sphere_merger.game.interesting_levels import RunConfig, save_run, select_runs
from sphere_merger.game.level import LevelDefinition, generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import native_backend
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.agent_grid import run_agent_grid
from sphere_merger.rendering.renderer import RenderConfig

BACKEND: Literal["python", "rust"] = "rust"
TOP_N = 9
SHOW_GRID = os.environ.get("SPHERE_MERGER_NO_GRID") != "1"

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)
SHOT_SPEED = 25.0
RANDOM_SAMPLE_COUNT = 20
LEVEL_COUNT = 1000

WINDOW_SIZE = (900, 300)
BAR_COLOR = (90, 160, 220)
BAR_BG_COLOR = (60, 60, 80)
TEXT_COLOR = (220, 220, 220)


@dataclass
class LevelResult:
    """One level's outcome across all three agents -- times plus each
    agent's full `ShotRecord` list, from which score/combo/shots and the
    per-shot metrics (score curve, merges per shot) are all read off
    on demand rather than duplicated into separate fields.

    Random is sampled RANDOM_SAMPLE_COUNT times (see module docstring):
    `random_scores` holds every sample's final score, `random_records`
    only the first sample's full shot list, kept around just so the grid
    replay at the end has *a* random playthrough to show.
    """

    seed: int
    t_random: float
    random_scores: list[int]
    random_records: list[ShotRecord]
    t_greedy: float
    greedy_records: list[ShotRecord]
    t_lookahead: float
    lookahead_records: list[ShotRecord]

    @property
    def gap(self) -> int:
        return abs(final_score(self.greedy_records) - final_score(self.lookahead_records))


def _build_level(seed: int, run: RunConfig) -> LevelDefinition:
    return generate_random_level(
        seed=seed,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=999,
        initial_sphere_count=run.sphere_count,
        shot_count=run.shot_count,
        level_range=(0, 2),
    )


def _draw_progress(
    screen: pygame.Surface,
    font: pygame.font.Font,
    done: int,
    total: int,
    last_elapsed: float,
    run: RunConfig,
) -> None:
    bar_rect = pygame.Rect(0, 0, int(WINDOW_SIZE[0] * 0.7), 24)
    bar_rect.center = (WINDOW_SIZE[0] // 2, WINDOW_SIZE[1] // 2)

    screen.fill((30, 30, 40))
    pygame.draw.rect(screen, BAR_BG_COLOR, bar_rect, border_radius=4)
    fill_rect = bar_rect.copy()
    fill_rect.width = int(bar_rect.width * done / total)
    pygame.draw.rect(screen, BAR_COLOR, fill_rect, border_radius=4)

    label = font.render(
        f"[{run.sphere_count} Kugeln / {run.shot_count} Schuss] "
        f"Level {done}/{total} -- letzter Level: {last_elapsed:.2f}s",
        True,
        TEXT_COLOR,
    )
    screen.blit(label, label.get_rect(center=(bar_rect.centerx, bar_rect.top - 24)))
    pygame.display.flip()


def run_batch(
    run: RunConfig,
    screen: pygame.Surface,
    font: pygame.font.Font,
    greedy: GreedyAgent,
    lookahead: LookaheadAgent,
) -> None:
    """Play LEVEL_COUNT random levels under `run`'s parameters, saving the
    results to their own `run.interesting_path`.
    """
    seeds = random.sample(range(1_000_000_000), LEVEL_COUNT)

    per_level: list[LevelResult] = []
    last_elapsed = 0.0
    _draw_progress(screen, font, 0, LEVEL_COUNT, last_elapsed, run)

    total_start = time.perf_counter()
    for done, seed in enumerate(seeds):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                pygame.quit()
                raise SystemExit

        level = _build_level(seed, run)

        start = time.perf_counter()
        random_scores: list[int] = []
        random_records: list[ShotRecord] = []
        for i in range(RANDOM_SAMPLE_COUNT):
            sample_agent = RandomAgent(seed=seed * RANDOM_SAMPLE_COUNT + i, speed=SHOT_SPEED)
            records = record_playthrough(level, sample_agent)
            random_scores.append(final_score(records))
            if i == 0:
                random_records = records
        t_random = time.perf_counter() - start

        start = time.perf_counter()
        greedy_records = record_playthrough(level, greedy)
        t_greedy = time.perf_counter() - start

        start = time.perf_counter()
        lookahead_records = record_playthrough(level, lookahead)
        t_lookahead = time.perf_counter() - start

        last_elapsed = t_random + t_greedy + t_lookahead
        per_level.append(
            LevelResult(
                seed=seed,
                t_random=t_random,
                random_scores=random_scores,
                random_records=random_records,
                t_greedy=t_greedy,
                greedy_records=greedy_records,
                t_lookahead=t_lookahead,
                lookahead_records=lookahead_records,
            )
        )
        _draw_progress(screen, font, done + 1, LEVEL_COUNT, last_elapsed, run)

    total_elapsed = time.perf_counter() - total_start

    top = sorted(per_level, key=lambda entry: entry.gap, reverse=True)[:TOP_N]

    print(f"\n=== {run.sphere_count} Kugeln / {run.shot_count} Schuss ({run.name}) ===")
    print(
        f"{'seed':>10}  {'random':>6}  {'t_greedy':>9}  {'greedy':>6}  "
        f"{'t_lookahead':>11}  {'lookahead':>9}  {'combo':>5}"
    )
    for entry in per_level:
        random_mean = sum(entry.random_scores) / len(entry.random_scores)
        greedy_score = final_score(entry.greedy_records)
        lookahead_score = final_score(entry.lookahead_records)
        lookahead_combo = max_combo(entry.lookahead_records)
        print(
            f"{entry.seed:>10}  {random_mean:>6.1f}  {entry.t_greedy:>8.2f}s  "
            f"{greedy_score:>6}  {entry.t_lookahead:>10.2f}s  {lookahead_score:>9}  "
            f"{lookahead_combo:>5}"
        )

    avg_lookahead = sum(entry.t_lookahead for entry in per_level) / LEVEL_COUNT
    print(f"\n{LEVEL_COUNT} Level in {total_elapsed:.1f}s gesamt")
    est_1000_min = avg_lookahead * 1000 / 60
    print(f"lookahead: {avg_lookahead:.2f}s/Level -> ~{est_1000_min:.0f} min fuer 1000 Level")

    gaps = [entry.gap for entry in per_level]
    print(
        f"gap (greedy/lookahead): avg {sum(gaps) / len(gaps):.2f}, min {min(gaps)}, max {max(gaps)}"
    )
    random_gaps = [
        final_score(entry.lookahead_records) - sum(entry.random_scores) / len(entry.random_scores)
        for entry in per_level
    ]
    print(
        f"gap (random/lookahead): avg {sum(random_gaps) / len(random_gaps):.2f}, "
        f"min {min(random_gaps):.1f}, max {max(random_gaps):.1f}"
    )
    max_combos = [max_combo(entry.lookahead_records) for entry in per_level]
    print(
        f"lookahead max combo: avg {sum(max_combos) / len(max_combos):.2f}, max {max(max_combos)}"
    )

    save_run(
        meta={
            "source_script": f"agent_batch_timing.py[{BACKEND}]",
            "field": {
                "x_min": FIELD.x_min,
                "x_max": FIELD.x_max,
                "y_min": FIELD.y_min,
                "y_max": FIELD.y_max,
            },
            "spawn_margin": SPAWN_MARGIN,
            "target_score": 999,
            "initial_sphere_count": run.sphere_count,
            "shot_count": run.shot_count,
            "level_range": [0, 2],
            "shot_speed": SHOT_SPEED,
            "found_at": date.today().isoformat(),
            "seeds": seeds,
        },
        levels=[
            {
                "seed": entry.seed,
                "random_scores": entry.random_scores,
                "greedy_score": final_score(entry.greedy_records),
                "greedy_shots": shots_of(entry.greedy_records),
                "greedy_score_per_shot": [r.score_after for r in entry.greedy_records],
                "greedy_merges_per_shot": [r.merged_levels for r in entry.greedy_records],
                "lookahead_score": final_score(entry.lookahead_records),
                "lookahead_shots": shots_of(entry.lookahead_records),
                "lookahead_score_per_shot": [r.score_after for r in entry.lookahead_records],
                "lookahead_merges_per_shot": [r.merged_levels for r in entry.lookahead_records],
                "gap": entry.gap,
                "lookahead_max_combo": max_combo(entry.lookahead_records),
            }
            for entry in per_level
        ],
        path=run.interesting_path,
    )

    print(f"\nTop {TOP_N} nach Score-Differenz (greedy/lookahead), {run.name}:")

    cells: dict[str, tuple[LevelDefinition, list[tuple[float, float]]]] = {}
    for entry in top:
        random_mean = sum(entry.random_scores) / len(entry.random_scores)
        greedy_score = final_score(entry.greedy_records)
        lookahead_score = final_score(entry.lookahead_records)
        lookahead_combo = max_combo(entry.lookahead_records)
        print(
            f"  seed {entry.seed}: random={random_mean:.1f} greedy={greedy_score} "
            f"lookahead={lookahead_score} (gap {entry.gap}, combo {lookahead_combo})"
        )

        if SHOW_GRID:
            level = _build_level(entry.seed, run)
            cells[f"seed {entry.seed} / random sample 0 ({entry.random_scores[0]})"] = (
                level,
                shots_of(entry.random_records),
            )
            cells[f"seed {entry.seed} / greedy ({greedy_score})"] = (
                level,
                shots_of(entry.greedy_records),
            )
            cells[f"seed {entry.seed} / lookahead ({lookahead_score})"] = (
                level,
                shots_of(entry.lookahead_records),
            )

    if SHOW_GRID:
        run_agent_grid(cells, columns=9, render_config=RenderConfig(window_size=(1800, 1000)))


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("Sphere Merger -- Batch-Timing")
    font = pygame.font.Font(None, 22)

    worker_init = prepare_native_batch_worker if BACKEND == "rust" else disable_contracts_in_worker
    main_process_backend = native_backend() if BACKEND == "rust" else nullcontext()

    with ProcessPoolExecutor(initializer=worker_init) as executor, main_process_backend:
        greedy = GreedyAgent(speed=SHOT_SPEED, executor=executor)
        lookahead = LookaheadAgent(speed=SHOT_SPEED, executor=executor)

        for run in select_runs(sys.argv[1:]):
            run_batch(run, screen, font, greedy, lookahead)

    pygame.quit()
