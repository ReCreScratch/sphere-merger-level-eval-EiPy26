"""Parity check for the native Rust backend -- currently disabled.

The native extension (`native/sphere_merger_native`) hasn't been ported to
the 2D/no-gravity physics model yet (see docs/physics_optimizations.md,
"height removal" refactor, step 4/native port). Re-enable/rewrite this once
that port lands; until then `agents.base.simulate_shot`'s native branch
raises `NotImplementedError`, so there is nothing here to compare against.
"""

import pytest

pytest.skip(
    "native backend not yet ported to 2D physics (height-removal refactor, step 4)",
    allow_module_level=True,
)
