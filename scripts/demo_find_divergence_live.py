"""Manual demo: search live (with a progress bar) across 10 random levels
(6 initial spheres, 2 shots, shot speed 20) for the one where greedy and
lookahead's final scores differ the most (not just the first one that
differs). Once all 10 are checked, opens the usual two-cell grid (greedy
vs lookahead) on the biggest-gap level.
"""

from concurrent.futures import ProcessPoolExecutor

import pygame

from sphere_merger.agents.greedy_agent import GreedyAgent
from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.runner import disable_contracts_in_worker, record_playthrough
from sphere_merger.game.level import LevelDefinition, generate_random_level, radius_for_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector3
from sphere_merger.rendering.agent_grid import run_agent_grid
from sphere_merger.rendering.renderer import RenderConfig

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0, z_min=0.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector3(
    FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN, FIELD.z_min + radius_for_level(0)
)
SHOT_SPEED = 20.0
SEED_COUNT = 10

SEARCH_WINDOW_SIZE = (900, 300)
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


def _draw_search_progress(
    screen: pygame.Surface, font: pygame.font.Font, done: int, total: int, seed: int
) -> None:
    bar_rect = pygame.Rect(0, 0, int(SEARCH_WINDOW_SIZE[0] * 0.7), 24)
    bar_rect.center = (SEARCH_WINDOW_SIZE[0] // 2, SEARCH_WINDOW_SIZE[1] // 2)

    screen.fill((30, 30, 40))
    pygame.draw.rect(screen, BAR_BG_COLOR, bar_rect, border_radius=4)
    fill_rect = bar_rect.copy()
    fill_rect.width = int(bar_rect.width * done / total)
    pygame.draw.rect(screen, BAR_COLOR, fill_rect, border_radius=4)

    label = font.render(
        f"Suche groesste Differenz: Level {done + 1}/{total} (Seed {seed}) ...", True, TEXT_COLOR
    )
    screen.blit(label, label.get_rect(center=(bar_rect.centerx, bar_rect.top - 24)))
    pygame.display.flip()


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode(SEARCH_WINDOW_SIZE)
    pygame.display.set_caption("Sphere Merger -- Suche groesste Differenz")
    font = pygame.font.Font(None, 22)

    best: (
        tuple[int, LevelDefinition, list[tuple[float, float]], int, list[tuple[float, float]], int]
        | None
    ) = None
    best_gap = -1
    with ProcessPoolExecutor(initializer=disable_contracts_in_worker) as executor:
        greedy = GreedyAgent(speed=SHOT_SPEED, executor=executor)
        lookahead = LookaheadAgent(speed=SHOT_SPEED, executor=executor)

        for seed in range(SEED_COUNT):
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    pygame.quit()
                    raise SystemExit
            _draw_search_progress(screen, font, seed, SEED_COUNT, seed)

            level = _build_level(seed)
            greedy_shots, greedy_score = record_playthrough(level, greedy)
            lookahead_shots, lookahead_score = record_playthrough(level, lookahead)
            gap = abs(lookahead_score - greedy_score)
            if gap > best_gap:
                best_gap = gap
                best = (seed, level, greedy_shots, greedy_score, lookahead_shots, lookahead_score)

    pygame.quit()

    assert best is not None
    seed, level, greedy_shots, greedy_score, lookahead_shots, lookahead_score = best
    print(f"Groesste Differenz bei Seed {seed}: greedy={greedy_score} lookahead={lookahead_score}")
    cells = {
        f"greedy ({greedy_score})": (level, greedy_shots),
        f"lookahead ({lookahead_score})": (level, lookahead_shots),
    }
    run_agent_grid(cells, columns=2, render_config=RenderConfig(window_size=(1200, 700)))
