"""Grid playback of precomputed agent playthroughs: one cell per named
(level, shot sequence) combination, replaying a fixed sequence of
(angle, speed) shots -- recorded ahead of time by the caller, e.g. via
`agents.runner.record_shots` -- rather than asking an agent live.

Unlike `rendering.grid_view`'s angle sweep (many copies of one scenario,
one shot each), each cell here plays an entire round -- multiple shots,
merges and scoring -- to completion. Starts paused on the level's initial
layout so it can be inspected before playback; Play starts/resumes
replaying the recorded shots, Reset returns every cell to that initial,
paused layout.

Takes shots rather than an agent so the (possibly slow) agent simulation
happens once, under the caller's control, instead of every time this
window opens.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pygame

from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.round import (
    DT,
    RoundState,
    advance_physics,
    is_settled,
    settle,
    spawn_shot,
    start_round,
)
from sphere_merger.rendering.renderer import (
    FIELD_OUTLINE_COLOR,
    LOSE_COLOR,
    WIN_COLOR,
    RenderConfig,
    Viewport,
    compute_viewport,
    draw_button,
    draw_sphere,
    field_rect,
)

LABEL_COLOR = (220, 220, 220)


@dataclass
class _Cell:
    """One named (level, agent) combination's own round, playback position
    and on-screen area."""

    label: str
    level: LevelDefinition
    shots: list[tuple[float, float]]
    viewport: Viewport
    outline: pygame.Rect
    state: RoundState = field(init=False)
    shot_index: int = field(init=False, default=0)
    combo_index: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self.state = start_round(self.level)

    def reset(self) -> None:
        self.state = start_round(self.level)
        self.shot_index = 0
        self.combo_index = 0

    @property
    def settled(self) -> bool:
        return is_settled(self.state.spheres)

    def spawn_next_shot(self) -> None:
        """Spawn the next recorded shot, if the round isn't over and any are left."""
        if not self.state.is_over and self.shot_index < len(self.shots):
            angle, speed = self.shots[self.shot_index]
            spawn_shot(self.state, angle, speed)
            self.shot_index += 1
            self.combo_index = 0

    def step_physics(self, dt: float) -> None:
        """Advance the current shot by one frame, or settle it exactly once
        it's slow enough (see `game.round.settle`'s docstring)."""
        if not self.settled:
            self.combo_index, _ = advance_physics(self.state, self.combo_index, dt=dt)
        else:
            settle(self.state.spheres)


def _draw_cell_hud(
    screen: pygame.Surface, font: pygame.font.Font, cell: _Cell, outline: pygame.Rect
) -> None:
    label = font.render(cell.label, True, LABEL_COLOR)
    screen.blit(label, (outline.x + 2, outline.y + 2))

    score_text = font.render(
        f"Score: {cell.state.score} / {cell.level.target_score}", True, LABEL_COLOR
    )
    screen.blit(score_text, (outline.x + 2, outline.bottom - 20))

    if cell.state.is_over:
        message, color = ("GEWONNEN", WIN_COLOR) if cell.state.is_won else ("VERLOREN", LOSE_COLOR)
        banner = font.render(message, True, color)
        screen.blit(banner, banner.get_rect(center=(outline.centerx, outline.y + 16)))


def run_agent_grid(
    cells: dict[str, tuple[LevelDefinition, list[tuple[float, float]]]],
    columns: int | None = None,
    render_config: RenderConfig | None = None,
    dt: float = DT,
    fullscreen: bool = False,
) -> None:
    """Lay out `cells` (label -> (level, recorded shots)) in a grid and
    replay them.

    `columns` defaults to a roughly square layout (`ceil(sqrt(len(cells)))`).
    Callers record each cell's shots themselves (e.g. via
    `agents.runner.record_shots`) before calling this -- simulating an
    agent can be slow, and doing it here would mean re-running it every
    time this window opens instead of once, under the caller's control.

    `dt` defaults to `game.round.DT`, the same step size
    `agents.runner.record_shots`/`play_shot` simulate with -- physics here
    is discrete (Euler integration, per-step collision/merge checks), so a
    different step size can genuinely change the outcome (merges
    happening/not happening) instead of just the animation's smoothness.
    Using a coarser, frame-rate-driven `dt` here would silently replay a
    *different* physics run than the one that was actually recorded, which
    defeats the point of a verified replay. This runs somewhat slower than
    real time as a result (`DT` * 60 =~0.6 simulated seconds per real
    second) -- acceptable for inspecting a playthrough, unlike
    `rendering.renderer.run_round`'s live, real-time-paced play.

    Starts paused, showing every cell's initial layout. Each Play click
    spawns the next recorded shot in every cell and plays it out until all
    cells are settled again, then pauses automatically -- so one click
    advances exactly one shot, instead of running the whole playthrough at
    once. Reset pauses and returns every cell to its initial layout (the
    same recorded shots, not recomputed).
    """
    if render_config is None:
        render_config = RenderConfig()
    if columns is None:
        columns = math.ceil(math.sqrt(len(cells)))
    rows = math.ceil(len(cells) / columns)

    pygame.init()
    if fullscreen:
        display_info = pygame.display.Info()
        render_config.window_size = (display_info.current_w, display_info.current_h)
        screen = pygame.display.set_mode(render_config.window_size, pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode(render_config.window_size)
    pygame.display.set_caption("Sphere Merger -- Agent Grid")
    font = pygame.font.Font(None, 18)
    clock = pygame.time.Clock()

    top_margin = 40
    cell_w = render_config.window_size[0] / columns
    cell_h = (render_config.window_size[1] - top_margin) / rows

    grid_cells = []
    for i, (label, (level, shots)) in enumerate(cells.items()):
        col, row = i % columns, i // columns
        viewport = compute_viewport(
            level.boundary, (cell_w, cell_h), (col * cell_w, top_margin + row * cell_h)
        )
        outline = field_rect(level.boundary, viewport)
        grid_cells.append(
            _Cell(label=label, level=level, shots=shots, viewport=viewport, outline=outline)
        )

    reset_button = pygame.Rect(10, 4, 90, 32)
    play_button = pygame.Rect(110, 4, 90, 32)
    playing = False

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if reset_button.collidepoint(event.pos):
                    playing = False
                    for cell in grid_cells:
                        cell.reset()
                elif play_button.collidepoint(event.pos) and not playing:
                    for cell in grid_cells:
                        cell.spawn_next_shot()
                    playing = True

        if playing:
            for cell in grid_cells:
                cell.step_physics(dt)
            if all(cell.settled for cell in grid_cells):
                playing = False

        screen.fill(render_config.background_color)
        for cell in grid_cells:
            pygame.draw.rect(screen, FIELD_OUTLINE_COLOR, cell.outline, 1)
            for sphere in cell.state.spheres:
                draw_sphere(screen, font, sphere, cell.level.boundary, cell.viewport, render_config)
            _draw_cell_hud(screen, font, cell, cell.outline)

        draw_button(screen, font, reset_button, "Reset", reset_button.collidepoint(mouse_pos))
        draw_button(screen, font, play_button, "Play", play_button.collidepoint(mouse_pos))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
