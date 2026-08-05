"""Side-by-side playback of one level's four (original/shrunk x
greedy/lookahead) combinations at once, picked by a caller-supplied
curated list of seeds -- unlike `rendering.level_browser`'s one-at-a-time
toggle, all four play together here so the actual difference between them
is visible directly, not something you have to remember across a toggle
click.

Reuses `game.round.ShotReplay` for playback and `rendering.renderer`'s
viewport/drawing primitives -- same building blocks as
`rendering.agent_grid`'s fixed grid, plus a clickable sidebar list for
picking which level's four panels are showing.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.round import DT, ShotReplay
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

SIDEBAR_WIDTH = 300
HEADER_HEIGHT = 46
SIDEBAR_PADDING = 8
SIDEBAR_SEED_ROW_HEIGHT = 26
SIDEBAR_LINE_HEIGHT = 15
SIDEBAR_GAP_ROW_HEIGHT = 22
SIDEBAR_SCROLLBAR_WIDTH = 4
SIDEBAR_SCROLL_SPEED = 40

LABEL_COLOR = (220, 220, 220)
SIDEBAR_BG_COLOR = (24, 24, 34)
SIDEBAR_ITEM_COLOR = (34, 34, 48)
SIDEBAR_ITEM_HOVER_COLOR = (44, 44, 60)
SIDEBAR_ITEM_ACTIVE_COLOR = (60, 90, 130)
SIDEBAR_DIVIDER_COLOR = (10, 10, 16)
SIDEBAR_TEXT_COLOR = (220, 220, 220)
SIDEBAR_MUTED_COLOR = (150, 150, 165)
SIDEBAR_SCROLLBAR_COLOR = (70, 70, 90)
GAP_UP_COLOR = (220, 90, 90)
GAP_DOWN_COLOR = (100, 160, 230)


@dataclass
class CompareEntry:
    """One curated level plus everything needed to play all four
    (original/shrunk x greedy/lookahead) combinations side by side.

    `reason` is a one-line, human-written note on why this seed made the
    curated list (highest gap, biggest shrink effect, ...) -- shown in the
    sidebar so the list is legible without cross-referencing another doc.
    """

    seed: int
    reason: str
    original_gap: int
    shrunk_gap: int
    spheres_removed: int
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

    def panels(self) -> list[tuple[str, LevelDefinition, list[tuple[float, float]]]]:
        """The four (label, level, shots) combinations, in fixed display order."""
        return [
            ("Original x Greedy", self.original_level, self.original_greedy_shots),
            ("Original x Lookahead", self.original_level, self.original_lookahead_shots),
            ("Shrunk x Greedy", self.shrunk_level, self.shrunk_greedy_shots),
            ("Shrunk x Lookahead", self.shrunk_level, self.shrunk_lookahead_shots),
        ]


@dataclass
class _Cell(ShotReplay):
    """One panel's own round, playback position and on-screen area --
    `ShotReplay` plus grid-specific display fields (see `agent_grid._Cell`,
    same pattern, kept as its own copy since the two views' cells differ
    in what else they need to carry)."""

    label: str
    viewport: Viewport
    outline: pygame.Rect


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Break `text` into lines that each fit within `max_width` pixels in `font`.

    Never splits a single word, even if it alone overflows `max_width` --
    good enough for the short, space-separated reason strings this is used
    for, not a general-purpose typesetter.
    """
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


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


def _build_cells(
    entry: CompareEntry, area_size: tuple[float, float], area_offset: tuple[float, float]
) -> list[_Cell]:
    """Lay `entry`'s four panels out in a fixed 2x2 grid within `area_size`
    (offset by `area_offset` on screen) and start each one paused on its
    initial layout."""
    cols, rows = 2, 2
    cell_w = area_size[0] / cols
    cell_h = area_size[1] / rows
    cells = []
    for i, (label, level, shots) in enumerate(entry.panels()):
        col, row = i % cols, i // cols
        offset = (area_offset[0] + col * cell_w, area_offset[1] + row * cell_h)
        viewport = compute_viewport(level.boundary, (cell_w, cell_h), offset)
        outline = field_rect(level.boundary, viewport)
        cells.append(
            _Cell(label=label, level=level, shots=shots, viewport=viewport, outline=outline)
        )
    return cells


def _layout_sidebar_items(
    entries: list[CompareEntry], small_font: pygame.font.Font
) -> list[tuple[pygame.Rect, list[str]]]:
    """Stack each entry's sidebar row directly beneath the previous one, in
    content coordinates (top of the list is y=0, independent of scroll).

    Row height follows the entry's actual wrapped line count instead of a
    fixed guess -- a fixed height either wastes space on short reasons or
    silently truncates long ones (see docs/level_shrinking.md-style lesson:
    don't assume the seen part is all there is).
    """
    text_width = SIDEBAR_WIDTH - 2 * SIDEBAR_PADDING - SIDEBAR_SCROLLBAR_WIDTH
    layouts = []
    y = 0
    for entry in entries:
        lines = _wrap_text(entry.reason, small_font, text_width)
        height = SIDEBAR_SEED_ROW_HEIGHT + len(lines) * SIDEBAR_LINE_HEIGHT + SIDEBAR_GAP_ROW_HEIGHT
        rect = pygame.Rect(0, y, SIDEBAR_WIDTH, height)
        layouts.append((rect, lines))
        y += height
    return layouts


def _clamp_scroll(scroll: float, content_height: int, visible_height: int) -> float:
    max_scroll = max(0, content_height - visible_height)
    return min(max(scroll, 0), max_scroll)


def _sidebar_index_at(
    layouts: list[tuple[pygame.Rect, list[str]]], mouse_pos: tuple[int, int], scroll: float
) -> int | None:
    """Which sidebar row (if any) contains `mouse_pos`, accounting for the
    current scroll offset -- `mouse_pos` is in screen space, `layouts`'
    rects are in content space, so the mouse position needs shifting by
    `scroll` before it can be compared against them."""
    content_pos = (mouse_pos[0], mouse_pos[1] + scroll)
    for i, (rect, _lines) in enumerate(layouts):
        if rect.collidepoint(content_pos):
            return i
    return None


def _draw_sidebar(
    screen: pygame.Surface,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    entries: list[CompareEntry],
    selected_index: int,
    mouse_pos: tuple[int, int],
    layouts: list[tuple[pygame.Rect, list[str]]],
    scroll: float,
) -> None:
    sidebar_rect = pygame.Rect(0, 0, SIDEBAR_WIDTH, screen.get_height())
    pygame.draw.rect(screen, SIDEBAR_BG_COLOR, sidebar_rect)

    previous_clip = screen.get_clip()
    screen.set_clip(sidebar_rect)

    hovered_index = _sidebar_index_at(layouts, mouse_pos, scroll)
    for i, (entry, (content_rect, lines)) in enumerate(zip(entries, layouts, strict=True)):
        rect = content_rect.move(0, -scroll)
        if rect.bottom < 0 or rect.top > sidebar_rect.height:
            continue  # scrolled out of view -- nothing to draw

        if i == selected_index:
            bg = SIDEBAR_ITEM_ACTIVE_COLOR
        elif i == hovered_index:
            bg = SIDEBAR_ITEM_HOVER_COLOR
        else:
            bg = SIDEBAR_ITEM_COLOR
        pygame.draw.rect(screen, bg, rect)
        pygame.draw.line(screen, SIDEBAR_DIVIDER_COLOR, rect.bottomleft, rect.bottomright)

        seed_label = font.render(f"Seed {entry.seed}", True, SIDEBAR_TEXT_COLOR)
        screen.blit(seed_label, (rect.x + SIDEBAR_PADDING, rect.y + 8))

        for j, line in enumerate(lines):
            text = small_font.render(line, True, SIDEBAR_MUTED_COLOR)
            line_y = rect.y + SIDEBAR_SEED_ROW_HEIGHT + j * SIDEBAR_LINE_HEIGHT
            screen.blit(text, (rect.x + SIDEBAR_PADDING, line_y))

        delta = entry.shrunk_gap - entry.original_gap
        gap_color = (
            GAP_UP_COLOR if delta > 0 else (GAP_DOWN_COLOR if delta < 0 else SIDEBAR_MUTED_COLOR)
        )
        gap_text = small_font.render(
            f"Gap {entry.original_gap} -> {entry.shrunk_gap}  (-{entry.spheres_removed} Kugeln)",
            True,
            gap_color,
        )
        screen.blit(gap_text, (rect.x + SIDEBAR_PADDING, rect.bottom - SIDEBAR_GAP_ROW_HEIGHT + 4))

    content_height = layouts[-1][0].bottom if layouts else 0
    if content_height > sidebar_rect.height:
        track_height = sidebar_rect.height
        thumb_height = max(24, int(track_height * track_height / content_height))
        thumb_y = int((track_height - thumb_height) * (scroll / (content_height - track_height)))
        thumb = pygame.Rect(
            SIDEBAR_WIDTH - SIDEBAR_SCROLLBAR_WIDTH, thumb_y, SIDEBAR_SCROLLBAR_WIDTH, thumb_height
        )
        pygame.draw.rect(screen, SIDEBAR_SCROLLBAR_COLOR, thumb)

    screen.set_clip(previous_clip)


def run_level_compare(
    entries: list[CompareEntry], render_config: RenderConfig | None = None
) -> None:
    """Open the compare view: a clickable sidebar list of `entries`, and a
    2x2 grid replaying the selected entry's four (original/shrunk x
    greedy/lookahead) combinations together.

    Controls: click a sidebar row to switch levels (resets the grid to its
    paused initial layout); Play spawns and plays out the next shot in all
    four panels simultaneously, pausing automatically once every panel has
    settled (click again for the next shot); Reset returns all four panels
    to their initial layout. Playing all four together, rather than one
    toggled view at a time, is the point -- greedy vs. lookahead and
    original vs. shrunk are meant to be compared *while watching*, not
    recalled from a previous click.
    """
    if not entries:
        raise ValueError("run_level_compare needs at least one entry")
    if render_config is None:
        render_config = RenderConfig(window_size=(1600, 1000))

    pygame.init()
    screen = pygame.display.set_mode(render_config.window_size)
    pygame.display.set_caption("Sphere Merger -- Level Compare")
    font = pygame.font.Font(None, 18)
    small_font = pygame.font.Font(None, 15)
    hud_font = pygame.font.Font(None, 22)
    clock = pygame.time.Clock()

    sidebar_layouts = _layout_sidebar_items(entries, small_font)
    sidebar_content_height = sidebar_layouts[-1][0].bottom
    scroll = 0.0

    area_offset = (float(SIDEBAR_WIDTH), float(HEADER_HEIGHT))
    area_size = (
        render_config.window_size[0] - SIDEBAR_WIDTH,
        render_config.window_size[1] - HEADER_HEIGHT,
    )

    selected_index = 0
    cells = _build_cells(entries[selected_index], area_size, area_offset)
    playing = False

    reset_button = pygame.Rect(SIDEBAR_WIDTH + 10, 6, 90, 32)
    play_button = pygame.Rect(SIDEBAR_WIDTH + 110, 6, 90, 32)

    def select(index: int) -> None:
        nonlocal selected_index, cells, playing
        selected_index = index
        cells = _build_cells(entries[selected_index], area_size, area_offset)
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
                    for cell in cells:
                        cell.reset()
                elif play_button.collidepoint(event.pos) and not playing:
                    for cell in cells:
                        cell.spawn_next_shot()
                    playing = True
                else:
                    index = _sidebar_index_at(sidebar_layouts, event.pos, scroll)
                    if index is not None:
                        select(index)
            elif event.type == pygame.MOUSEWHEEL and mouse_pos[0] < SIDEBAR_WIDTH:
                scroll = _clamp_scroll(
                    scroll - event.y * SIDEBAR_SCROLL_SPEED,
                    sidebar_content_height,
                    render_config.window_size[1],
                )

        if playing:
            for cell in cells:
                cell.step_physics(DT)
            if all(cell.settled for cell in cells):
                playing = False

        screen.fill(render_config.background_color)
        _draw_sidebar(
            screen, font, small_font, entries, selected_index, mouse_pos, sidebar_layouts, scroll
        )

        entry = entries[selected_index]
        header = hud_font.render(
            f"Seed {entry.seed}  |  Gap {entry.original_gap} -> {entry.shrunk_gap}  |  "
            f"{len(entry.original_level.initial_spheres)} -> "
            f"{len(entry.shrunk_level.initial_spheres)} Kugeln",
            True,
            LABEL_COLOR,
        )
        screen.blit(header, (SIDEBAR_WIDTH + 210, 14))

        for cell in cells:
            pygame.draw.rect(screen, FIELD_OUTLINE_COLOR, cell.outline, 1)
            for sphere in cell.state.spheres:
                draw_sphere(screen, font, sphere, cell.level.boundary, cell.viewport, render_config)
            _draw_cell_hud(screen, font, cell, cell.outline)

        draw_button(screen, font, reset_button, "Reset", reset_button.collidepoint(mouse_pos))
        draw_button(screen, font, play_button, "Play", play_button.collidepoint(mouse_pos))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
