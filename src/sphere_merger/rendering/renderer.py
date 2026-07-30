"""Live pygame visualization of the physics simulation."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import PhysicsConfig, step
from sphere_merger.physics.sphere import Sphere

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


@dataclass
class RenderConfig:
    """Tunable rendering parameters, exposed for a future settings menu."""

    window_size: tuple[int, int] = (800, 600)
    background_color: tuple[int, int, int] = (30, 30, 40)
    show_level_labels: bool = True


def _scale(boundary: Boundary, window_size: tuple[int, int]) -> float:
    world_width = boundary.x_max - boundary.x_min
    world_height = boundary.y_max - boundary.y_min
    return min(window_size[0] / world_width, window_size[1] / world_height)


def _world_to_screen(
    x: float, y: float, boundary: Boundary, window_size: tuple[int, int], scale: float
) -> tuple[int, int]:
    screen_x = (x - boundary.x_min) * scale
    screen_y = window_size[1] - (y - boundary.y_min) * scale
    return int(screen_x), int(screen_y)


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


def _draw_sphere(
    screen: pygame.Surface,
    font: pygame.font.Font,
    sphere: Sphere,
    boundary: Boundary,
    window_size: tuple[int, int],
    scale: float,
    config: RenderConfig,
) -> None:
    ground_x, ground_y = _world_to_screen(
        sphere.position.x, sphere.position.y, boundary, window_size, scale
    )
    radius_px = max(int(sphere.radius * scale), 2)
    height_above_ground = sphere.position.z - boundary.z_min
    shadow_r = shadow_radius_px(radius_px, height_above_ground)
    shadow_rect = pygame.Rect(0, 0, shadow_r * 2, int(shadow_r * 2 * SHADOW_FLATTEN))
    shadow_rect.center = (ground_x, ground_y - int(shadow_r * SHADOW_CENTER_LIFT))
    pygame.draw.ellipse(screen, SHADOW_COLOR, shadow_rect)

    center = (ground_x, ground_y - int(sphere.position.z * scale))
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
    """Open a window and continuously step + draw `spheres` until it is closed."""
    if render_config is None:
        render_config = RenderConfig()

    pygame.init()
    screen = pygame.display.set_mode(render_config.window_size)
    pygame.display.set_caption("Sphere Merger")
    font = pygame.font.Font(None, 24)
    clock = pygame.time.Clock()
    scale = _scale(boundary, render_config.window_size)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        step(spheres, dt, boundary, physics_config)

        screen.fill(render_config.background_color)
        for sphere in spheres:
            _draw_sphere(
                screen, font, sphere, boundary, render_config.window_size, scale, render_config
            )
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
