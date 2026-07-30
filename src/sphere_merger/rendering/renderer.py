"""Live pygame visualization of the physics simulation."""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass

import pygame

from sphere_merger.game.shooting import shoot
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import PhysicsConfig, step
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

MAX_PREVIEW_STEPS = 400

LEVEL_COLORS = [
    (220, 80, 80),
    (80, 160, 220),
    (90, 200, 120),
    (230, 190, 70),
    (170, 100, 220),
    (240, 140, 60),
]
SHADOW_COLOR = (40, 40, 40)
LABEL_COLOR = (20, 20, 20)
SHADOW_MAX_SCALE = 0.9
SHADOW_MIN_SCALE = 0.25
SHADOW_HEIGHT_FALLOFF = 3.0
SHADOW_FLATTEN = 0.5
SHADOW_CENTER_LIFT = 0.15
BUTTON_COLOR = (60, 60, 80)
BUTTON_HOVER_COLOR = (90, 90, 120)
BUTTON_TEXT_COLOR = (230, 230, 230)
DRAG_LINE_COLOR = (250, 250, 250)
FIELD_OUTLINE_COLOR = (110, 110, 130)


@dataclass
class RenderConfig:
    """Tunable rendering parameters, exposed for a future settings menu."""

    window_size: tuple[int, int] = (800, 600)
    background_color: tuple[int, int, int] = (30, 30, 40)
    show_level_labels: bool = True
    shot_strength: float = 3.0
    min_shot_speed: float = 1.0
    max_shot_speed: float = 15.0
    random_sphere_count: int = 5


@dataclass(frozen=True)
class Viewport:
    """World-to-screen mapping for one drawable area (a window, or one cell
    of a grid): uniform scale plus the screen position of the world origin.

    A single `scale` for both axes (instead of independently stretching x
    and y to fill the area) keeps circles circular; `origin_x`/
    `origin_y_bottom` already include the centering margin, so all four
    field walls get an equal, visible border instead of one sitting flush
    against the area's edge.
    """

    scale: float
    origin_x: float
    origin_y_bottom: float


def compute_viewport(
    boundary: Boundary, area_size: tuple[float, float], area_offset: tuple[float, float] = (0, 0)
) -> Viewport:
    """Viewport that fits `boundary` centered inside `area_size`, offset by
    `area_offset` (the area's top-left corner, in screen pixels)."""
    world_width = boundary.x_max - boundary.x_min
    world_height = boundary.y_max - boundary.y_min
    scale = min(area_size[0] / world_width, area_size[1] / world_height)
    margin_x = (area_size[0] - world_width * scale) / 2
    margin_y = (area_size[1] - world_height * scale) / 2
    return Viewport(scale, area_offset[0] + margin_x, area_offset[1] + area_size[1] - margin_y)


def _world_to_screen(x: float, y: float, boundary: Boundary, viewport: Viewport) -> tuple[int, int]:
    screen_x = viewport.origin_x + (x - boundary.x_min) * viewport.scale
    screen_y = viewport.origin_y_bottom - (y - boundary.y_min) * viewport.scale
    return int(screen_x), int(screen_y)


def field_rect(boundary: Boundary, viewport: Viewport) -> pygame.Rect:
    world_width = boundary.x_max - boundary.x_min
    world_height = boundary.y_max - boundary.y_min
    return pygame.Rect(
        int(viewport.origin_x),
        int(viewport.origin_y_bottom - world_height * viewport.scale),
        int(world_width * viewport.scale),
        int(world_height * viewport.scale),
    )


def shadow_radius_px(radius_px: int, height_above_ground: float) -> int:
    """Shadow size for a sphere at `height_above_ground` (world units).

    Shrinks as the sphere rises, down to a floor of `SHADOW_MIN_SCALE` so it
    never fully disappears.

    >>> shadow_radius_px(100, 0.0)
    90
    >>> shadow_radius_px(100, 0.0) > shadow_radius_px(100, 3.0)
    True
    """
    scale = max(
        SHADOW_MAX_SCALE / (1 + height_above_ground / SHADOW_HEIGHT_FALLOFF), SHADOW_MIN_SCALE
    )
    return max(int(radius_px * scale), 1)


def _sphere_screen_center(
    sphere: Sphere, boundary: Boundary, viewport: Viewport
) -> tuple[int, int]:
    ground_x, ground_y = _world_to_screen(sphere.position.x, sphere.position.y, boundary, viewport)
    return ground_x, ground_y - int(sphere.position.z * viewport.scale)


def _sphere_at_screen_pos(
    spheres: list[Sphere], pos: tuple[int, int], boundary: Boundary, viewport: Viewport
) -> Sphere | None:
    """Topmost sphere whose drawn circle contains `pos`, if any."""
    for sphere in reversed(spheres):
        center_x, center_y = _sphere_screen_center(sphere, boundary, viewport)
        radius_px = max(int(sphere.radius * viewport.scale), 2)
        dx, dy = pos[0] - center_x, pos[1] - center_y
        if dx * dx + dy * dy <= radius_px * radius_px:
            return sphere
    return None


def _random_scenario(boundary: Boundary, count: int) -> list[Sphere]:
    """A fresh, non-deterministic set of spheres to play around with.

    Unseeded on purpose: this is a manual exploration tool, not the
    reproducible simulation/agent logic the project's determinism
    requirements apply to.
    """
    spheres = []
    for _ in range(count):
        radius = random.uniform(0.4, 1.0)
        x = random.uniform(boundary.x_min + radius, boundary.x_max - radius)
        y = random.uniform(boundary.y_min + radius, boundary.y_max - radius)
        z = random.uniform(boundary.z_min + radius, boundary.z_min + radius + 8.0)
        vx = random.uniform(-2.0, 2.0)
        vy = random.uniform(-2.0, 2.0)
        level = random.randint(0, 3)
        spheres.append(Sphere(Vector3(x, y, z), Vector3(vx, vy, 0.0), radius=radius, level=level))
    return spheres


def _predicted_flight_distance(
    sphere: Sphere,
    angle_degrees: float,
    speed: float,
    boundary: Boundary,
    physics_config: PhysicsConfig,
    dt: float,
    max_distance: float,
) -> float:
    """Simulate a shot in isolation to estimate how far it would travel.

    Mass-independent by construction: friction/gravity/resting in `step`
    have no mass term (mass only matters for sphere-sphere collisions, and
    there is only one sphere in this preview). Capped at `max_distance` so
    the aiming line never grows absurdly long.
    """
    preview = copy.deepcopy(sphere)
    shoot(preview, angle_degrees, speed)
    start_x, start_y = preview.position.x, preview.position.y
    for _ in range(MAX_PREVIEW_STEPS):
        step([preview], dt, boundary, physics_config)
        if preview.velocity.length() < 1e-3:
            break
    distance = math.hypot(preview.position.x - start_x, preview.position.y - start_y)
    return min(distance, max_distance)


def draw_button(
    screen: pygame.Surface, font: pygame.font.Font, rect: pygame.Rect, label: str, hovered: bool
) -> None:
    pygame.draw.rect(screen, BUTTON_HOVER_COLOR if hovered else BUTTON_COLOR, rect, border_radius=6)
    text = font.render(label, True, BUTTON_TEXT_COLOR)
    screen.blit(text, text.get_rect(center=rect.center))


def draw_sphere(
    screen: pygame.Surface,
    font: pygame.font.Font,
    sphere: Sphere,
    boundary: Boundary,
    viewport: Viewport,
    config: RenderConfig,
) -> None:
    ground_x, ground_y = _world_to_screen(sphere.position.x, sphere.position.y, boundary, viewport)
    radius_px = max(int(sphere.radius * viewport.scale), 2)
    height_above_ground = sphere.position.z - boundary.z_min
    shadow_r = shadow_radius_px(radius_px, height_above_ground)
    shadow_rect = pygame.Rect(0, 0, shadow_r * 2, int(shadow_r * 2 * SHADOW_FLATTEN))
    shadow_rect.center = (ground_x, ground_y - int(shadow_r * SHADOW_CENTER_LIFT))
    pygame.draw.ellipse(screen, SHADOW_COLOR, shadow_rect)

    center = (ground_x, ground_y - int(sphere.position.z * viewport.scale))
    color = LEVEL_COLORS[sphere.level % len(LEVEL_COLORS)]
    pygame.draw.circle(screen, color, center, radius_px)

    if config.show_level_labels:
        label = font.render(str(sphere.level), True, LABEL_COLOR)
        screen.blit(label, label.get_rect(center=center))


def run(
    spheres: list[Sphere],
    boundary: Boundary,
    physics_config: PhysicsConfig | None = None,
    render_config: RenderConfig | None = None,
    dt: float = 1 / 60,
) -> None:
    """Open a window and continuously step + draw `spheres` until it is closed.

    Reset/Random buttons and click-drag shooting are exploration aids, not
    part of the actual game: Reset restores the last starting scenario
    (the initial `spheres`, or the last "Random" draw); Random replaces it
    with a fresh, unseeded scenario and makes that the new reset point;
    click-dragging a sphere pauses physics and, on release, launches it
    opposite the drag direction, scaled by drag length.
    """
    if render_config is None:
        render_config = RenderConfig()
    effective_physics_config = physics_config if physics_config is not None else PhysicsConfig()

    pygame.init()
    screen = pygame.display.set_mode(render_config.window_size)
    pygame.display.set_caption("Sphere Merger")
    font = pygame.font.Font(None, 24)
    clock = pygame.time.Clock()
    viewport = compute_viewport(boundary, render_config.window_size)
    field_outline = field_rect(boundary, viewport)

    initial_spheres = copy.deepcopy(spheres)
    reset_button = pygame.Rect(10, 10, 90, 32)
    random_button = pygame.Rect(110, 10, 90, 32)
    drag_sphere: Sphere | None = None
    drag_start = (0, 0)

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if reset_button.collidepoint(event.pos):
                    spheres[:] = copy.deepcopy(initial_spheres)
                elif random_button.collidepoint(event.pos):
                    spheres[:] = _random_scenario(boundary, render_config.random_sphere_count)
                    initial_spheres = copy.deepcopy(spheres)
                else:
                    drag_sphere = _sphere_at_screen_pos(spheres, event.pos, boundary, viewport)
                    drag_start = event.pos
            elif (
                event.type == pygame.MOUSEBUTTONUP and event.button == 1 and drag_sphere is not None
            ):
                shot_dx = (drag_start[0] - mouse_pos[0]) / viewport.scale
                shot_dy = -(drag_start[1] - mouse_pos[1]) / viewport.scale
                drag_length = math.hypot(shot_dx, shot_dy)
                if drag_length > 1e-6:
                    angle_degrees = math.degrees(math.atan2(shot_dy, shot_dx))
                    speed = drag_length * render_config.shot_strength
                    speed = min(
                        max(speed, render_config.min_shot_speed), render_config.max_shot_speed
                    )
                    shoot(drag_sphere, angle_degrees, speed)
                drag_sphere = None

        if drag_sphere is None:
            step(spheres, dt, boundary, effective_physics_config)

        screen.fill(render_config.background_color)
        pygame.draw.rect(screen, FIELD_OUTLINE_COLOR, field_outline, 2)
        for sphere in spheres:
            draw_sphere(screen, font, sphere, boundary, viewport, render_config)

        if drag_sphere is not None:
            start_center = _sphere_screen_center(drag_sphere, boundary, viewport)
            shot_dx = (drag_start[0] - mouse_pos[0]) / viewport.scale
            shot_dy = -(drag_start[1] - mouse_pos[1]) / viewport.scale
            drag_length = math.hypot(shot_dx, shot_dy)
            if drag_length > 1e-6:
                angle_degrees = math.degrees(math.atan2(shot_dy, shot_dx))
                speed = drag_length * render_config.shot_strength
                speed = min(max(speed, render_config.min_shot_speed), render_config.max_shot_speed)
                field_width = boundary.x_max - boundary.x_min
                predicted_distance = _predicted_flight_distance(
                    drag_sphere,
                    angle_degrees,
                    speed,
                    boundary,
                    effective_physics_config,
                    dt,
                    max_distance=field_width * 3,
                )
                line_length_px = predicted_distance * viewport.scale
                direction_x, direction_y = shot_dx / drag_length, shot_dy / drag_length
                arrow_tip = (
                    start_center[0] + direction_x * line_length_px,
                    start_center[1] - direction_y * line_length_px,
                )
                pygame.draw.line(screen, DRAG_LINE_COLOR, start_center, arrow_tip, 2)
                angle_text = font.render(f"{angle_degrees % 360:.0f} deg", True, DRAG_LINE_COLOR)
                screen.blit(angle_text, (arrow_tip[0] + 10, arrow_tip[1] - 10))

        draw_button(screen, font, reset_button, "Reset", reset_button.collidepoint(mouse_pos))
        draw_button(screen, font, random_button, "Random", random_button.collidepoint(mouse_pos))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
