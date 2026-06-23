"""Secret masking helpers shared across config, console, and web routes.

Never log or return a raw API key. Use :func:`mask_api_key` for any value that
will appear in logs, curl responses, or the UI, and :func:`openai_key_status`
to expose only a status label.
"""

from __future__ import annotations

from typing import Literal


KeyStatus = Literal["configured", "missing", "invalid", "unknown"]


def mask_api_key(value: str | None, *, prefix: int = 7, suffix: int = 4) -> str:
    """Return a masked representation of a secret, e.g. ``sk-proj-...87IA``.

    - Empty/None -> ``"(missing)"``.
    - Short values (too small to safely show head+tail) -> ``"***"``.
    """
    key = (value or "").strip()
    if not key:
        return "(missing)"
    if len(key) <= prefix + suffix:
        return "***"
    return f"{key[:prefix]}...{key[-suffix:]}"


def openai_key_status(value: str | None, *, invalid: bool = False) -> KeyStatus:
    """Map a key value to a status label without revealing the key.

    Pass ``invalid=True`` when an upstream check (e.g. the Realtime API) has
    already rejected the key.
    """
    key = (value or "").strip()
    if not key:
        return "missing"
    if invalid:
        return "invalid"
    return "configured"
