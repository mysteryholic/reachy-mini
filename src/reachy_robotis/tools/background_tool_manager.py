"""Background tool orchestrator for non-blocking tool execution."""

from __future__ import annotations
import time
import asyncio
import logging
from typing import Any, Dict, Callable, Optional, Coroutine

from pydantic import Field, BaseModel, PrivateAttr

from reachy_robotis.tools.core_tools import (
    ToolDependencies,
    dispatch_tool_call,
    dispatch_tool_call_with_manager,
)
from reachy_robotis.tools.tool_constants import ToolState, SystemTool


logger = logging.getLogger(__name__)

_SYSTEM_TOOL_NAMES: set[str] = {t.value for t in SystemTool}

class ToolProgress(BaseModel):
    """Progress of a background tool."""

    """the progress of the tool"""
    progress: float = Field(..., ge=0.0, le=1.0)

    """the message of the tool"""
    message: Optional[str] = None


class ToolCallRoutine(BaseModel):
    """Encapsulates an async callable with its arguments for deferred execution."""

    model_config = {"arbitrary_types_allowed": True}

    """the name of the tool"""
    tool_name: str

    """the JSON arguments for the tool call"""
    args_json_str: str

    """the dependencies for the tool call"""
    deps: "ToolDependencies"

    async def __call__(self, tool_manager: BackgroundToolManager) -> Any:
        """Execute the stored callable with its arguments."""
        if self.tool_name in _SYSTEM_TOOL_NAMES:
            return await dispatch_tool_call_with_manager(tool_name=self.tool_name, args_json=self.args_json_str, deps=self.deps, tool_manager=tool_manager)
        return await dispatch_tool_call(tool_name=self.tool_name, args_json=self.args_json_str, deps=self.deps)


class ToolNotification(BaseModel):
    """Notification payload for completed tools."""

    """the ID of the tool"""
    id: str

    """the name of the tool"""
    tool_name: str

    """whether the tool call was triggered by an idle signal"""
    is_idle_tool_call: bool

    """the status of the tool"""
    status: ToolState

    """the result of the tool"""
    result: Optional[Dict[str, Any]] = None

    """the error of the tool"""
    error: Optional[str] = None


class BackgroundTool(ToolNotification):
    """Represents a background tool."""

    """the progress of the tool"""
    progress: Optional[ToolProgress] = None

    """the start time of the tool"""
    started_at: float = Field(default_factory=time.monotonic)

    """the completion time of the tool"""
    completed_at: Optional[float] = None

    """the async tool execution task"""
    _task: Optional[asyncio.Task[None]] = PrivateAttr(default=None)

    @property
    def tool_id(self) -> str:
        """Get the name of the tool."""
        return f"{self.tool_name}-{self.id}-{self.started_at}"

    def get_notification(self) -> ToolNotification:
        """Get the notification for the tool."""
        return ToolNotification(
            id=self.id,
            tool_name=self.tool_name,
            is_idle_tool_call=self.is_idle_tool_call,
            status=self.status,
            result=self.result,
            error=self.error,
        )


class BackgroundToolManager(BaseModel):
    """Manages background tools for non-blocking tool execution."""

    """the dictionary of tools"""
    _tools: Dict[str, BackgroundTool] = PrivateAttr(default_factory=dict)

    """the async queue for notifications"""
    _notification_queue: asyncio.Queue[ToolNotification] = PrivateAttr(default_factory=asyncio.Queue)

    """the event loop"""
    _loop: Optional[asyncio.AbstractEventLoop] = PrivateAttr(default=None)

    """internal lifecycle tasks (notification listener, periodic cleanup)"""
    _lifecycle_tasks: list[asyncio.Task[None]] = PrivateAttr(default_factory=list)

    """the maximum duration of a tool execution in seconds (default: 1 day)"""
    _max_tool_duration_seconds: float = PrivateAttr(default=86400)

    """the maximum time to keep a completed/failed/cancelled tool in memory (default: 1 hour)"""
    _max_tool_memory_seconds: float = PrivateAttr(default=3600)

    def set_loop(
        self,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """Set the event loop."""
        if loop is not None:
            self._loop = loop
        else:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        logger.debug("BackgroundToolManager: event loop set")


    async def start_tool(
        self,
        call_id: str,
        tool_call_routine: ToolCallRoutine,
        is_idle_tool_call: bool,
        with_progress: bool = False,
    ) -> BackgroundTool:
        """Start a new background tool."""
        tool_name = tool_call_routine.tool_name
        id = call_id
        bg_tool = BackgroundTool(
            id=id,
            tool_name=tool_name,
            is_idle_tool_call=is_idle_tool_call,
            progress=ToolProgress(progress=0.0) if with_progress else None,
            status=ToolState.RUNNING,
        )
        self._tools[bg_tool.tool_id] = bg_tool

        async_task = asyncio.create_task(
            self._run_tool(bg_tool, tool_call_routine),
            name=f"bg-{tool_name}-{id}",
        )
        bg_tool._task = async_task

        logger.info(f"Started background tool: {bg_tool.tool_name} (id={id})")

        return bg_tool

    async def _run_tool(
        self,
        bg_tool: BackgroundTool,
        tool_call_routine: ToolCallRoutine,
    ) -> None:
        """Execute the tool and handle completion."""
        result: dict[str, Any] = await tool_call_routine(self)
        bg_tool.completed_at = time.monotonic()
        error = result.get("error")

        if error is not None:
            if error == "Tool cancelled":
                bg_tool.status = ToolState.CANCELLED
                logger.debug(f"Background tool cancelled: {bg_tool.tool_name} (id={bg_tool.id})")
            else:
                bg_tool.status = ToolState.FAILED
                logger.debug(f"Background tool failed: {bg_tool.tool_name} (id={bg_tool.id}): {bg_tool.error}")
            bg_tool.error = result["error"]

        else:
            bg_tool.result = result
            bg_tool.status = ToolState.COMPLETED
            logger.debug(f"Background tool completed: {bg_tool.tool_name} (id={bg_tool.id})")

        await self._notification_queue.put(bg_tool.get_notification())
        logger.debug(f"Queued notification for tool: {bg_tool.tool_name} (id={bg_tool.id})")

    async def update_progress(
        self,
        tool_id: str,
        progress: float,
        message: Optional[str] = None,
    ) -> bool:
        """Update progress for a tool (for tools with with_progress=True)."""
        tool = self._tools.get(tool_id)
        if tool is None:
            return False

        if tool.progress is None:
            return False

        tool.progress = ToolProgress(progress=max(0.0, min(1.0, progress)), message=message)
        logger.debug(f"Tool {tool_id} progress: {progress:.1%} - {message or ''}")
        return True

    async def cancel_tool(self, tool_id: str, log: bool = True) -> bool:
        """Cancel a running tool by ID."""
        tool = self._tools.get(tool_id)
        if tool is None:
            if log:
                logger.warning(f"Cannot cancel tool {tool_id}: not found")
            return False

        if tool.status != ToolState.RUNNING:
            if log:
                logger.warning(f"Cannot cancel tool {tool_id}: status is {tool.status.value}")
            return True

        if tool._task:
            tool._task.cancel()
            if log:
                logger.info(f"Cancelled tool: {tool.tool_name} (id={tool_id})")
            return True

        return False

    def start_up(self, tool_callbacks: list[Callable[[ToolNotification], Coroutine[Any, Any, None]]]) -> None:
        """Start the background tool manager."""
        self.set_loop()

        async def _listener() -> None:
            while True:
                bg_tool = await self._notification_queue.get()
                for callback in tool_callbacks:
                    await callback(bg_tool)

        async def _cleanup(interval_seconds: float = 5 * 60) -> None:
            while True:
                await asyncio.sleep(interval_seconds)
                await self.cleanup_tools()
                await self.timeout_tools()

        self._lifecycle_tasks = [
            asyncio.create_task(_cleanup(), name="bg-tool-cleanup"),
            asyncio.create_task(_listener(), name="bg-tool-listener-callback"),
        ]

        logger.info(
            "BackgroundToolManager started. "
            "Max tool execution duration: %s seconds (tools running longer will be auto-cancelled). "
            "Max tool memory retention: %s seconds (completed/failed/cancelled tools older than this are purged).",
            self._max_tool_duration_seconds, self._max_tool_memory_seconds,
        )

    async def shutdown(self) -> None:
        """Cancel all background tasks (listener, cleanup) and running tools."""
        for task in self._lifecycle_tasks:
            task.cancel()
        for task in self._lifecycle_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._lifecycle_tasks.clear()

        for tool_id in list(self._tools):
            await self.cancel_tool(tool_id, log=False)

        logger.info("BackgroundToolManager shut down")

    async def timeout_tools(self) -> int:
        """Cancel tools that have been running too long."""
        now = time.monotonic()
        to_cancel = []

        for tool_id, tool in self._tools.items():
            if tool.status == ToolState.RUNNING:
                if tool.started_at and (now - tool.started_at) > self._max_tool_duration_seconds:
                    to_cancel.append(tool_id)

        for tool_id in to_cancel:
            await self.cancel_tool(tool_id)

        if to_cancel:
            logger.debug(f"Timed out {len(to_cancel)} tools")

        return len(to_cancel)

    async def cleanup_tools(self) -> int:
        """Remove completed/failed/cancelled tools that have been in memory for too long."""
        now = time.monotonic()
        to_remove = []

        for tool_id, tool in self._tools.items():
            if tool.status in (ToolState.COMPLETED, ToolState.FAILED, ToolState.CANCELLED):
                if tool.completed_at and (now - tool.completed_at) > self._max_tool_memory_seconds:
                    to_remove.append(tool_id)

        for tool_id in to_remove:
            del self._tools[tool_id]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old tools")

        return len(to_remove)

    def get_tool(self, tool_id: str) -> Optional[BackgroundTool]:
        """Get a tool by ID."""
        return self._tools.get(tool_id)

    def get_running_tools(self) -> list[BackgroundTool]:
        """Get all currently running tools."""
        return [t for t in self._tools.values() if t.status == ToolState.RUNNING]

    def get_all_tools(self, limit: Optional[int] = None) -> list[BackgroundTool]:
        """Get recent tools (most recent first)."""
        sorted_tools = sorted(
            self._tools.values(),
            key=lambda t: t.started_at,
            reverse=True,
        )
        if limit is not None:
            return sorted_tools[:limit]
        return sorted_tools
