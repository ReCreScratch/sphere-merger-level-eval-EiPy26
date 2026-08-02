"""Minimal interactive browser for the top-gap shrink results (see
scripts/shrink_top_levels.py and data/shrunk_levels.json): pick one of
three angles on the same set of entries -- biggest gap increase from
shrinking, most spheres removed, or least changed (already tight without
shrinking) -- step through that ranked list one at a time, and replay
original vs. shrunk / greedy vs. lookahead, one view at a time, at an
adjustable speed.

Everything needed to replay is pre-recorded (see `BrowserEntry`) -- no
agents, no executor, nothing to (re)simulate here, so this opens
instantly regardless of how expensive finding/shrinking the level was.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pygame

from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.round import DT, ShotReplay
from sphere_merger.physics.sphere import Sphere
from sphere_merger.rendering.renderer import (
    BUTTON_COLOR,
    BUTTON_HOVER_COLOR,
    BUTTON_TEXT_COLOR,
    FIELD_OUTLINE_COLOR,
    HUD_TEXT_COLOR,
    LOSE_COLOR,
    WIN_COLOR,
    RenderConfig,
    Slider,
    compute_viewport,
    draw_button,
    draw_slider,
    draw_sphere,
    field_rect,
    sphere_at_screen_pos,
)

HOVER_LABEL_BG_COLOR = (20, 20, 30)

BUTTON_ACTIVE_COLOR = (70, 130, 180)
INPUT_BOX_COLOR = (50, 50, 70)
INPUT_BOX_ACTIVE_COLOR = (80, 90, 130)

MIN_SPEED = 0.25
MAX_SPEED = 2.0


class ViewMode(Enum):
    ORIGINAL = "original"
    SHRUNK = "shrunk"


class AgentMode(Enum):
    GREEDY = "greedy"
    LOOKAHEAD = "lookahead"


@dataclass
class BrowserEntry:
    """One shrink result plus everything needed to replay it -- both
    levels and both agents' shots/scores, already recorded by
    `scripts/shrink_top_levels.py` so no agent/executor is needed here."""

    seed: int
    original_gap: int
    shrunk_gap: int
    spheres_removed: int
    gap_increase: int
    original_level: LevelDefinition
    shrunk_level: LevelDefinition
    original_greedy_shots: list[tuple[float, float]]
    original_lookahead_shots: list[tuple[float, float]]
    shrunk_greedy_shots: list[tuple[float, float]]
    shrunk_lookahead_shots: list[tuple[float, float]]
    original_greedy_score: int
    original_lookahead_score: int
    shrunk_greedy_score: int
    shrunk_lookahead_score: int

    def level(self, view: ViewMode) -> LevelDefinition:
        return self.original_level if view is ViewMode.ORIGINAL else self.shrunk_level

    def shots(self, view: ViewMode, agent: AgentMode) -> list[tuple[float, float]]:
        if view is ViewMode.ORIGINAL:
            return (
                self.original_greedy_shots
                if agent is AgentMode.GREEDY
                else self.original_lookahead_shots
            )
        return (
            self.shrunk_greedy_shots if agent is AgentMode.GREEDY else self.shrunk_lookahead_shots
        )


def _categories(entries: list[BrowserEntry]) -> list[tuple[str, list[BrowserEntry]]]:
    return [
        ("Gap-Zuwachs", sorted(entries, key=lambda e: e.gap_increase, reverse=True)),
        ("Max Shrink", sorted(entries, key=lambda e: e.spheres_removed, reverse=True)),
        (
            "Kaum veraendert",
            sorted(entries, key=lambda e: (e.spheres_removed, abs(e.gap_increase))),
        ),
    ]


def _draw_toggle_button(
    screen: pygame.Surface,
    font: pygame.font.Font,
    rect: pygame.Rect,
    label: str,
    active: bool,
    hovered: bool,
) -> None:
    if active:
        color = BUTTON_ACTIVE_COLOR
    elif hovered:
        color = BUTTON_HOVER_COLOR
    else:
        color = BUTTON_COLOR
    pygame.draw.rect(screen, color, rect, border_radius=6)
    text = font.render(label, True, BUTTON_TEXT_COLOR)
    screen.blit(text, text.get_rect(center=rect.center))


def _draw_rank_box(
    screen: pygame.Surface,
    font: pygame.font.Font,
    rect: pygame.Rect,
    active: bool,
    buffer: str,
    rank: int,
    total: int,
) -> None:
    color = INPUT_BOX_ACTIVE_COLOR if active else INPUT_BOX_COLOR
    pygame.draw.rect(screen, color, rect, border_radius=4)
    text = f"{buffer}_" if active else f"{rank + 1}/{total}"
    label = font.render(text, True, BUTTON_TEXT_COLOR)
    screen.blit(label, label.get_rect(center=rect.center))


def _sphere_hover_label(sphere: Sphere, initial_spheres: list[Sphere]) -> str:
    """Identifies `sphere` against `initial_spheres` -- a snapshot of
    `state.spheres` taken right after the round last (re)started -- "original
    #i" if it's literally the same object that started there (by identity,
    not equality: a merge produces a brand-new `Sphere` even if the result
    sits almost exactly where one of its two inputs was, so identity is the
    only way to tell "never merged" from "merged with near-zero visible
    displacement"). Comparing against `level.initial_spheres` directly
    would never match anything: `start_round` deep-copies into
    `state.spheres`, so even an untouched sphere is already a different
    object from the one in `level.initial_spheres`.
    """
    for i, original in enumerate(initial_spheres):
        if original is sphere:
            identity = f"original #{i}"
            break
    else:
        identity = "merged"
    pos = f"pos ({sphere.position.x:.4f}, {sphere.position.y:.4f})"
    vel = f"vel ({sphere.velocity.x:.4f}, {sphere.velocity.y:.4f})"
    return f"{identity}  level {sphere.level}  {pos}  {vel}"


def _draw_hover_label(
    screen: pygame.Surface, font: pygame.font.Font, pos: tuple[int, int], text: str
) -> None:
    label = font.render(text, True, BUTTON_TEXT_COLOR)
    box = label.get_rect()
    box.topleft = (pos[0] + 12, pos[1] + 12)
    pygame.draw.rect(screen, HOVER_LABEL_BG_COLOR, box.inflate(8, 6))
    screen.blit(label, box)


def run_level_browser(
    entries: list[BrowserEntry], render_config: RenderConfig | None = None
) -> None:
    """Open the browser: pick a category, step through its ranked list,
    replay one (level, agent) combination at a time.

    Controls: the three category buttons switch which ranking is active
    (jumps to its first entry); Prev/Next step through the current ranking
    one at a time; the rank box jumps straight to a typed position (click
    it, type a number, Enter); the two toggle buttons switch
    original/shrunk and greedy/lookahead independently, always replaying
    the newly selected combination from its start. Play/Reset match
    `agent_grid`'s: Play spawns and plays out the next shot, pausing
    automatically once settled (click again for the next one); Reset
    returns to the initial layout.

    Speed scales how many fixed physics steps run per rendered frame (via
    a fractional accumulator) rather than `dt` itself, so pacing changes
    but the replayed physics never does -- a coarser `dt` would silently
    replay a different run than the one actually recorded.
    """
    if render_config is None:
        render_config = RenderConfig(window_size=(1000, 750))
    if not entries:
        raise ValueError("run_level_browser needs at least one entry")

    categories = _categories(entries)

    pygame.init()
    screen = pygame.display.set_mode(render_config.window_size)
    pygame.display.set_caption("Sphere Merger -- Level Browser")
    font = pygame.font.Font(None, 20)
    hud_font = pygame.font.Font(None, 22)
    clock = pygame.time.Clock()

    category_index = 0
    rank_index = 0
    view_mode = ViewMode.ORIGINAL
    agent_mode = AgentMode.GREEDY
    playing = False
    step_accumulator = 0.0
    rank_input_active = False
    rank_input_buffer = ""

    def current_entry() -> BrowserEntry:
        return categories[category_index][1][rank_index]

    def make_replay() -> ShotReplay:
        entry = current_entry()
        return ShotReplay(level=entry.level(view_mode), shots=entry.shots(view_mode, agent_mode))

    replay = make_replay()
    # `start_round` (called by `ShotReplay.__post_init__`/`.reset()`) deep-copies
    # `level.initial_spheres` into `state.spheres` -- so those are never the
    # *same* objects, even right after a fresh reset with nothing touched
    # yet. Snapshotting `state.spheres` here (right after each (re)start)
    # instead of comparing against `level.initial_spheres` gives a
    # reference list that genuinely stays identity-stable for anything
    # that doesn't get merged.
    initial_spheres = list(replay.state.spheres)

    def select(new_category: int | None = None, new_rank: int | None = None) -> None:
        nonlocal category_index, rank_index, replay, playing, step_accumulator, initial_spheres
        if new_category is not None:
            category_index = new_category
            rank_index = 0
        if new_rank is not None:
            rank_index = min(max(new_rank, 0), len(categories[category_index][1]) - 1)
        replay = make_replay()
        initial_spheres = list(replay.state.spheres)
        playing = False
        step_accumulator = 0.0

    def toggle_view() -> None:
        nonlocal view_mode, replay, playing, step_accumulator, initial_spheres
        view_mode = ViewMode.SHRUNK if view_mode is ViewMode.ORIGINAL else ViewMode.ORIGINAL
        replay = make_replay()
        initial_spheres = list(replay.state.spheres)
        playing = False
        step_accumulator = 0.0

    def toggle_agent() -> None:
        nonlocal agent_mode, replay, playing, step_accumulator, initial_spheres
        agent_mode = AgentMode.LOOKAHEAD if agent_mode is AgentMode.GREEDY else AgentMode.GREEDY
        replay = make_replay()
        initial_spheres = list(replay.state.spheres)
        playing = False
        step_accumulator = 0.0

    category_buttons = [pygame.Rect(10 + i * 210, 8, 200, 32) for i in range(len(categories))]
    speed_slider = Slider(
        pygame.Rect(700, 20, 260, 8), min_value=MIN_SPEED, max_value=MAX_SPEED, value=1.0
    )
    prev_button = pygame.Rect(10, 48, 60, 32)
    rank_box = pygame.Rect(80, 48, 90, 32)
    next_button = pygame.Rect(180, 48, 60, 32)
    view_button = pygame.Rect(260, 48, 150, 32)
    agent_button = pygame.Rect(420, 48, 160, 32)
    reset_button = pygame.Rect(600, 48, 90, 32)
    play_button = pygame.Rect(700, 48, 90, 32)
    dragging_speed_slider = False

    field_top = 96
    field_area = (render_config.window_size[0], render_config.window_size[1] - field_top)

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_ESCAPE
                and not rank_input_active
            ):
                running = False
            elif event.type == pygame.KEYDOWN and rank_input_active:
                if event.key == pygame.K_RETURN:
                    if rank_input_buffer:
                        select(new_rank=int(rank_input_buffer) - 1)
                    rank_input_active = False
                    rank_input_buffer = ""
                elif event.key == pygame.K_ESCAPE:
                    rank_input_active = False
                    rank_input_buffer = ""
                elif event.key == pygame.K_BACKSPACE:
                    rank_input_buffer = rank_input_buffer[:-1]
                elif event.unicode.isdigit() and len(rank_input_buffer) < 4:
                    rank_input_buffer += event.unicode
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if rank_box.collidepoint(event.pos):
                    rank_input_active = True
                    rank_input_buffer = ""
                elif speed_slider.rect.inflate(0, 16).collidepoint(event.pos):
                    dragging_speed_slider = True
                    speed_slider.value = speed_slider.value_at(event.pos[0])
                else:
                    rank_input_active = False
                    if reset_button.collidepoint(event.pos):
                        replay.reset()
                        initial_spheres = list(replay.state.spheres)
                        playing = False
                        step_accumulator = 0.0
                    elif play_button.collidepoint(event.pos) and not playing:
                        replay.spawn_next_shot()
                        playing = True
                    elif view_button.collidepoint(event.pos):
                        toggle_view()
                    elif agent_button.collidepoint(event.pos):
                        toggle_agent()
                    elif prev_button.collidepoint(event.pos):
                        select(new_rank=rank_index - 1)
                    elif next_button.collidepoint(event.pos):
                        select(new_rank=rank_index + 1)
                    else:
                        for i, button in enumerate(category_buttons):
                            if button.collidepoint(event.pos):
                                select(new_category=i)
            elif event.type == pygame.MOUSEMOTION and dragging_speed_slider:
                speed_slider.value = speed_slider.value_at(event.pos[0])
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging_speed_slider = False

        if playing:
            step_accumulator += speed_slider.value
            while step_accumulator >= 1.0:
                replay.step_physics(DT)
                step_accumulator -= 1.0
            if replay.settled:
                playing = False

        entry = current_entry()
        level = entry.level(view_mode)
        viewport = compute_viewport(level.boundary, field_area, area_offset=(0, field_top))
        outline = field_rect(level.boundary, viewport)

        screen.fill(render_config.background_color)
        pygame.draw.rect(screen, FIELD_OUTLINE_COLOR, outline, 1)
        for sphere in replay.state.spheres:
            draw_sphere(screen, font, sphere, level.boundary, viewport, render_config)

        hovered_sphere = (
            sphere_at_screen_pos(replay.state.spheres, mouse_pos, level.boundary, viewport)
            if mouse_pos[1] >= field_top
            else None
        )
        if hovered_sphere is not None:
            _draw_hover_label(
                screen, hud_font, mouse_pos, _sphere_hover_label(hovered_sphere, initial_spheres)
            )

        for i, (name, _ranked) in enumerate(categories):
            _draw_toggle_button(
                screen,
                font,
                category_buttons[i],
                name,
                active=i == category_index,
                hovered=category_buttons[i].collidepoint(mouse_pos),
            )
        draw_slider(screen, font, speed_slider, "Speed")

        draw_button(screen, font, prev_button, "<", prev_button.collidepoint(mouse_pos))
        _draw_rank_box(
            screen,
            font,
            rank_box,
            rank_input_active,
            rank_input_buffer,
            rank_index,
            len(categories[category_index][1]),
        )
        draw_button(screen, font, next_button, ">", next_button.collidepoint(mouse_pos))
        _draw_toggle_button(
            screen,
            font,
            view_button,
            view_mode.value,
            active=False,
            hovered=view_button.collidepoint(mouse_pos),
        )
        _draw_toggle_button(
            screen,
            font,
            agent_button,
            agent_mode.value,
            active=False,
            hovered=agent_button.collidepoint(mouse_pos),
        )
        draw_button(screen, font, reset_button, "Reset", reset_button.collidepoint(mouse_pos))
        draw_button(screen, font, play_button, "Play", play_button.collidepoint(mouse_pos))

        original_count = len(entry.original_level.initial_spheres)
        shrunk_count = len(entry.shrunk_level.initial_spheres)
        info = hud_font.render(
            f"seed {entry.seed}  |  spheres {original_count} -> {shrunk_count}  |  "
            f"gap {entry.original_gap} -> {entry.shrunk_gap} ({entry.gap_increase:+d})  |  "
            f"Score {replay.state.score} / {level.target_score}",
            True,
            HUD_TEXT_COLOR,
        )
        screen.blit(info, (10, 86))

        if replay.state.is_over:
            message, color = (
                ("GEWONNEN", WIN_COLOR) if replay.state.is_won else ("VERLOREN", LOSE_COLOR)
            )
            banner = hud_font.render(message, True, color)
            screen.blit(banner, banner.get_rect(center=(outline.centerx, outline.y + 16)))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
