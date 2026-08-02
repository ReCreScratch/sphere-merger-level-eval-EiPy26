"""Angle-sweep grid view: run many independent copies of one scenario at
once, each launching the same sphere at a different starting angle.

Quick visual sanity check for how sensitive the outcome is to the shot
angle, and a demonstration that simulations are fully independent (each
just a `list[Sphere]` plus config objects, no shared state) -- the same
property that would let a real agent batch evaluation split this across
processes without any extra work.
"""

from __future__ import annotations

import copy

import pygame

from sphere_merger.game.shooting import shoot
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import PhysicsConfig, step
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.renderer import (
    FIELD_OUTLINE_COLOR,
    RenderConfig,
    compute_viewport,
    draw_button,
    draw_sphere,
    field_rect,
)

LABEL_COLOR = (220, 220, 220)


def _build_instances(
    spheres: list[Sphere],
    shot_sphere_index: int,
    boundary: Boundary,
    cell_count: int,
    angle_step: float,
    speed: float,
) -> list[list[Sphere]]:
    instances = []
    for i in range(cell_count):
        instance_spheres = copy.deepcopy(spheres)
        shot_sphere = instance_spheres[shot_sphere_index]
        shot_sphere.position = Vector2(
            boundary.x_min + shot_sphere.radius,
            boundary.y_min + shot_sphere.radius,
        )
        shoot(shot_sphere, angle_degrees=i * angle_step, speed=speed)
        instances.append(instance_spheres)
    return instances


def run_angle_sweep(
    spheres: list[Sphere],
    shot_sphere_index: int,
    boundary: Boundary,
    columns: int = 4,
    rows: int = 2,
    speed: float = 6.0,
    angle_range_degrees: float = 90.0,
    duration_seconds: float = 10.0,
    physics_config: PhysicsConfig | None = None,
    render_config: RenderConfig | None = None,
    dt: float = 1 / 60,
    fullscreen: bool = False,
) -> None:
    """Show `columns * rows` copies of `spheres` side by side, each with
    `spheres[shot_sphere_index]` launched from the field's bottom-left
    corner at the same `speed` but an evenly spaced, distinct angle between
    0 and `angle_range_degrees` -- a quarter turn by default, so every shot
    heads into the field instead of straight into a wall.

    Every cell steps its own independent sphere list; physics stops
    advancing once `duration_seconds` of simulated time have passed. A
    Restart button re-launches all cells from scratch without closing the
    window; otherwise it stays open (showing the final state) until closed.
    `fullscreen` uses the current desktop resolution (overriding
    `render_config.window_size`) and has no window chrome to close, so Esc
    quits too.
    """
    if physics_config is None:
        physics_config = PhysicsConfig()
    if render_config is None:
        render_config = RenderConfig()

    cell_count = columns * rows
    angle_step = angle_range_degrees / cell_count

    pygame.init()
    if fullscreen:
        display_info = pygame.display.Info()
        render_config.window_size = (display_info.current_w, display_info.current_h)
        screen = pygame.display.set_mode(render_config.window_size, pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode(render_config.window_size)
    pygame.display.set_caption("Sphere Merger -- Angle Sweep")
    font = pygame.font.Font(None, 18)
    clock = pygame.time.Clock()

    cell_w = render_config.window_size[0] / columns
    cell_h = render_config.window_size[1] / rows
    viewports = []
    outlines = []
    for i in range(cell_count):
        col, row = i % columns, i // columns
        viewport = compute_viewport(boundary, (cell_w, cell_h), (col * cell_w, row * cell_h))
        viewports.append(viewport)
        outlines.append(field_rect(boundary, viewport))

    restart_button = pygame.Rect(10, 10, 90, 32)
    instances = _build_instances(
        spheres, shot_sphere_index, boundary, cell_count, angle_step, speed
    )
    elapsed = 0.0

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and restart_button.collidepoint(event.pos)
            ):
                instances = _build_instances(
                    spheres, shot_sphere_index, boundary, cell_count, angle_step, speed
                )
                elapsed = 0.0

        if elapsed < duration_seconds:
            for instance_spheres in instances:
                step(instance_spheres, dt, boundary, physics_config)
            elapsed += dt

        screen.fill(render_config.background_color)
        for i in range(cell_count):
            pygame.draw.rect(screen, FIELD_OUTLINE_COLOR, outlines[i], 1)
            for sphere in instances[i]:
                draw_sphere(screen, font, sphere, boundary, viewports[i], render_config)
            label = font.render(f"{i * angle_step:.0f} deg", True, LABEL_COLOR)
            screen.blit(label, (outlines[i].x + 2, outlines[i].y + 2))

        draw_button(screen, font, restart_button, "Restart", restart_button.collidepoint(mouse_pos))
        fps_text = font.render(f"{clock.get_fps():.0f} FPS", True, LABEL_COLOR)
        screen.blit(fps_text, (render_config.window_size[0] - fps_text.get_width() - 10, 10))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
