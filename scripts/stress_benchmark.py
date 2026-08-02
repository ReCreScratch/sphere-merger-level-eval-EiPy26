"""Meilenstein-3-Stresstest: 30 Kugeln, kleines Feld, eigener Laptop.

Misst Schritte/Sekunde und prüft grob, ob das System zur Ruhe kommt.
Für ein detailliertes Profil (welche Funktion wie viel Zeit kostet):

    python -m cProfile -s cumulative scripts/stress_benchmark.py
"""

import random
import time

from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import PhysicsConfig, step
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

FIELD = Boundary(x_min=-8.0, x_max=8.0, y_min=-8.0, y_max=8.0)
SPHERE_COUNT = 30
SIMULATED_SECONDS = 30.0
DT = 0.01
SEED = 42


def _random_scenario() -> list[Sphere]:
    rng = random.Random(SEED)
    spheres = []
    for _ in range(SPHERE_COUNT):
        radius = rng.uniform(0.3, 0.6)
        x = rng.uniform(FIELD.x_min + radius, FIELD.x_max - radius)
        y = rng.uniform(FIELD.y_min + radius, FIELD.y_max - radius)
        vx = rng.uniform(-2.0, 2.0)
        vy = rng.uniform(-2.0, 2.0)
        spheres.append(Sphere(Vector2(x, y), Vector2(vx, vy), radius=radius, level=0))
    return spheres


if __name__ == "__main__":
    spheres = _random_scenario()
    config = PhysicsConfig()
    n_steps = int(SIMULATED_SECONDS / DT)

    start = time.perf_counter()
    for _ in range(n_steps):
        step(spheres, DT, FIELD, config)
    elapsed = time.perf_counter() - start

    max_speed = max(s.velocity.length() for s in spheres)
    out_of_bounds = [
        s
        for s in spheres
        if not (FIELD.x_min <= s.position.x - s.radius and s.position.x + s.radius <= FIELD.x_max)
    ]

    print(f"{n_steps} steps of {SPHERE_COUNT} spheres in {elapsed:.3f}s")
    print(f"-> {n_steps / elapsed:.0f} steps/sec ({elapsed / n_steps * 1000:.3f} ms/step)")
    print(f"max final speed: {max_speed:.4f}")
    print(f"spheres out of bounds: {len(out_of_bounds)}")
