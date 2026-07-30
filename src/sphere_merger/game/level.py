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
from sphere_merger.physics.vector import Vector3

BASE_RADIUS = 0.5
# Merging two same-level (same-radius) spheres combines their mass
# (radius**3), i.e. exactly doubles it -- see game/merge.py.
_MASS_GROWTH_PER_LEVEL = 2.0


def radius_for_level(level: int, base_radius: float = BASE_RADIUS) -> float:
    """Radius of a fresh sphere at `level`, consistent with merge growth.

    Scales `base_radius` by `2**(level/3)`, the size a level-0 sphere would
    reach after being repeatedly merged with same-level copies of itself up
    to `level`. Keeps hand-placed and merge-created spheres of the same
    level the same size.

    >>> round(radius_for_level(0), 5)
    0.5
    >>> round(radius_for_level(3), 5)
    1.0
    """
    return base_radius * _MASS_GROWTH_PER_LEVEL ** (level / 3)


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
    spawn_position: Vector3
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


def generate_random_level(
    seed: int,
    boundary: Boundary,
    spawn_position: Vector3,
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

    >>> field_ = Boundary(-5.0, 5.0, -5.0, 5.0, 0.0)
    >>> spawn = Vector3(0.0, 0.0, 3.0)
    >>> a = generate_random_level(42, field_, spawn, 100, 5, 10)
    >>> b = generate_random_level(42, field_, spawn, 100, 5, 10)
    >>> a == b
    True
    """
    rng = random.Random(seed)
    min_level, max_level = level_range

    initial_spheres = []
    for _ in range(initial_sphere_count):
        level = rng.randint(min_level, max_level)
        radius = radius_for_level(level)
        x = rng.uniform(boundary.x_min + radius, boundary.x_max - radius)
        y = rng.uniform(boundary.y_min + radius, boundary.y_max - radius)
        z = boundary.z_min + radius
        initial_spheres.append(
            Sphere(Vector3(x, y, z), Vector3(0.0, 0.0, 0.0), radius=radius, level=level)
        )

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
