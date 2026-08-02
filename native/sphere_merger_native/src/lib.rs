//! Placeholder Python <-> Rust bridge. Proves the build/import pipeline
//! (maturin + PyO3 + local GNU toolchain) end to end before any real
//! physics logic is ported here -- see docs/physics_optimizations.md for
//! why (Rust over C++/GPU) and how (local-only toolchain) this exists.

use pyo3::prelude::*;

#[pyfunction]
fn ping() -> PyResult<String> {
    Ok("pong".to_string())
}

#[pymodule]
fn sphere_merger_native(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ping, m)?)?;
    Ok(())
}
