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


def total_value(levels: list[int]) -> int:
    """Sum of `2**level` over `levels` -- the quantity merging conserves
    exactly (two same-level spheres combine into one at `level + 1`:
    `2 * 2**L == 2**(L + 1)`), so this is invariant across a whole round no
    matter how it plays out. Nothing else in the game creates, destroys, or
    duplicates a sphere (`merge_spheres` is the only place a sphere ever
    stops existing, and always as exactly half of a same-value replacement).

    >>> total_value([0, 0, 1])
    4
    """
    return sum(2**level for level in levels)


def merge_popcount(levels: list[int]) -> int:
    """Fewest spheres `levels` can ever be reduced to by merging, regardless
    of play order or skill -- the number of set bits in `total_value`'s
    binary form (`total_value` is conserved exactly by every merge, so this
    is the same number a full binary "carry" reduction of that total would
    leave behind). `1` means the whole set can in principle collapse into a
    single sphere; anything higher is a hard ceiling no strategy can beat,
    regardless of skill or physical routing.

    >>> merge_popcount([0, 0, 1])  # 1+1+2=4=2**2, one bit set
    1
    >>> merge_popcount([0, 1])  # 1+2=3=0b11, two bits set
    2
    """
    return bin(total_value(levels)).count("1")


def _split_to_leaves(
    rng: random.Random, count: int, target_level: int, min_level: int, max_level: int
) -> list[int]:
    """`count` leaf levels from recursively splitting a single node at
    `target_level` into two children at `level - 1` -- the exact reverse of
    `merge_spheres` -- so their `total_value` sums to exactly
    `2**target_level` by construction, whatever split choices are made
    along the way. That is what lets `generate_full_mergeable_level` reach
    `merge_popcount == 1` without ever rejecting a candidate.

    Every leaf above `max_level` is split (forced -- it would not be a
    valid sphere level otherwise); a leaf at `min_level` cannot split
    further. Once every leaf is within range, splits beyond what is forced
    are chosen at random among the currently splittable leaves -- this is
    where the composition varies from call to call, not from the target
    level's choice alone.
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
    """Every `target_level` (up to `max_target_level`) `_split_to_leaves`
    can reach exactly `count` leaves from, staying within
    `[min_level, max_level]` throughout.

    Bounded below by the *forced* leaf count at that target level (split
    everything down until nothing exceeds `max_level`) and above by the
    *maximum* reachable leaf count (split everything all the way down to
    `min_level`) -- every leaf count in between is reachable too, since
    each individual split changes the leaf count by exactly one.
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
    """Like `generate_random_level`, but `merge_popcount` of every sphere
    that will ever be on the field (initial spheres *and* the shot queue,
    combined) is always exactly 1 -- the level can in principle collapse
    into a single sphere. Not a claim that any actual playthrough achieves
    that: routing same-level spheres into contact, in the right order,
    under real physics and a limited shot budget is a separate, much
    harder question this generator has no say over -- it only guarantees
    the necessary arithmetic precondition, which `generate_random_level`
    satisfies just by chance (roughly 10-15% of the time, empirically, for
    typical sphere/shot counts).

    Built by reversing `merge_spheres`: pick a target level for the single
    sphere the whole level *could* reduce to, then recursively split it
    down into exactly `initial_sphere_count + shot_count` leaves (see
    `_split_to_leaves`). Splitting conserves `total_value` exactly, the
    same invariant merging conserves, just run backwards -- so the result
    always has `merge_popcount == 1` by construction. No rejection
    sampling, no retry loop: every candidate this draws is already valid.

    The target level is drawn uniformly from every level in
    `[level_range[0], max_target_level]` that can actually produce the
    requested sphere count within `level_range` (`_feasible_target_levels`)
    -- this is where the variety between calls comes from. A target level
    equal to the forced minimum or maximum leaf count for its own value
    has exactly one possible composition (e.g. "every leaf at `min_level`"
    or "every leaf at `max_level`"); only target levels strictly between
    those bounds allow a genuinely mixed multiset of levels.

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
