from __future__ import annotations

import asyncio
from time import time
from uuid import uuid4
from dataclasses import asdict, dataclass
from typing import Any

from reachy_robotis.robotis_interface.core.recipe_catalog import CommandRecipe, RecipeCatalog, RecipeTerminal
from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.transports.connection_transport import ConnectionTransport


TERMINAL_STATES = {"pending", "starting", "running", "exited", "failed", "stopping", "stopped", "unknown"}


@dataclass
class TerminalSession:
    """Tracked result/state for one recipe terminal command."""

    session_id: str
    recipe_id: str
    terminal_id: str
    device: str
    connection_id: str
    display_name: str
    command: str
    command_type: str
    run_mode: str
    state: str = "pending"
    started_at: float | None = None
    ended_at: float | None = None
    return_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    last_error: str = ""
    stop_command: str = ""
    start_order: int = 1
    required: bool = True

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


class TerminalSessionManager:
    """Start, stop, and report terminal-like sessions for Command Recipes."""

    def __init__(self, recipe_catalog: RecipeCatalog, connection_registry: ConnectionRegistry) -> None:
        self.recipe_catalog = recipe_catalog
        self.connection_registry = connection_registry
        self._sessions: dict[str, TerminalSession] = {}
        self._lock = asyncio.Lock()

    async def start_recipe(self, recipe_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        recipe = self.recipe_catalog.get(recipe_id)
        if recipe is None:
            return {"ok": False, "error": "unknown_recipe", "recipe_id": recipe_id}
        started: list[TerminalSession] = []
        for terminal in recipe.terminals:
            result = await self.start_terminal(recipe_id, terminal.terminal_id, dry_run=dry_run)
            session = self._sessions.get(str(result.get("session_id") or ""))
            if session is not None:
                started.append(session)
            if not result.get("ok") and terminal.required:
                await self.stop_recipe(recipe_id)
                return {
                    "ok": False,
                    "error": "required_terminal_failed",
                    "recipe_id": recipe_id,
                    "failed_terminal_id": terminal.terminal_id,
                    "sessions": [item.to_mapping() for item in started],
                    "result": result,
                }
            if terminal.wait_after_start_sec > 0:
                await asyncio.sleep(terminal.wait_after_start_sec)
        return {
            "ok": True,
            "message": "Recipe started",
            "recipe_id": recipe_id,
            "sessions": [item.to_mapping() for item in started],
        }

    async def stop_recipe(self, recipe_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        recipe = self.recipe_catalog.get(recipe_id)
        if recipe is None:
            return {"ok": False, "error": "unknown_recipe", "recipe_id": recipe_id}
        sessions = [
            session
            for session in self._sessions.values()
            if session.recipe_id == recipe_id and session.state in {"pending", "starting", "running", "unknown", "failed"}
        ]
        order = {terminal.terminal_id: terminal.start_order for terminal in recipe.terminals}
        sessions.sort(key=lambda item: order.get(item.terminal_id, item.start_order), reverse=True)
        results = [await self.stop_terminal(session.session_id, dry_run=dry_run) for session in sessions]
        return {"ok": all(result.get("ok") for result in results), "recipe_id": recipe_id, "results": results}

    async def start_terminal(self, recipe_id: str, terminal_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        recipe = self.recipe_catalog.get(recipe_id)
        if recipe is None:
            return {"ok": False, "error": "unknown_recipe", "recipe_id": recipe_id}
        terminal = self._terminal(recipe, terminal_id)
        if terminal is None:
            return {"ok": False, "error": "unknown_terminal", "recipe_id": recipe_id, "terminal_id": terminal_id}
        profile = self.connection_registry.get(terminal.connection_id)
        if profile is None:
            return {"ok": False, "error": "unknown_connection", "connection_id": terminal.connection_id}

        session = TerminalSession(
            session_id=f"{recipe_id}_{terminal_id}_{uuid4().hex[:8]}",
            recipe_id=recipe.recipe_id,
            terminal_id=terminal.terminal_id,
            device=recipe.device,
            connection_id=terminal.connection_id,
            display_name=terminal.display_name,
            command=terminal.command,
            command_type=terminal.command_type,
            run_mode=terminal.run_mode,
            stop_command=terminal.stop_command or "",
            start_order=terminal.start_order,
            required=terminal.required,
        )
        async with self._lock:
            self._sessions[session.session_id] = session
            session.state = "starting"
            session.started_at = time()

        result = await ConnectionTransport(profile).async_run_command(
            terminal.command,
            terminal.command_type,
            terminal.run_mode,
            dry_run=dry_run,
        )
        data = result.data or {}
        session.return_code = data.get("return_code")
        session.stdout_tail = str(data.get("stdout_tail") or data.get("output") or "")
        session.stderr_tail = str(data.get("stderr_tail") or data.get("error") or "")
        session.last_error = "" if result.ok else str(result.error or data.get("error") or "")
        if result.ok:
            session.state = "running" if terminal.run_mode == "detached" else "exited"
        else:
            session.state = "failed"
            session.ended_at = time()
        payload = session.to_mapping()
        payload["transport"] = data
        return {"ok": result.ok, "message": result.message, "session_id": session.session_id, "session": payload}

    async def stop_terminal(self, session_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            return {"ok": False, "error": "unknown_session", "session_id": session_id}
        session.state = "stopping"
        profile = self.connection_registry.get(session.connection_id)
        if profile is None:
            session.state = "failed"
            session.last_error = "unknown_connection"
            return {"ok": False, "error": "unknown_connection", "session_id": session_id}
        if session.stop_command:
            result = await ConnectionTransport(profile).async_run_command(
                session.stop_command,
                session.command_type,
                "foreground",
                dry_run=dry_run,
            )
            data = result.data or {}
            session.return_code = data.get("return_code")
            session.stdout_tail = str(data.get("stdout_tail") or data.get("output") or session.stdout_tail)
            session.stderr_tail = str(data.get("stderr_tail") or data.get("error") or session.stderr_tail)
            session.last_error = "" if result.ok else str(result.error or data.get("error") or "")
            session.state = "stopped" if result.ok else "failed"
            session.ended_at = time()
            return {"ok": result.ok, "session": session.to_mapping(), "transport": data}
        session.state = "stopped"
        session.ended_at = time()
        return {"ok": True, "session": session.to_mapping()}

    async def list_sessions(self) -> dict[str, Any]:
        return {"ok": True, "sessions": self.sessions_snapshot()}

    def sessions_snapshot(self) -> list[dict[str, Any]]:
        return [session.to_mapping() for session in self._sessions.values()]

    async def get_session(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            return {"ok": False, "error": "unknown_session", "session_id": session_id}
        return {"ok": True, "session": session.to_mapping()}

    async def get_session_logs(self, session_id: str, lines: int = 100) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            return {"ok": False, "error": "unknown_session", "session_id": session_id}
        stdout = "\n".join(session.stdout_tail.splitlines()[-lines:])
        stderr = "\n".join(session.stderr_tail.splitlines()[-lines:])
        return {"ok": True, "session_id": session_id, "stdout_tail": stdout, "stderr_tail": stderr, "last_error": session.last_error}

    def _terminal(self, recipe: CommandRecipe, terminal_id: str) -> RecipeTerminal | None:
        for terminal in recipe.terminals:
            if terminal.terminal_id == terminal_id:
                return terminal
        return None
