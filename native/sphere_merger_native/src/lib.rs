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

fn is_settled(spheres: &[SphereState], settle_speed_threshold: f64) -> bool {
    spheres.iter().all(|s| s.vel.length() < settle_speed_threshold)
}

fn settle_velocities(spheres: &mut [SphereState]) {
    for s in spheres.iter_mut() {
        s.vel = Vec3 { x: 0.0, y: 0.0, z: 0.0 };
    }
}

/// `game/scoring.py::default_merge_score` -- the only merge-score formula
/// ever passed in this codebase, hardcoded here rather than accepted as a
/// callback (same reasoning as `exclude_same_level`: arbitrary Python
/// callables can't cross the FFI boundary).
fn default_merge_score(new_level: i64, combo_index: i64) -> i64 {
    2i64.pow(new_level as u32) * combo_index
}

/// `game/merge.py::merge_spheres` -- mass/momentum-weighted combination of
/// two same-level spheres into one at `level + 1`. `radius_for_level`
/// currently returns a fixed `base_radius` regardless of level (see its
/// docstring -- a deliberate, temporary simplification), so that's what's
/// passed in here rather than reimplementing level-dependent sizing.
fn merge_spheres(a: &SphereState, b: &SphereState, base_radius: f64) -> SphereState {
    let new_mass = a.mass() + b.mass();
    SphereState {
        pos: a.pos.scale(a.mass()).add(b.pos.scale(b.mass())).scale(1.0 / new_mass),
        vel: a.vel.scale(a.mass()).add(b.vel.scale(b.mass())).scale(1.0 / new_mass),
        radius: base_radius,
        level: a.level + 1,
    }
}

/// `game/merge.py::resolve_merges` -- same fixed pair order as
/// `find_colliding_pairs` (with `moving_threshold=0.0`, i.e. every pair
/// checked every call, deliberately not reusing `step`'s resting-pair
/// skip: merges are score-relevant, not just physics smoothness). Returns
/// the resulting level of each merge, in processing order.
fn resolve_merges(spheres: &mut Vec<SphereState>, base_radius: f64) -> Vec<i64> {
    let pairs = find_colliding_pairs(spheres, 0.0);
    let mut already_merged = std::collections::HashSet::new();
    let mut to_remove = std::collections::HashSet::new();
    let mut new_levels = Vec::new();

    for (i, j) in pairs {
        if already_merged.contains(&i) || already_merged.contains(&j) {
            continue;
        }
        if spheres[i].level != spheres[j].level {
            continue;
        }
        let merged = merge_spheres(&spheres[i], &spheres[j], base_radius);
        new_levels.push(merged.level);
        spheres[i] = merged;
        to_remove.insert(j);
        already_merged.insert(i);
        already_merged.insert(j);
    }

    if !to_remove.is_empty() {
        let mut idx = 0usize;
        spheres.retain(|_| {
            let keep = !to_remove.contains(&idx);
            idx += 1;
            keep
        });
    }
    new_levels
}

/// Native port of `agents.base.simulate_shot`'s whole settle loop --
/// spawn the next queued sphere (`game.shooting.shoot`'s formula), then
/// `physics.engine.step` + merge-resolve + score repeatedly (mirroring
/// `game.round.play_shot`/`advance_physics`) until the shot's score
/// reaches `target_score`, the field settles, or `max_settle_steps` is
/// hit. One FFI call covers a whole shot's worth of steps instead of one
/// call per physics step, so the marshaling cost that dominates
/// `step_native` for a single step is paid once per candidate shot here.
///
/// Returns `(final_spheres, score_gained_by_this_shot, is_won)`.
#[pyfunction]
#[pyo3(signature = (
    spheres, next_level, next_radius, spawn_position, angle_degrees, speed,
    dt, boundary, config, max_settle_steps, settle_speed_threshold,
    score_before, target_score
))]
#[allow(clippy::too_many_arguments)]
fn simulate_shot_native(
    spheres: Vec<SphereTuple>,
    next_level: i64,
    next_radius: f64,
    spawn_position: (f64, f64, f64),
    angle_degrees: f64,
    speed: f64,
    dt: f64,
    boundary: (f64, f64, f64, f64, f64, Option<f64>),
    config: (f64, f64, f64, f64, f64),
    max_settle_steps: u32,
    settle_speed_threshold: f64,
    score_before: i64,
    target_score: i64,
) -> (Vec<SphereTuple>, i64, bool) {
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

    let angle_radians = angle_degrees.to_radians();
    let (sx, sy, sz) = spawn_position;
    states.push(SphereState {
        pos: Vec3 { x: sx, y: sy, z: sz },
        vel: Vec3 { x: speed * angle_radians.cos(), y: speed * angle_radians.sin(), z: 0.0 },
        radius: next_radius,
        level: next_level,
    });

    let mut score = score_before;
    let mut combo_index: i64 = 0;
    let mut won = score >= target_score;

    for _ in 0..max_settle_steps {
        step_impl(&mut states, dt, &boundary_state, &config_state, true);

        for new_level in resolve_merges(&mut states, next_radius) {
            combo_index += 1;
            score += default_merge_score(new_level, combo_index);
        }

        won = score >= target_score;
        if won {
            break;
        }
        if is_settled(&states, settle_speed_threshold) {
            settle_velocities(&mut states);
            break;
        }
    }

    let final_spheres = states
        .iter()
        .map(|s| (s.pos.x, s.pos.y, s.pos.z, s.vel.x, s.vel.y, s.vel.z, s.radius, s.level))
        .collect();
    (final_spheres, score - score_before, won)
}

#[pymodule]
fn sphere_merger_native(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(step_native, m)?)?;
    m.add_function(wrap_pyfunction!(simulate_shot_native, m)?)?;
    Ok(())
}
