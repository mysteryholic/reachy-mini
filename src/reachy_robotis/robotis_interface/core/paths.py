from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def project_path(*parts: str) -> Path:
    """Return a path to a bundled data file under the package root."""
    return PACKAGE_ROOT.joinpath(*parts)
