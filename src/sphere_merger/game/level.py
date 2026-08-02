"""Round setup: what the field looks like at the start and which spheres
the player/agent gets to shoot, in order.

Both hand-designed baseline levels (built directly with explicit values)
and randomly generated ones (`generate_random_level`) produce the same
`LevelDefinition`, so the rest of the game/agent code never has to care
which one it got -- and both are fully reproducible: baseline levels
because their values are literal, random ones because generation is
seeded.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import PhysicsConfig
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

BASE_RADIUS = 0.5
_MAX_PLACEMENT_ATTEMPTS = 500


def radius_for_level(level: int, base_radius: float = BASE_RADIUS) -> float:
    """Radius of a fresh sphere at `level`.

    Currently returns `base_radius` unconditionally, regardless of `level`
    -- a temporary simplification (uniform ball size/mass) for tuning aim,
    power and friction by hand without size variety in the way. The
    level-scaled radius this used to return (`base_radius * 2**(level/3)`)
    is still what `merge_spheres` computes from conserved mass on every
    merge, independently of this function, so merged spheres already grow
    regardless.

    >>> radius_for_level(0) == radius_for_level(3) == BASE_RADIUS
    True
    """
    return base_radius


@dataclass
class LevelDefinition:
    """Everything needed to reproducibly set up and play one round.

    Attributes:
        boundary: Play field.
        initial_spheres: Fixed starting state of the field.
        shot_queue: Levels of the spheres the player/agent receives, in
            order -- known in full in advance (not drawn on the fly), so
            baseline levels have a well-defined solution and a lookahead
            agent can see more than one shot ahead.
        spawn_position: Fixed point every queued sphere appears at; only
            angle/speed (see `game.shooting.shoot`) are chosen per shot.
        target_score: Score needed to win the round.
        physics_config: Physics tuning to simulate this level with.
        seed: Seed used to generate this level, if it was generated
            (`None` for hand-designed levels). Provenance only -- nothing
            reads it at runtime.
    """

    boundary: Boundary
    initial_spheres: list[Sphere]
    shot_queue: list[int]
    spawn_position: Vector2
    target_score: int
    physics_config: PhysicsConfig = field(default_factory=PhysicsConfig)
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.target_score <= 0:
            raise ValueError(f"target_score must be positive, got {self.target_score}")
        if not self.shot_queue:
            raise ValueError("shot_queue must not be empty")
        if any(level < 0 for level in self.shot_queue):
            raise ValueError(f"shot_queue levels must be non-negative, got {self.shot_queue}")


def _non_overlapping_position(
    rng: random.Random, boundary: Boundary, radius: float, placed: list[Sphere]
) -> Vector2:
    """A position that doesn't overlap any of `placed`.

    Rejection sampling: keeps drawing candidates from `rng` until one
    clears every already-placed sphere, so a generated level starts from a
    valid, non-overlapping layout instead of relying on the first shot's
    physics step to push overlapping spawns apart.

    Raises:
        ValueError: if no clear position is found within
            `_MAX_PLACEMENT_ATTEMPTS` tries (the field is too small/crowded
            for the requested sphere count and sizes).
    """
    for _ in range(_MAX_PLACEMENT_ATTEMPTS):
        x = rng.uniform(boundary.x_min + radius, boundary.x_max - radius)
        y = rng.uniform(boundary.y_min + radius, boundary.y_max - radius)
        candidate = Vector2(x, y)
        if all((candidate - other.position).length() >= radius + other.radius for other in placed):
            return candidate
    raise ValueError(
        f"could not place a non-overlapping sphere (radius {radius}) after "
        f"{_MAX_PLACEMENT_ATTEMPTS} attempts -- field too small/crowded for "
        "the requested sphere count"
    )


def generate_random_level(
    seed: int,
    boundary: Boundary,
    spawn_position: Vector2,
    target_score: int,
    initial_sphere_count: int,
    shot_count: int,
    level_range: tuple[int, int] = (0, 2),
    physics_config: PhysicsConfig | None = None,
) -> LevelDefinition:
    """Randomly generate a reproducible level from `seed`.

    Uses a private `random.Random(seed)` instance rather than the global
    `random` module, so generation never depends on (or disturbs) unrelated
    random state elsewhere in the process -- the same `seed` and parameters
    always produce the exact same level.

    >>> field_ = Boundary(-5.0, 5.0, -5.0, 5.0)
    >>> spawn = Vector2(0.0, 0.0)
    >>> a = generate_random_level(42, field_, spawn, 100, 5, 10)
    >>> b = generate_random_level(42, field_, spawn, 100, 5, 10)
    >>> a == b
    True
    """
    rng = random.Random(seed)
    min_level, max_level = level_range

    initial_spheres: list[Sphere] = []
    for _ in range(initial_sphere_count):
        level = rng.randint(min_level, max_level)
        radius = radius_for_level(level)
        position = _non_overlapping_position(rng, boundary, radius, initial_spheres)
        initial_spheres.append(Sphere(position, Vector2(0.0, 0.0), radius=radius, level=level))

    shot_queue = [rng.randint(min_level, max_level) for _ in range(shot_count)]

    return LevelDefinition(
        boundary=boundary,
        initial_spheres=initial_spheres,
        shot_queue=shot_queue,
        spawn_position=spawn_position,
        target_score=target_score,
        physics_config=physics_config if physics_config is not None else PhysicsConfig(),
        seed=seed,
    )
