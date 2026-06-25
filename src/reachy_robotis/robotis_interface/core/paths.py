from __future__ import annotations

import os
import shutil
import logging
from pathlib import Path


logger = logging.getLogger(__name__)

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def project_path(*parts: str) -> Path:
    """Return a path to a bundled data file under the package root.

    Use this for read-only, built-in defaults that ship with the package and
    should track app updates (device presets, command allowlists, ...).
    """
    return PACKAGE_ROOT.joinpath(*parts)


def data_dir() -> Path:
    """Return the persistent, writable base directory for user-modified data.

    The package directory lives inside ``site-packages`` and is wiped whenever
    the app is reinstalled/updated, so user-saved tasks and connection profiles
    must live outside it. Override with ``REACHY_ROBOTIS_DATA_DIR``; defaults to
    ``~/.local/share/reachy_robotis``.
    """
    base = os.getenv("REACHY_ROBOTIS_DATA_DIR")
    if base:
        return Path(base).expanduser()
    return Path.home() / ".local" / "share" / "reachy_robotis"


def persistent_path(*parts: str) -> Path:
    """Return a persistent path for a user-writable data file.

    On first use the bundled default (``project_path(*parts)``) is copied into
    the persistent location so existing built-in content is preserved; from then
    on all reads and writes use the persistent copy, which survives reinstalls.
    """
    target = data_dir().joinpath(*parts)
    if not target.exists():
        bundled = project_path(*parts)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if bundled.exists():
                shutil.copy2(bundled, target)
        except Exception as exc:  # pragma: no cover - best-effort seeding
            logger.warning("Could not seed persistent file %s from %s: %s", target, bundled, exc)
            # Fall back to the bundled path so the app still functions read-only.
            return bundled
    return target
