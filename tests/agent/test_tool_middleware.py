"""Tests for optional tool middleware and runtime feedback."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.runner import AgentRunSpec, AgentRunner
from nanobot.agent.tool_middleware import ToolMiddleware
from nanobot.bus.queue import MessageBus
from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.config.schema import AgentDefaults
from nanobot.providers.base import LLMResponse, ToolCallRequest

_MAX_TOOL_RESULT_CHARS = AgentDefaults().max_tool_result_chars


class _ReportingTool(Tool):
    @property
    def name(self) -> str:
        return "reporting_tool"

    @property
    def description(self) -> str:
        return "reporting_tool"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs):
        runtime = self._get_tool_runtime(kwargs)
        assert runtime is not None
        await asyncio.to_thread(runtime.report, "working inside tool")
        return "tool result"


class _FailingTool(Tool):
    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "failing_tool"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs):
        runtime = self._get_tool_runtime(kwargs)
        assert runtime is not None
        runtime.report("about to fail")
        await asyncio.sleep(0)
        raise RuntimeError("boom")


class _RecordingMiddleware(ToolMiddleware):
    def __init__(self) -> None:
        self.events: list[tuple] = []

    async def before_call(self, context) -> None:
        self.events.append(("before", context.tool_name, context.call_id))

    async def on_event(self, context, event) -> None:
        self.events.append(("event", context.tool_name, event.phase, event.message, event.percent))

    async def after_call(self, context, result) -> None:
        self.events.append(("after", context.tool_name, result))

    async def on_error(self, context, exc) -> None:
        self.events.append(("error", context.tool_name, str(exc)))


def _make_loop_with_feedback(tmp_path):
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"

    with patch("nanobot.agent.loop.ContextBuilder"), \
         patch("nanobot.agent.loop.SessionManager"), \
         patch("nanobot.agent.loop.SubagentManager") as mock_subagents:
        mock_subagents.return_value.cancel_by_session = AsyncMock(return_value=0)
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=tmp_path,
            enable_tool_feedback=True,
        )
    return loop


@pytest.mark.asyncio
async def test_runner_tool_middleware_receives_runtime_events_from_worker_thread():
    provider = type("Provider", (), {})()
    call_count = {"n": 0}

    async def chat_with_retry(*, messages, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return LLMResponse(
                content="working",
                tool_calls=[ToolCallRequest(id="call_1", name="reporting_tool", arguments={})],
                usage={},
            )
        return LLMResponse(content="done", tool_calls=[], usage={})

    provider.chat_with_retry = chat_with_retry

    tools = ToolRegistry()
    tools.register(_ReportingTool())
    middleware = _RecordingMiddleware()

    runner = AgentRunner(provider)
    result = await runner.run(AgentRunSpec(
        initial_messages=[],
        tools=tools,
        model="test-model",
        max_iterations=2,
        max_tool_result_chars=_MAX_TOOL_RESULT_CHARS,
        tool_middleware=middleware,
    ))

    assert result.final_content == "done"
    assert middleware.events == [
        ("before", "reporting_tool", "call_1"),
        ("event", "reporting_tool", "progress", "working inside tool", None),
        ("after", "reporting_tool", "tool result"),
    ]


@pytest.mark.asyncio
async def test_runner_tool_middleware_receives_error_after_runtime_events():
    provider = type("Provider", (), {})()

    async def chat_with_retry(**kwargs):
        return LLMResponse(
            content="working",
            tool_calls=[ToolCallRequest(id="call_1", name="failing_tool", arguments={})],
            usage={},
        )

    provider.chat_with_retry = chat_with_retry

    tools = ToolRegistry()
    tools.register(_FailingTool())
    middleware = _RecordingMiddleware()

    runner = AgentRunner(provider)
    result = await runner.run(AgentRunSpec(
        initial_messages=[],
        tools=tools,
        model="test-model",
        max_iterations=1,
        max_tool_result_chars=_MAX_TOOL_RESULT_CHARS,
        tool_middleware=middleware,
        fail_on_tool_error=True,
    ))

    assert result.stop_reason == "tool_error"
    assert result.error == "Error: RuntimeError: boom"
    assert middleware.events == [
        ("before", "failing_tool", "call_1"),
        ("event", "failing_tool", "progress", "about to fail", None),
        ("error", "failing_tool", "boom"),
    ]


@pytest.mark.asyncio
async def test_agent_loop_emits_tool_feedback_when_enabled(tmp_path):
    loop = _make_loop_with_feedback(tmp_path)
    tool_call = ToolCallRequest(id="call1", name="read_file", arguments={"path": "foo.txt"})
    calls = iter([
        LLMResponse(content="thinking", tool_calls=[tool_call]),
        LLMResponse(content="Done", tool_calls=[]),
    ])
    loop.provider.chat_with_retry = AsyncMock(side_effect=lambda *a, **kw: next(calls))
    loop.tools.get_definitions = MagicMock(return_value=[])
    loop.tools.execute = AsyncMock(return_value="ok")

    progress: list[tuple[str | dict, bool]] = []

    async def on_progress(content: str | dict, *, tool_hint: bool = False) -> None:
        progress.append((content, tool_hint))

    final_content, _, _ = await loop._run_agent_loop([], on_progress=on_progress)

    assert final_content == "Done"
    assert ("thinking", False) in progress
    assert ('read_file("foo.txt")', True) in progress
    assert any(
        isinstance(content, dict)
        and content.get("type") == "tool_event"
        and content.get("phase") == "start"
        and content.get("tool_name") == "read_file"
        for content, _ in progress
    )
    assert any(
        isinstance(content, dict)
        and content.get("type") == "tool_event"
        and content.get("phase") == "finish"
        and content.get("tool_name") == "read_file"
        for content, _ in progress
    )
