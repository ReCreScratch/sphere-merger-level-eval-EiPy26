//! Native port of `physics.engine.step` (one physics step: gravity ->
//! integration -> boundary contact/friction -> pairwise collision solve),
//! for benchmarking/correctness comparison against the Python reference
//! implementation before anything is wired into the game loop for real.
//!
//! Mirrors `physics/{vector,sphere,boundary,collision,engine}.py` formula
//! for formula, same fixed iteration order, so results should match the
//! Python engine step for step (see the determinism comparison in
//! `scripts/native_step_check.py`). Spheres cross the FFI boundary as
//! plain `(x, y, z, vx, vy, vz, radius, level)` tuples rather than PyO3
//! classes -- simplest thing that works for this comparison slice; the
//! same-level exclusion `physics.engine.step`'s `collision_filter` is used
//! for in this project is passed as a plain bool (`exclude_same_level`)
//! since that's the only filter ever used, not a callback across the FFI
//! boundary.

use pyo3::prelude::*;

const VERTICAL_TILT_EPSILON: f64 = 1e-9;
const VERTICAL_TILT_AMOUNT: f64 = 1e-3;

#[derive(Clone, Copy)]
struct Vec3 {
    x: f64,
    y: f64,
    z: f64,
}

impl Vec3 {
    fn add(self, o: Vec3) -> Vec3 {
        Vec3 { x: self.x + o.x, y: self.y + o.y, z: self.z + o.z }
    }

    fn sub(self, o: Vec3) -> Vec3 {
        Vec3 { x: self.x - o.x, y: self.y - o.y, z: self.z - o.z }
    }

    fn scale(self, s: f64) -> Vec3 {
        Vec3 { x: self.x * s, y: self.y * s, z: self.z * s }
    }

    fn dot(self, o: Vec3) -> f64 {
        self.x * o.x + self.y * o.y + self.z * o.z
    }

    fn length(self) -> f64 {
        self.dot(self).sqrt()
    }
}

#[derive(Clone, Copy)]
struct SphereState {
    pos: Vec3,
    vel: Vec3,
    radius: f64,
    level: i64,
}

impl SphereState {
    fn mass(&self) -> f64 {
        // powf (general real pow, matching Python's `radius ** 3`), not
        // powi (exact repeated multiplication) -- they can differ in the
        // last bit, see docs/physics_optimizations.md.
        self.radius.powf(3.0)
    }
}

struct BoundaryState {
    x_min: f64,
    x_max: f64,
    y_min: f64,
    y_max: f64,
    z_min: f64,
    z_max: Option<f64>,
}

struct ConfigState {
    gravity: f64,
    friction: f64,
    sphere_restitution: f64,
    boundary_restitution: f64,
    rest_threshold_factor: f64,
}

fn is_colliding(a: &SphereState, b: &SphereState) -> bool {
    let dx = a.pos.x - b.pos.x;
    let dy = a.pos.y - b.pos.y;
    let dz = a.pos.z - b.pos.z;
    let radius_sum = a.radius + b.radius;
    dx * dx + dy * dy + dz * dz < radius_sum * radius_sum
}

fn distance(a: &SphereState, b: &SphereState) -> f64 {
    b.pos.sub(a.pos).length()
}

/// Exact unit vector a -> b, falling back to relative-velocity direction
/// then a fixed axis if centers coincide -- see `physics/collision.py::_raw_normal`.
fn raw_normal(a: &SphereState, b: &SphereState) -> Vec3 {
    let delta = b.pos.sub(a.pos);
    let dist = delta.length();
    if dist > 0.0 {
        return delta.scale(1.0 / dist);
    }
    let relative_velocity = b.vel.sub(a.vel);
    let speed = relative_velocity.length();
    if speed > 0.0 {
        relative_velocity.scale(1.0 / speed)
    } else {
        Vec3 { x: 1.0, y: 0.0, z: 0.0 }
    }
}

/// `raw_normal`, tilted off a near-exact vertical -- velocity solver only,
/// see `physics/collision.py::contact_normal`.
fn contact_normal(a: &SphereState, b: &SphereState) -> Vec3 {
    let normal = raw_normal(a, b);
    let horizontal = (normal.x * normal.x + normal.y * normal.y).sqrt();
    if horizontal < VERTICAL_TILT_EPSILON {
        let tilted = Vec3 { x: VERTICAL_TILT_AMOUNT, y: 0.0, z: normal.z };
        tilted.scale(1.0 / tilted.length())
    } else {
        normal
    }
}

fn resolve_overlap(a: &mut SphereState, b: &mut SphereState) {
    let normal = raw_normal(a, b);
    let overlap = a.radius + b.radius - distance(a, b);
    let total_mass = a.mass() + b.mass();
    a.pos = a.pos.sub(normal.scale(overlap * (b.mass() / total_mass)));
    b.pos = b.pos.add(normal.scale(overlap * (a.mass() / total_mass)));
}

fn resolve_velocity(
    a: &mut SphereState,
    b: &mut SphereState,
    restitution: f64,
    rest_velocity_threshold: f64,
) {
    let normal = contact_normal(a, b);
    let approach_speed = a.vel.sub(b.vel).dot(normal);
    if approach_speed <= 0.0 {
        return;
    }
    let effective_restitution =
        if approach_speed < rest_velocity_threshold { 0.0 } else { restitution };
    let impulse = (1.0 + effective_restitution) * approach_speed / (1.0 / a.mass() + 1.0 / b.mass());
    a.vel = a.vel.sub(normal.scale(impulse / a.mass()));
    b.vel = b.vel.add(normal.scale(impulse / b.mass()));
}

fn resolve_boundary(
    s: &mut SphereState,
    boundary: &BoundaryState,
    restitution: f64,
    rest_velocity_threshold: f64,
) {
    let (mut x, mut y, mut z) = (s.pos.x, s.pos.y, s.pos.z);
    let (mut vx, mut vy, mut vz) = (s.vel.x, s.vel.y, s.vel.z);
    let r = s.radius;

    if x - r < boundary.x_min {
        x = boundary.x_min + r;
        vx = if vx.abs() < rest_velocity_threshold { 0.0 } else { -vx * restitution };
    } else if x + r > boundary.x_max {
        x = boundary.x_max - r;
        vx = if vx.abs() < rest_velocity_threshold { 0.0 } else { -vx * restitution };
    }

    if y - r < boundary.y_min {
        y = boundary.y_min + r;
        vy = if vy.abs() < rest_velocity_threshold { 0.0 } else { -vy * restitution };
    } else if y + r > boundary.y_max {
        y = boundary.y_max - r;
        vy = if vy.abs() < rest_velocity_threshold { 0.0 } else { -vy * restitution };
    }

    if z - r < boundary.z_min {
        z = boundary.z_min + r;
        vz = if vz.abs() < rest_velocity_threshold { 0.0 } else { -vz * restitution };
    } else if let Some(z_max) = boundary.z_max {
        if z + r > z_max {
            z = z_max - r;
            vz = if vz.abs() < rest_velocity_threshold { 0.0 } else { -vz * restitution };
        }
    }

    s.pos = Vec3 { x, y, z };
    s.vel = Vec3 { x: vx, y: vy, z: vz };
}

/// Same fixed nested-loop order as `physics/collision.py::find_colliding_pairs`,
/// including the moving-pair skip.
fn find_colliding_pairs(spheres: &[SphereState], moving_threshold: f64) -> Vec<(usize, usize)> {
    let threshold_squared = moving_threshold * moving_threshold;
    let moving: Vec<bool> =
        spheres.iter().map(|s| s.vel.dot(s.vel) >= threshold_squared).collect();
    let mut pairs = Vec::new();
    for i in 0..spheres.len() {
        for j in (i + 1)..spheres.len() {
            if !moving[i] && !moving[j] {
                continue;
            }
            if is_colliding(&spheres[i], &spheres[j]) {
                pairs.push((i, j));
            }
        }
    }
    pairs
}

fn step_impl(
    spheres: &mut [SphereState],
    dt: f64,
    boundary: &BoundaryState,
    config: &ConfigState,
    exclude_same_level: bool,
) {
    let rest_velocity_threshold = config.rest_threshold_factor * config.gravity * dt;

    for s in spheres.iter_mut() {
        s.vel = Vec3 { x: s.vel.x, y: s.vel.y, z: s.vel.z - config.gravity * dt };
        s.pos = s.pos.add(s.vel.scale(dt));
        resolve_boundary(s, boundary, config.boundary_restitution, rest_velocity_threshold);
        if s.pos.z <= boundary.z_min + s.radius + 1e-9 {
            s.vel = Vec3 {
                x: s.vel.x * (1.0 - config.friction),
                y: s.vel.y * (1.0 - config.friction),
                z: s.vel.z,
            };
        }
    }

    for (i, j) in find_colliding_pairs(spheres, rest_velocity_threshold) {
        if !is_colliding(&spheres[i], &spheres[j]) {
            continue;
        }
        if exclude_same_level && spheres[i].level == spheres[j].level {
            continue;
        }
        let (left, right) = spheres.split_at_mut(j);
        let (a, b) = (&mut left[i], &mut right[0]);
        resolve_velocity(a, b, config.sphere_restitution, rest_velocity_threshold);
        resolve_overlap(a, b);
    }
}

type SphereTuple = (f64, f64, f64, f64, f64, f64, f64, i64);

#[pyfunction]
#[pyo3(signature = (spheres, dt, boundary, config, exclude_same_level))]
fn step_native(
    spheres: Vec<SphereTuple>,
    dt: f64,
    boundary: (f64, f64, f64, f64, f64, Option<f64>),
    config: (f64, f64, f64, f64, f64),
    exclude_same_level: bool,
) -> Vec<SphereTuple> {
    let mut states: Vec<SphereState> = spheres
        .iter()
        .map(|&(x, y, z, vx, vy, vz, radius, level)| SphereState {
            pos: Vec3 { x, y, z },
            vel: Vec3 { x: vx, y: vy, z: vz },
            radius,
            level,
        })
        .collect();

    let boundary_state = BoundaryState {
        x_min: boundary.0,
        x_max: boundary.1,
        y_min: boundary.2,
        y_max: boundary.3,
        z_min: boundary.4,
        z_max: boundary.5,
    };
    let config_state = ConfigState {
        gravity: config.0,
        friction: config.1,
        sphere_restitution: config.2,
        boundary_restitution: config.3,
        rest_threshold_factor: config.4,
    };

    step_impl(&mut states, dt, &boundary_state, &config_state, exclude_same_level);

    states
        .iter()
        .map(|s| (s.pos.x, s.pos.y, s.pos.z, s.vel.x, s.vel.y, s.vel.z, s.radius, s.level))
        .collect()
}

#[pymodule]
fn sphere_merger_native(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(step_native, m)?)?;
    Ok(())
}
