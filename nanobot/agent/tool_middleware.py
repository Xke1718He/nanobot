"""Optional middleware and runtime for tool execution feedback."""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import Future as ThreadFuture
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from loguru import logger


ProgressCallback = Callable[[str | dict[str, Any]], Awaitable[None]]


@dataclass(slots=True)
class ToolCallContext:
    """Immutable context for one tool call."""

    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    iteration: int
    session_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started_at) * 1000)


@dataclass(slots=True)
class ToolEvent:
    """One runtime event emitted from inside a tool."""

    phase: Literal["progress", "log"]
    message: str = ""
    percent: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class ToolMiddleware:
    """Optional observer around tool execution."""

    async def before_call(self, context: ToolCallContext) -> None:
        pass

    async def on_event(self, context: ToolCallContext, event: ToolEvent) -> None:
        pass

    async def after_call(self, context: ToolCallContext, result: Any) -> None:
        pass

    async def on_error(self, context: ToolCallContext, exc: BaseException) -> None:
        pass


class CompositeToolMiddleware(ToolMiddleware):
    """Fan out lifecycle notifications to multiple middlewares."""

    def __init__(self, middlewares: list[ToolMiddleware] | None = None):
        self._middlewares = list(middlewares or [])

    async def before_call(self, context: ToolCallContext) -> None:
        for middleware in self._middlewares:
            try:
                await middleware.before_call(context)
            except Exception:
                logger.exception("ToolMiddleware.before_call error in {}", type(middleware).__name__)

    async def on_event(self, context: ToolCallContext, event: ToolEvent) -> None:
        for middleware in self._middlewares:
            try:
                await middleware.on_event(context, event)
            except Exception:
                logger.exception("ToolMiddleware.on_event error in {}", type(middleware).__name__)

    async def after_call(self, context: ToolCallContext, result: Any) -> None:
        for middleware in self._middlewares:
            try:
                await middleware.after_call(context, result)
            except Exception:
                logger.exception("ToolMiddleware.after_call error in {}", type(middleware).__name__)

    async def on_error(self, context: ToolCallContext, exc: BaseException) -> None:
        for middleware in self._middlewares:
            try:
                await middleware.on_error(context, exc)
            except Exception:
                logger.exception("ToolMiddleware.on_error error in {}", type(middleware).__name__)


class ToolRuntime:
    """Sync-safe helper passed into tools so they can emit internal progress."""

    def __init__(
        self,
        context: ToolCallContext,
        middleware: ToolMiddleware | None,
        *,
        loop: asyncio.AbstractEventLoop,
    ):
        self._context = context
        self._middleware = middleware
        self._loop = loop
        self._pending: list[asyncio.Task[None] | ThreadFuture[None]] = []

    def report(self, message: str, *, payload: dict[str, Any] | None = None) -> None:
        """Emit a text progress update."""
        self.emit("progress", message=message, payload=payload)

    def report_progress(
        self,
        percent: int | float,
        stage: str = "",
        *,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit a structured progress update."""
        normalized = max(0, min(100, int(percent)))
        self.emit("progress", message=stage, percent=normalized, payload=payload)

    def emit(
        self,
        phase: Literal["progress", "log"],
        *,
        message: str = "",
        percent: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit a raw runtime event."""
        if self._middleware is None or self._loop.is_closed():
            return
        event = ToolEvent(
            phase=phase,
            message=message,
            percent=percent,
            payload=dict(payload or {}),
        )
        future = self._schedule(self._safe_emit(event))
        if future is not None:
            self._pending.append(future)

    async def drain(self) -> None:
        """Wait for all emitted runtime events to finish dispatching."""
        pending, self._pending = self._pending, []
        for future in pending:
            try:
                if isinstance(future, asyncio.Task):
                    await future
                else:
                    await asyncio.wrap_future(future)
            except Exception:
                logger.exception("Tool runtime event dispatch failed for {}", self._context.tool_name)

    def _schedule(self, coro: Awaitable[None]) -> asyncio.Task[None] | ThreadFuture[None] | None:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self._loop:
            return self._loop.create_task(coro)
        try:
            return asyncio.run_coroutine_threadsafe(coro, self._loop)
        except RuntimeError:
            logger.debug("Dropping tool runtime event because loop is no longer available")
            return None

    async def _safe_emit(self, event: ToolEvent) -> None:
        if self._middleware is None:
            return
        try:
            await self._middleware.on_event(self._context, event)
        except Exception:
            logger.exception("Tool middleware event dispatch failed for {}", self._context.tool_name)


class ProgressToolMiddleware(ToolMiddleware):
    """Bridge tool lifecycle and runtime events into the existing progress stream."""

    def __init__(self, progress_callback: ProgressCallback | None = None):
        self._progress_callback = progress_callback

    async def before_call(self, context: ToolCallContext) -> None:
        await self._emit({
            "type": "tool_event",
            "phase": "start",
            "tool_name": context.tool_name,
            "call_id": context.call_id,
            "message": f"Executing {context.tool_name}",
            "payload": {"argument_keys": sorted(context.arguments)},
        })

    async def on_event(self, context: ToolCallContext, event: ToolEvent) -> None:
        payload: dict[str, Any] = {
            "type": "tool_event",
            "phase": event.phase,
            "tool_name": context.tool_name,
            "call_id": context.call_id,
            "message": event.message,
            "payload": dict(event.payload),
        }
        if event.percent is not None:
            payload["percent"] = event.percent
        await self._emit(payload)

    async def after_call(self, context: ToolCallContext, result: Any) -> None:
        await self._emit({
            "type": "tool_event",
            "phase": "finish",
            "tool_name": context.tool_name,
            "call_id": context.call_id,
            "message": f"{context.tool_name} completed",
            "payload": {
                "elapsed_ms": context.elapsed_ms,
                "result_summary": self._summarize_result(result),
            },
        })

    async def on_error(self, context: ToolCallContext, exc: BaseException) -> None:
        await self._emit({
            "type": "tool_event",
            "phase": "error",
            "tool_name": context.tool_name,
            "call_id": context.call_id,
            "message": str(exc),
            "payload": {"elapsed_ms": context.elapsed_ms},
        })

    async def _emit(self, payload: dict[str, Any]) -> None:
        if self._progress_callback is None:
            return
        try:
            await self._progress_callback(payload)
        except Exception:
            logger.exception("Tool progress callback failed")

    @staticmethod
    def _summarize_result(result: Any) -> str:
        if isinstance(result, list):
            return f"{len(result)} content block(s)"
        if isinstance(result, dict):
            keys = ", ".join(sorted(str(key) for key in result.keys())[:5])
            return f"dict[{keys}]" if keys else "dict"
        text = str(result).strip().replace("\n", " ")
        if not text:
            return "empty"
        return text[:117] + "..." if len(text) > 120 else text
