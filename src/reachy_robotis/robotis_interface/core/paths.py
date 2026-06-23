from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def project_path(*parts: str) -> Path:
    """Return a path rooted at the app project directory."""
    return PROJECT_ROOT.joinpath(*parts)

