"""Timing check: play LEVEL_COUNT random levels with random, greedy and
lookahead, each timed individually, to measure whether/how far a much
larger batch (the eventual goal: ~1000 levels) is practical. Random is the
difficulty baseline this project's core question needs (README: how hard
is a level, judged by how far above chance an informed agent gets) --
greedy/lookahead alone only measure the gap between two informed
strategies, not distance from chance. Saves minimal info (seed + scores,
not shots) for every level played -- enough to revisit any of them later,
not just the standouts -- to the interesting-levels store. Afterwards,
replays the top TOP_N by greedy/lookahead score gap side by side.

Progress bar (pygame, same pattern as demo_find_divergence_live.py) is
drawn once per level, not per simulation step -- negligible next to the
seconds-per-level agent search itself.
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from datetime import date
from typing import Literal

import pygame

from sphere_merger.agents.greedy_agent import GreedyAgent
from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.random_agent import RandomAgent
from sphere_merger.agents.runner import (
    disable_contracts_in_worker,
    prepare_native_batch_worker,
    record_playthrough,
)
from sphere_merger.game.interesting_levels import save_run
from sphere_merger.game.level import LevelDefinition, generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import native_backend
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.agent_grid import run_agent_grid
from sphere_merger.rendering.renderer import RenderConfig

BACKEND: Literal["python", "rust"] = "rust"
TOP_N = 9
SOURCE_SCRIPT = f"agent_batch_timing.py[{BACKEND}]"

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)
SHOT_SPEED = 25.0
RANDOM_SEED = 0
LEVEL_COUNT = 1000

WINDOW_SIZE = (900, 300)
BAR_COLOR = (90, 160, 220)
BAR_BG_COLOR = (60, 60, 80)
TEXT_COLOR = (220, 220, 220)


def _build_level(seed: int) -> LevelDefinition:
    return generate_random_level(
        seed=seed,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=999,
        initial_sphere_count=6,
        shot_count=2,
        level_range=(0, 2),
    )


def _draw_progress(
    screen: pygame.Surface, font: pygame.font.Font, done: int, total: int, last_elapsed: float
) -> None:
    bar_rect = pygame.Rect(0, 0, int(WINDOW_SIZE[0] * 0.7), 24)
    bar_rect.center = (WINDOW_SIZE[0] // 2, WINDOW_SIZE[1] // 2)

    screen.fill((30, 30, 40))
    pygame.draw.rect(screen, BAR_BG_COLOR, bar_rect, border_radius=4)
    fill_rect = bar_rect.copy()
    fill_rect.width = int(bar_rect.width * done / total)
    pygame.draw.rect(screen, BAR_COLOR, fill_rect, border_radius=4)

    label = font.render(
        f"Level {done}/{total} -- letzter Level: {last_elapsed:.2f}s", True, TEXT_COLOR
    )
    screen.blit(label, label.get_rect(center=(bar_rect.centerx, bar_rect.top - 24)))
    pygame.display.flip()


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("Sphere Merger -- Batch-Timing")
    font = pygame.font.Font(None, 22)

    Shots = list[tuple[float, float]]
    PerLevel = tuple[int, float, int, Shots, int, float, int, Shots, int, float, int, Shots, int]
    per_level: list[PerLevel] = []
    # seed, t_random, s_random, random_shots, random_combo, t_greedy, s_greedy,
    # greedy_shots, greedy_combo, t_lookahead, s_lookahead, lookahead_shots,
    # lookahead_combo -- combo is the longest single-shot merge chain (see
    # agents.runner.record_playthrough).
    last_elapsed = 0.0
    _draw_progress(screen, font, 0, LEVEL_COUNT, last_elapsed)

    worker_init = prepare_native_batch_worker if BACKEND == "rust" else disable_contracts_in_worker
    main_process_backend = native_backend() if BACKEND == "rust" else nullcontext()

    with ProcessPoolExecutor(initializer=worker_init) as executor, main_process_backend:
        random_agent = RandomAgent(seed=RANDOM_SEED, speed=SHOT_SPEED)
        greedy = GreedyAgent(speed=SHOT_SPEED, executor=executor)
        lookahead = LookaheadAgent(speed=SHOT_SPEED, executor=executor)

        total_start = time.perf_counter()
        for seed in range(LEVEL_COUNT):
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    pygame.quit()
                    raise SystemExit

            level = _build_level(seed)

            start = time.perf_counter()
            random_shots, random_score, random_combo = record_playthrough(level, random_agent)
            t_random = time.perf_counter() - start

            start = time.perf_counter()
            greedy_shots, greedy_score, greedy_combo = record_playthrough(level, greedy)
            t_greedy = time.perf_counter() - start

            start = time.perf_counter()
            lookahead_shots, lookahead_score, lookahead_combo = record_playthrough(level, lookahead)
            t_lookahead = time.perf_counter() - start

            last_elapsed = t_random + t_greedy + t_lookahead
            per_level.append(
                (
                    seed,
                    t_random,
                    random_score,
                    random_shots,
                    random_combo,
                    t_greedy,
                    greedy_score,
                    greedy_shots,
                    greedy_combo,
                    t_lookahead,
                    lookahead_score,
                    lookahead_shots,
                    lookahead_combo,
                )
            )
            _draw_progress(screen, font, seed + 1, LEVEL_COUNT, last_elapsed)

        total_elapsed = time.perf_counter() - total_start

    pygame.quit()

    print(
        f"{'seed':>4}  {'random':>6}  {'t_greedy':>9}  {'greedy':>6}  "
        f"{'t_lookahead':>11}  {'lookahead':>9}  {'combo':>5}"
    )
    for (
        seed,
        _t_random,
        random_score,
        _random_shots,
        _random_combo,
        t_greedy,
        greedy_score,
        _greedy_shots,
        _greedy_combo,
        t_lookahead,
        lookahead_score,
        _lookahead_shots,
        lookahead_combo,
    ) in per_level:
        print(
            f"{seed:>4}  {random_score:>6}  {t_greedy:>8.2f}s  {greedy_score:>6}  "
            f"{t_lookahead:>10.2f}s  {lookahead_score:>9}  {lookahead_combo:>5}"
        )

    avg_lookahead = sum(entry[9] for entry in per_level) / LEVEL_COUNT
    print(f"\n{LEVEL_COUNT} Level in {total_elapsed:.1f}s gesamt")
    est_1000_min = avg_lookahead * 1000 / 60
    print(f"lookahead: {avg_lookahead:.2f}s/Level -> ~{est_1000_min:.0f} min fuer 1000 Level")

    gaps = [abs(entry[6] - entry[10]) for entry in per_level]
    print(
        f"gap (greedy/lookahead): avg {sum(gaps) / len(gaps):.2f}, min {min(gaps)}, max {max(gaps)}"
    )
    random_gaps = [entry[10] - entry[2] for entry in per_level]
    print(
        f"gap (random/lookahead): avg {sum(random_gaps) / len(random_gaps):.2f}, "
        f"min {min(random_gaps)}, max {max(random_gaps)}"
    )
    max_combos = [entry[12] for entry in per_level]
    print(
        f"lookahead max combo: avg {sum(max_combos) / len(max_combos):.2f}, max {max(max_combos)}"
    )

    save_run(
        meta={
            "source_script": SOURCE_SCRIPT,
            "field": {
                "x_min": FIELD.x_min,
                "x_max": FIELD.x_max,
                "y_min": FIELD.y_min,
                "y_max": FIELD.y_max,
            },
            "spawn_margin": SPAWN_MARGIN,
            "target_score": 999,
            "initial_sphere_count": 6,
            "shot_count": 2,
            "level_range": [0, 2],
            "shot_speed": SHOT_SPEED,
            "found_at": date.today().isoformat(),
        },
        levels=[
            {
                "seed": entry[0],
                "random_score": entry[2],
                "greedy_score": entry[6],
                "lookahead_score": entry[10],
                "gap": abs(entry[6] - entry[10]),
                "lookahead_max_combo": entry[12],
            }
            for entry in per_level
        ],
    )

    top = sorted(per_level, key=lambda entry: abs(entry[6] - entry[10]), reverse=True)[:TOP_N]
    print(f"\nTop {TOP_N} nach Score-Differenz (greedy/lookahead):")

    cells: dict[str, tuple[LevelDefinition, list[tuple[float, float]]]] = {}
    for (
        seed,
        _t_random,
        random_score,
        random_shots,
        _random_combo,
        _t_greedy,
        greedy_score,
        greedy_shots,
        _greedy_combo,
        _t_lookahead,
        lookahead_score,
        lookahead_shots,
        lookahead_combo,
    ) in top:
        gap = abs(greedy_score - lookahead_score)
        print(
            f"  seed {seed}: random={random_score} greedy={greedy_score} "
            f"lookahead={lookahead_score} (gap {gap}, combo {lookahead_combo})"
        )

        level = _build_level(seed)
        cells[f"seed {seed} / random ({random_score})"] = (level, random_shots)
        cells[f"seed {seed} / greedy ({greedy_score})"] = (level, greedy_shots)
        cells[f"seed {seed} / lookahead ({lookahead_score})"] = (level, lookahead_shots)

    run_agent_grid(cells, columns=9, render_config=RenderConfig(window_size=(1800, 1000)))
