"""Manual demo: search live (with a running counter) through levels built
by `generate_full_mergeable_level` -- every one already satisfies the
necessary arithmetic precondition for collapsing into a single sphere
(`merge_popcount == 1`) -- for the first one where `LookaheadAgent`
*actually* reduces the field to one sphere in practice.

Fixed at 2 shots deliberately: `LookaheadAgent`'s 2-ply search is only
known to be near-optimal there (see docs/data_schema.md and the
long_run.py findings on negative depth-gaps at shot_count > 2) -- at more
shots, "lookahead didn't find it" would conflate "not achievable" with
"lookahead is too short-sighted to see that far", which would make the
found percentage uninterpretable.

Stops at the first hit (not a fixed search budget, since there's no way to
know in advance how many tries that takes) and opens a single-cell replay
of the winning level. Ctrl-C or closing the window aborts the search.
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor

import pygame

from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.runner import (
    final_score,
    prepare_native_batch_worker,
    record_playthrough,
    shots_of,
)
from sphere_merger.game.level import generate_full_mergeable_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import native_backend
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.agent_grid import run_agent_grid
from sphere_merger.rendering.renderer import RenderConfig

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)
SHOT_SPEED = 25.0
SHOT_COUNT = 2
INITIAL_SPHERE_COUNT = 6
MAX_TARGET_LEVEL = 7

WINDOW_SIZE = (900, 220)
BG_COLOR = (30, 30, 40)
TEXT_COLOR = (220, 220, 220)
HIT_COLOR = (120, 220, 140)


def _draw_progress(
    screen: pygame.Surface, font: pygame.font.Font, tried: int, elapsed: float
) -> None:
    screen.fill(BG_COLOR)
    rate = tried / elapsed if elapsed > 0 else 0.0
    lines = [
        f"{INITIAL_SPHERE_COUNT} Kugeln / {SHOT_COUNT} Schuss, alle mit merge_popcount == 1",
        f"Level simuliert: {tried}",
        f"Laufzeit: {elapsed:.1f}s  ({rate:.1f} Level/s)",
        "Suche nach der ersten Lookahead-Loesung, die auf 1 Kugel kollabiert ...",
    ]
    for i, text in enumerate(lines):
        label = font.render(text, True, TEXT_COLOR)
        screen.blit(label, (20, 20 + i * 32))
    pygame.display.flip()


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("Sphere Merger -- Suche vollstaendigen Merge")
    font = pygame.font.Font(None, 24)

    found: tuple[int, int, list[tuple[float, float]]] | None = None
    tried = 0
    started = time.perf_counter()

    with ProcessPoolExecutor(initializer=prepare_native_batch_worker) as executor, native_backend():
        lookahead = LookaheadAgent(speed=SHOT_SPEED, executor=executor)

        while found is None:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    pygame.quit()
                    raise SystemExit

            level = generate_full_mergeable_level(
                seed=tried,
                boundary=FIELD,
                spawn_position=SPAWN,
                target_score=999,
                initial_sphere_count=INITIAL_SPHERE_COUNT,
                shot_count=SHOT_COUNT,
                level_range=(0, 2),
                max_target_level=MAX_TARGET_LEVEL,
            )
            records = record_playthrough(level, lookahead)
            tried += 1

            if len(records[-1].spheres_after) == 1:
                found = (tried - 1, final_score(records), shots_of(records))

            if tried % 5 == 0 or found is not None:
                _draw_progress(screen, font, tried, time.perf_counter() - started)

    pygame.quit()

    assert found is not None
    seed, score, shots = found
    elapsed = time.perf_counter() - started
    print(
        f"Gefunden nach {tried} Level(n) in {elapsed:.1f}s: Seed {seed}, "
        f"Score {score}, Feld kollabiert auf 1 Kugel."
    )
    level = generate_full_mergeable_level(
        seed=seed,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=999,
        initial_sphere_count=INITIAL_SPHERE_COUNT,
        shot_count=SHOT_COUNT,
        level_range=(0, 2),
        max_target_level=MAX_TARGET_LEVEL,
    )
    run_agent_grid(
        {f"lookahead (seed {seed}, score {score})": (level, shots)},
        columns=1,
        render_config=RenderConfig(window_size=(900, 900)),
    )
