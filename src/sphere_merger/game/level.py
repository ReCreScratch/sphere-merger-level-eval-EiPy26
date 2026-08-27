"""Round setup: the starting field plus the ordered queue of spheres the
player or agent gets to shoot.

Hand-designed and randomly generated levels produce the same
`LevelDefinition`, so nothing downstream cares which it got. Both are
reproducible -- the former by literal values, the latter by seed.
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

    Returns `base_radius` for every level: a deliberate simplification, so
    aim, power and friction can be tuned by hand without size variety in
    the way. Since `merge_spheres` sizes merged spheres through this same
    function, every sphere on the field has the same radius -- which is
    also why `Sphere` needs no mass.

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
        shot_queue: Levels of the spheres received, in order. Known in
            full in advance rather than drawn on the fly, so levels have a
            well-defined solution and lookahead can see past one shot.
        spawn_position: Fixed point every queued sphere appears at; only
            angle and speed are chosen per shot.
        target_score: Score needed to win the round.
        physics_config: Physics tuning to simulate this level with.
        seed: Provenance for generated levels, `None` for hand-designed
            ones. Nothing reads it at runtime.
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

    Rejection sampling, so a generated level starts from a valid layout
    instead of relying on the first physics step to untangle it.

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

    Uses a private `random.Random(seed)` rather than the global `random`
    module, so generation neither depends on nor disturbs random state
    elsewhere in the process.

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


def total_value(levels: list[int]) -> int:
    """Sum of `2**level` over `levels`, the quantity merging conserves.

    A merge replaces two spheres at level L by one at L+1, and
    `2 * 2**L == 2**(L + 1)`, so the total is invariant however a round
    plays out. `merge_spheres` is the only place a sphere stops existing,
    always as half of a same-value replacement.

    >>> total_value([0, 0, 1])
    4
    """
    return sum(2**level for level in levels)


def merge_popcount(levels: list[int]) -> int:
    """Fewest spheres `levels` can be reduced to by merging, at best play.

    The number of set bits in `total_value`'s binary form: since merging
    conserves that total, no sequence of merges can do better than a full
    binary carry reduction. `1` means the set can in principle collapse
    into a single sphere; anything higher is a ceiling no skill or routing
    can beat.

    >>> merge_popcount([0, 0, 1])  # 1+1+2=4=2**2, one bit set
    1
    >>> merge_popcount([0, 1])  # 1+2=3=0b11, two bits set
    2
    """
    return bin(total_value(levels)).count("1")


def _split_to_leaves(
    rng: random.Random, count: int, target_level: int, min_level: int, max_level: int
) -> list[int]:
    """`count` leaf levels that sum to exactly `2**target_level` in value.

    Repeatedly splits a node at `level` into two at `level - 1`, the exact
    reverse of `merge_spheres`. Value is therefore conserved by
    construction, which is how `generate_full_mergeable_level` reaches
    `merge_popcount == 1` without ever rejecting a candidate.

    Leaves above `max_level` must split (they would not be valid sphere
    levels); leaves at `min_level` cannot. Once all are in range, the
    remaining splits are drawn at random among the splittable leaves --
    that is what varies the composition between calls.
    """
    leaves = [target_level]
    while any(level > max_level for level in leaves):
        i = next(k for k, level in enumerate(leaves) if level > max_level)
        level = leaves.pop(i)
        leaves.extend([level - 1, level - 1])
    while len(leaves) < count:
        splittable = [i for i, level in enumerate(leaves) if level > min_level]
        i = rng.choice(splittable)
        level = leaves.pop(i)
        leaves.extend([level - 1, level - 1])
    return leaves


def _feasible_target_levels(
    count: int, min_level: int, max_level: int, max_target_level: int
) -> list[int]:
    """Target levels from which `_split_to_leaves` can reach `count` leaves.

    The reachable range runs from the forced leaf count (split only until
    nothing exceeds `max_level`) to the maximum one (split everything down
    to `min_level`). Everything in between is reachable too, because a
    single split changes the leaf count by exactly one.
    """
    feasible = []
    for level in range(min_level, max_target_level + 1):
        forced_min = 2 ** max(0, level - max_level)
        forced_max = 2 ** (level - min_level)
        if forced_min <= count <= forced_max:
            feasible.append(level)
    return feasible


def generate_full_mergeable_level(
    seed: int,
    boundary: Boundary,
    spawn_position: Vector2,
    target_score: int,
    initial_sphere_count: int,
    shot_count: int,
    level_range: tuple[int, int] = (0, 2),
    max_target_level: int = 7,
    physics_config: PhysicsConfig | None = None,
) -> LevelDefinition:
    """Like `generate_random_level`, but with `merge_popcount` always 1.

    Counting initial spheres and shot queue together, the level can in
    principle collapse into a single sphere. That is an arithmetic
    precondition only -- whether a playthrough actually routes the right
    spheres into contact within the shot budget is a separate and much
    harder question. `generate_random_level` happens to satisfy it around
    10-15% of the time.

    Built by reversing `merge_spheres`: pick the level of the single
    sphere everything could reduce to, then split it into exactly
    `initial_sphere_count + shot_count` leaves (`_split_to_leaves`). Since
    splitting conserves `total_value`, the result is valid by
    construction -- no rejection sampling, no retry loop.

    The target level is drawn from those that can actually produce the
    requested count (`_feasible_target_levels`), which is where variety
    between calls comes from. At the extremes of that range only one
    composition exists (all leaves at `min_level`, or all at `max_level`);
    mixed levels need a target strictly in between.

    Raises:
        ValueError: if no target level up to `max_target_level` can
            produce `initial_sphere_count + shot_count` leaves within
            `level_range` -- a very large sphere/shot count relative to
            `max_target_level`.
    """
    rng = random.Random(seed)
    min_level, max_level = level_range
    count = initial_sphere_count + shot_count

    feasible = _feasible_target_levels(count, min_level, max_level, max_target_level)
    if not feasible:
        raise ValueError(
            f"kein Ziel-Level bis {max_target_level} kann {count} Kugeln "
            f"innerhalb level_range={level_range} erzeugen"
        )
    target_level = rng.choice(feasible)
    leaves = _split_to_leaves(rng, count, target_level, min_level, max_level)
    rng.shuffle(leaves)
    initial_levels, shot_queue = leaves[:initial_sphere_count], leaves[initial_sphere_count:]

    initial_spheres: list[Sphere] = []
    for level in initial_levels:
        radius = radius_for_level(level)
        position = _non_overlapping_position(rng, boundary, radius, initial_spheres)
        initial_spheres.append(Sphere(position, Vector2(0.0, 0.0), radius=radius, level=level))

    return LevelDefinition(
        boundary=boundary,
        initial_spheres=initial_spheres,
        shot_queue=shot_queue,
        spawn_position=spawn_position,
        target_score=target_score,
        physics_config=physics_config if physics_config is not None else PhysicsConfig(),
        seed=seed,
    )
