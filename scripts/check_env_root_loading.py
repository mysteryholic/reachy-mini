from __future__ import annotations

from pathlib import Path

import _bootstrap  # noqa: F401

from reachy_robotis.config import (
    LEGACY_PACKAGE_ENV_PATH,
    PROJECT_ROOT_ENV_PATH,
    resolve_env_path,
)


# Canonical env path must be the project root, never the package dir.
root = Path("/home/pollen/reachy_robotis/.env")
assert PROJECT_ROOT_ENV_PATH == root, PROJECT_ROOT_ENV_PATH
assert resolve_env_path() == root, resolve_env_path()

# Legacy package path points inside src/reachy_robotis/.
assert LEGACY_PACKAGE_ENV_PATH.name == ".env", LEGACY_PACKAGE_ENV_PATH
assert "src/reachy_robotis" in str(LEGACY_PACKAGE_ENV_PATH), LEGACY_PACKAGE_ENV_PATH

# After import-time migration the legacy file must not coexist with the root one.
if PROJECT_ROOT_ENV_PATH.exists():
    assert not LEGACY_PACKAGE_ENV_PATH.exists(), (
        "legacy src/.env should have been migrated to project root"
    )

print("ok env root loading")
