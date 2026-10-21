"""Unit tests for the agno-agent integration (Agno AgentOS API)."""

import asyncio
import json
import tracemalloc
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from agno_agent import (
    MAX_ERROR_BODY_BYTES,
    MAX_EVENT_BYTES,
    AgnoConnectedAccountHandler,
    AnswerTooLargeError,
    _extract_answer,
    _SSEAnswerCollector,
    agno_agent,
)

pytestmark = pytest.mark.unit

RUNS_URL = "https://agno.example.com/agents/my-agent/runs"

# Real Agno wire format: each block has an `event:` line followed by `data:` JSON.
AGNO_WIRE_BODY = (
    "event: RunStarted\n"
    'data: {"event":"RunStarted"}\n'
    "\n"
    "event: RunContent\n"
    'data: {"event":"RunContent","content":"Hello "}\n'
    "\n"
    "event: RunContent\n"
    'data: {"event":"RunContent","content":"world."}\n'
    "\n"
    "event: RunCompleted\n"
    'data: {"event":"RunCompleted","content":"Hello world."}\n'
    "\n"
)


def _overflowing_chunks() -> list[str]:
    """RunContent events that together exceed the ``MAX_EVENT_BYTES`` answer bound."""
    chunk = "b" * 100_000
    return [f'data: {{"event": "RunContent", "content": "{chunk}"}}' for _ in range(30)]


def _sse(*events: str) -> str:
    """Build an SSE response body from already-encoded ``data: ...`` lines."""
    return "\n\n".join(events) + "\n\n"


# ---- Fake AgentOS transport ----
# ask_agent reads the run stream with aiohttp directly (context.fetch buffers the
# whole body), so these stand in for aiohttp.ClientSession and its StreamReader.


class _FakeStreamReader:
    """Yields the body in small chunks so tests exercise SSE lines split across chunks."""

    def __init__(self, body: bytes, chunk_size: int, error: Exception | None = None):
        self._body = body
        self._chunk_size = chunk_size
        self._error = error
        self._read_pos = 0

    async def iter_chunked(self, n: int):
        for i in range(0, len(self._body), self._chunk_size):
            yield self._body[i : i + self._chunk_size]
        if self._error:
            raise self._error

    async def read(self, n: int = -1) -> bytes:
        # Like aiohttp, a read returns whatever has arrived — at most one network chunk.
        size = self._chunk_size if n < 0 else min(n, self._chunk_size)
        data = self._body[self._read_pos : self._read_pos + size]
        self._read_pos += len(data)
        return data


class _FakeResponse:
    def __init__(self, body: bytes, status: int, content_type: str, chunk_size: int, error: Exception | None):
        self.status = status
        self.headers = {"Content-Type": content_type}
        self.content = _FakeStreamReader(body, chunk_size, error)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _reply(
    body: Any,
    status: int = 200,
    content_type: str = "text/event-stream",
    chunk_size: int = 7,
    error: Exception | None = None,
) -> _FakeResponse:
    """Build a fake AgentOS HTTP response. Dict bodies are sent as JSON; ``error`` is
    raised mid-stream after the body has been delivered."""
    if isinstance(body, dict):
        body, content_type = json.dumps(body), "application/json"
    raw = body if isinstance(body, bytes) else body.encode("utf-8")
    return _FakeResponse(raw, status, content_type, chunk_size, error)


class _FakeAgentOS:
    """Replaces ``aiohttp.ClientSession``: hands out queued responses (or raises
    queued exceptions) and records each POST."""

    def __init__(self):
        self.replies: list = []
        self.calls: list = []
        self.session_kwargs: dict = {}

    def queue(self, *replies: Any) -> None:
        self.replies.extend(replies)

    def __call__(self, **session_kwargs: Any) -> "_FakeAgentOS":
        self.session_kwargs = session_kwargs
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"url": url, **kwargs})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def agentos():
    fake = _FakeAgentOS()
    with patch("agno_agent.aiohttp.ClientSession", new=fake):
        yield fake


@pytest.fixture
def no_sleep():
    with patch("agno_agent.asyncio.sleep", new=AsyncMock()) as sleep_mock:
        yield sleep_mock


async def _ask(context, query: str = "How many active users?"):
    return await agno_agent.execute_action("ask_agent", {"query": query}, context)


# ---- ask_agent ----


class TestAskAgent:
    async def test_returns_run_completed_content(self, mock_context, agentos):
        agentos.queue(
            _reply(
                _sse(
                    'data: {"event": "RunStarted"}',
                    'data: {"event": "RunResponseContent", "content": "thinking..."}',
                    'data: {"event": "RunCompleted", "content": "There are 42 active users."}',
                )
            )
        )

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {"response": "There are 42 active users."}

    async def test_request_url_method_and_payload(self, mock_context, agentos):
        agentos.queue(_reply(_sse('data: {"event": "RunCompleted", "content": "ok"}')))

        await _ask(mock_context)

        assert agentos.calls == [
            {
                "url": RUNS_URL,
                "data": {"message": "How many active users?", "stream": "true"},
                "headers": {"Accept": "text/event-stream", "Authorization": "Bearer test-token"},
            }
        ]
        assert agentos.session_kwargs["timeout"].total == 120

    async def test_no_authorization_header_without_token(self, make_context, agentos):
        context = make_context(
            auth={"auth_type": "Custom", "credentials": {"api_url": "https://agno.example.com", "agent_id": "my-agent"}}
        )
        agentos.queue(_reply(_sse('data: {"event": "RunCompleted", "content": "ok"}')))

        await _ask(context)

        assert agentos.calls[0]["headers"] == {"Accept": "text/event-stream"}

    async def test_strips_trailing_slash_from_url(self, make_context, agentos):
        context = make_context(
            auth={
                "auth_type": "Custom",
                "credentials": {"api_url": "https://agno.example.com/", "agent_id": "my-agent"},
            }
        )
        agentos.queue(_reply(_sse('data: {"event": "RunCompleted", "content": "ok"}')))

        await _ask(context)

        assert agentos.calls[0]["url"] == RUNS_URL

    async def test_empty_stream_returns_default_message(self, mock_context, agentos):
        agentos.queue(_reply(_sse('data: {"event": "RunStarted"}')))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "No response from agent."

    async def test_missing_query_is_validation_error(self, mock_context, agentos):
        result = await agno_agent.execute_action("ask_agent", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert agentos.calls == []

    async def test_empty_query_is_validation_error(self, mock_context, agentos):
        result = await _ask(mock_context, query="")

        assert result.type == ResultType.VALIDATION_ERROR
        assert "query" in result.result["message"]
        assert agentos.calls == []

    @pytest.mark.parametrize(
        "credentials, missing",
        [
            ({}, "api_url"),
            ({"api_url": "https://agno.example.com"}, "agent_id"),
        ],
    )
    async def test_missing_credentials_is_validation_error(self, make_context, agentos, credentials, missing):
        context = make_context(auth={"auth_type": "Custom", "credentials": credentials})

        result = await _ask(context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert missing in result.result["message"]
        assert agentos.calls == []


class TestAskAgentResponseParsing:
    async def test_falls_back_to_run_content_chunks(self, mock_context, agentos):
        """Default Agno streaming emits RunContent chunks with no RunCompleted — concatenate them."""
        agentos.queue(
            _reply(
                _sse(
                    'data: {"event": "RunStarted"}',
                    'data: {"event": "RunContent", "content": "Hello "}',
                    'data: {"event": "RunContent", "content": "world."}',
                )
            )
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "Hello world."

    async def test_falls_back_to_legacy_chunk_names(self, mock_context, agentos):
        """Older Agno deployments stream RunResponseContent — still supported."""
        agentos.queue(
            _reply(
                _sse(
                    'data: {"event": "RunResponseContent", "content": "Hello "}',
                    'data: {"event": "RunResponseContent", "content": "world."}',
                )
            )
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "Hello world."

    async def test_parses_agno_wire_format_with_event_lines(self, mock_context, agentos):
        agentos.queue(_reply(AGNO_WIRE_BODY))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "Hello world."

    async def test_parses_event_from_sse_event_line_only(self, mock_context, agentos):
        """Canonical SSE: event type on the ``event:`` line, payload carrying only ``content``."""
        agentos.queue(
            _reply(
                "event: RunStarted\n"
                "data: {}\n"
                "\n"
                "event: RunContent\n"
                'data: {"content":"Hello "}\n'
                "\n"
                "event: RunContent\n"
                'data: {"content":"world."}\n'
                "\n"
                "event: RunCompleted\n"
                'data: {"content":"Hello world."}\n'
                "\n"
            )
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "Hello world."

    async def test_parses_crlf_framed_sse(self, mock_context, agentos):
        agentos.queue(_reply('data: {"event": "RunCompleted", "content": "crlf works"}\r\n\r\n'))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "crlf works"

    async def test_trailing_event_without_blank_line_is_parsed(self, mock_context, agentos):
        agentos.queue(_reply('data: {"event": "RunCompleted", "content": "last"}'))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "last"

    async def test_preserves_plain_text_body(self, mock_context, agentos):
        """A plain (non-SSE) body is returned as the answer, even if labelled as an event stream."""
        agentos.queue(_reply("Plain text response with no SSE framing"))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "Plain text response with no SSE framing"

    async def test_preserves_plain_multiline_body(self, mock_context, agentos):
        agentos.queue(_reply("Line one\n\nLine two\n"))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "Line one\n\nLine two\n"

    async def test_preserves_non_sse_json_body(self, mock_context, agentos):
        agentos.queue(_reply({"content": "There are 42 active users."}))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "There are 42 active users."

    async def test_json_body_split_across_reads_is_read_whole(self, mock_context, agentos):
        agentos.queue(
            _reply('{"content": "There are 42 active users."}', content_type="application/json", chunk_size=5)
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "There are 42 active users."

    @pytest.mark.parametrize("content_type", ["text/plain", "text/event-stream"])
    async def test_plain_answer_starting_with_sse_field_name_is_kept(self, mock_context, agentos, content_type: str):
        """Text that merely starts with ``id:`` or ``retry:`` has no SSE data, so it is a plain answer."""
        agentos.queue(_reply("id: 42 name: Ada", content_type=content_type))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "id: 42 name: Ada"

    async def test_invalid_json_body_falls_back_to_text(self, mock_context, agentos):
        agentos.queue(_reply("not json", content_type="application/json"))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "not json"

    async def test_sse_content_type_with_charset_is_streamed(self, mock_context, agentos):
        agentos.queue(
            _reply(
                AGNO_WIRE_BODY.replace("Hello world.", "charset ok"),
                content_type="text/event-stream; charset=utf-8",
            )
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "charset ok"

    async def test_text_plain_body_is_returned_as_answer(self, mock_context, agentos):
        agentos.queue(_reply("A plain answer.", content_type="text/plain"))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "A plain answer."

    async def test_sse_text_under_non_sse_content_type_is_parsed(self, mock_context, agentos):
        agentos.queue(_reply(AGNO_WIRE_BODY, content_type="text/plain"))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "Hello world."

    async def test_json_list_body_returns_default_message(self, mock_context, agentos):
        agentos.queue(_reply("[1, 2]", content_type="application/json"))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "No response from agent."

    @pytest.mark.parametrize("content_type", ["text/plain", "application/json"])
    async def test_oversized_plain_body_returns_action_error(self, mock_context, agentos, content_type: str):
        agentos.queue(_reply("z" * (MAX_EVENT_BYTES + 100), content_type=content_type, chunk_size=64 * 1024))

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "too large" in result.result.message

    async def test_json_body_at_cap_is_parsed(self, mock_context, agentos):
        content = "j" * (MAX_EVENT_BYTES - len('{"content": ""}'))
        agentos.queue(_reply(json.dumps({"content": content}), content_type="application/json", chunk_size=64 * 1024))

        result = await _ask(mock_context)

        assert result.result.data["response"] == content

    async def test_plain_body_at_cap_is_returned_whole(self, mock_context, agentos):
        agentos.queue(_reply("z" * MAX_EVENT_BYTES, content_type="text/plain", chunk_size=64 * 1024))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "z" * MAX_EVENT_BYTES


class TestAskAgentRetry:
    async def test_retries_with_exponential_backoff_then_succeeds(self, mock_context, agentos, no_sleep):
        agentos.queue(
            _reply("<html>504</html>", status=504, content_type="text/html"),
            _reply("<html>504</html>", status=504, content_type="text/html"),
            _reply(_sse('data: {"event": "RunCompleted", "content": "answer"}')),
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "answer"
        assert len(agentos.calls) == 3
        # Exponential backoff: 2**0 = 1s, 2**1 = 2s
        assert [c.args for c in no_sleep.await_args_list] == [(1,), (2,)]

    @pytest.mark.parametrize("status", [502, 503, 504])
    async def test_retries_each_gateway_status(self, mock_context, agentos, no_sleep, status: int):
        agentos.queue(
            _reply("gateway error", status=status, content_type="text/plain"),
            _reply(_sse('data: {"event": "RunCompleted", "content": "ok"}')),
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "ok"
        assert len(agentos.calls) == 2

    async def test_returns_action_error_after_max_retries(self, mock_context, agentos, no_sleep):
        """Exhausted gateway retries return ActionError (not raise) so the user sees a
        clean message and error tracking isn't paged for a service-availability condition."""
        agentos.queue(*[_reply("<html>504</html>", status=504, content_type="text/html") for _ in range(3)])

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "504" in result.result.message
        assert "temporarily unavailable" in result.result.message
        assert len(agentos.calls) == 3

    async def test_does_not_retry_on_4xx(self, mock_context, agentos, no_sleep):
        agentos.queue(_reply("bad request", status=400, content_type="text/plain"))

        with pytest.raises(HTTPError) as exc_info:
            await _ask(mock_context)

        assert exc_info.value.status == 400
        assert exc_info.value.message == "bad request"
        assert len(agentos.calls) == 1
        no_sleep.assert_not_awaited()

    async def test_retries_connection_failure(self, mock_context, agentos, no_sleep):
        agentos.queue(
            aiohttp.ClientConnectorError(AsyncMock(), OSError("connection refused")),
            _reply(_sse('data: {"event": "RunCompleted", "content": "ok"}')),
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "ok"
        assert len(agentos.calls) == 2
        no_sleep.assert_awaited_once_with(1)

    async def test_connection_failure_returns_action_error_after_max_attempts(self, mock_context, agentos, no_sleep):
        agentos.queue(*[aiohttp.ClientConnectorError(AsyncMock(), OSError("refused")) for _ in range(3)])

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Could not reach the agent service" in result.result.message
        assert len(agentos.calls) == 3

    @pytest.mark.parametrize(
        "error",
        [
            asyncio.TimeoutError(),
            aiohttp.ClientPayloadError("Response payload is not completed"),
            aiohttp.ServerDisconnectedError(),
        ],
    )
    async def test_mid_stream_failure_returns_action_error_without_retry(
        self, mock_context, agentos, no_sleep, error: Exception
    ):
        """A run that times out or loses its connection mid-stream may already be executing
        on the server, so it is not re-POSTed; the user gets a clean error instead."""
        agentos.queue(_reply(_sse('data: {"event": "RunStarted"}'), error=error))

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "did not finish" in result.result.message
        assert len(agentos.calls) == 1
        no_sleep.assert_not_awaited()

    @pytest.mark.parametrize("status", [502, 503])
    async def test_action_error_names_last_gateway_status(self, mock_context, agentos, no_sleep, status: int):
        agentos.queue(*[_reply("gateway error", status=status, content_type="text/plain") for _ in range(3)])

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert f"HTTP {status}" in result.result.message

    @pytest.mark.parametrize("status", [429, 500])
    async def test_non_gateway_errors_are_not_retried(self, mock_context, agentos, no_sleep, status: int):
        agentos.queue(_reply("error", status=status, content_type="text/plain"))

        with pytest.raises(HTTPError) as exc_info:
            await _ask(mock_context)

        assert exc_info.value.status == status
        assert len(agentos.calls) == 1
        no_sleep.assert_not_awaited()

    async def test_connection_failure_and_gateway_error_share_attempt_budget(self, mock_context, agentos, no_sleep):
        agentos.queue(
            aiohttp.ClientConnectorError(AsyncMock(), OSError("refused")),
            _reply("<html>504</html>", status=504, content_type="text/html"),
            _reply(_sse('data: {"event": "RunCompleted", "content": "ok"}')),
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "ok"
        assert len(agentos.calls) == 3


class TestAskAgentMemoryBounds:
    """The run stream is read incrementally so large tool results can't exhaust memory."""

    async def test_large_tool_result_is_not_buffered(self, mock_context, agentos):
        """Regression: a 'return the full table' query streamed ~50 MB of ToolCallCompleted
        SQL results and the action ran out of memory. Non-answer events must be discarded
        as they stream, not held in memory."""
        body = (
            b"event: RunStarted\n"
            b'data: {"event":"RunStarted"}\n'
            b"\n"
            b"event: ToolCallCompleted\n"
            b'data: {"event":"ToolCallCompleted","tool":{"result":"' + b"row," * (12 * 1024 * 1024) + b'"}}\n'
            b"\n"
            b"event: RunCompleted\n"
            b'data: {"event":"RunCompleted","content":"12 accounts dropped 20% or more."}\n'
            b"\n"
        )
        assert len(body) > 40 * 1024 * 1024
        agentos.queue(_reply(body, chunk_size=64 * 1024))

        tracemalloc.start()
        result = await _ask(mock_context, query="full table")
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert result.result.data["response"] == "12 accounts dropped 20% or more."
        assert peak < 2 * 1024 * 1024

    async def test_oversized_event_without_event_line_is_dropped(self, mock_context, agentos):
        """Events typed only inside their JSON are buffered up to the cap, then dropped."""
        huge = "x" * (MAX_EVENT_BYTES + 1)
        agentos.queue(
            _reply(
                _sse(
                    f'data: {{"event": "ToolCallCompleted", "content": "{huge}"}}',
                    'data: {"event": "RunCompleted", "content": "done"}',
                ),
                chunk_size=64 * 1024,
            )
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "done"

    async def test_long_answer_is_returned_in_full(self, mock_context, agentos):
        answer = "a" * 500_000
        agentos.queue(
            _reply("data: " + json.dumps({"event": "RunCompleted", "content": answer}) + "\n\n", chunk_size=4096)
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == answer

    async def test_oversized_chunked_answer_returns_action_error(self, mock_context, agentos):
        """Chunks past the memory bound are reported, not silently cut to a prefix."""
        agentos.queue(_reply(_sse(*_overflowing_chunks()), chunk_size=64 * 1024))

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "too large" in result.result.message

    async def test_oversized_run_completed_returns_action_error(self, mock_context, agentos):
        big = "c" * (MAX_EVENT_BYTES + 1)
        agentos.queue(
            _reply(
                f'event: RunStarted\ndata: {{"event": "RunStarted"}}\n\n'
                f'event: RunCompleted\ndata: {{"content": "{big}"}}\n\n',
                chunk_size=64 * 1024,
            )
        )

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "too large" in result.result.message

    async def test_oversized_run_content_event_returns_action_error(self, mock_context, agentos):
        big = "c" * (MAX_EVENT_BYTES + 1)
        agentos.queue(_reply(f'event: RunContent\ndata: {{"content": "{big}"}}\n\n', chunk_size=64 * 1024))

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "too large" in result.result.message

    async def test_too_large_error_names_limit_and_is_not_retried(self, mock_context, agentos, no_sleep):
        agentos.queue(_reply(_sse(*_overflowing_chunks()), chunk_size=64 * 1024))

        result = await _ask(mock_context)

        assert "over 2 MB" in result.result.message
        assert "narrower" in result.result.message
        assert len(agentos.calls) == 1
        no_sleep.assert_not_awaited()

    async def test_run_completed_supersedes_chunk_overflow(self, mock_context, agentos):
        events = [*_overflowing_chunks(), 'data: {"event": "RunCompleted", "content": "final answer"}']
        agentos.queue(_reply(_sse(*events), chunk_size=64 * 1024))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "final answer"

    async def test_error_body_is_capped(self, mock_context, agentos):
        agentos.queue(_reply("e" * (MAX_ERROR_BODY_BYTES * 10), status=400, content_type="text/plain"))

        with pytest.raises(HTTPError) as exc_info:
            await _ask(mock_context)

        assert len(exc_info.value.message) == MAX_ERROR_BODY_BYTES

    async def test_short_error_body_is_kept_whole(self, mock_context, agentos):
        agentos.queue(_reply("agent not found", status=404, content_type="text/plain", chunk_size=3))

        with pytest.raises(HTTPError) as exc_info:
            await _ask(mock_context)

        assert exc_info.value.message == "agent not found"


# ---- Helpers ----


class TestSSEAnswerCollector:
    def test_leading_utf8_bom_is_ignored(self):
        """SSE streams may begin with a UTF-8 BOM, which must not be mistaken for a plain body."""
        collector = _SSEAnswerCollector()
        collector.feed('\ufeffevent: RunCompleted\ndata: {"event":"RunCompleted","content":"ANS"}\n\n'.encode())

        assert collector.finish() == "ANS"

    def test_event_line_type_decides_skipping(self):
        """Non-answer events are discarded on their ``event:`` line without reading the
        payload — that is what bounds memory — so a payload can't override it."""
        collector = _SSEAnswerCollector()
        collector.feed(b'event: ToolCallCompleted\ndata: {"event":"RunCompleted","content":"ANS"}\n\n')

        assert collector.finish() == ""

    @pytest.mark.parametrize("chunk_size", [1, 2, 5, 64 * 1024])
    def test_chunk_boundaries_do_not_change_result(self, chunk_size: int):
        raw = AGNO_WIRE_BODY.encode()
        collector = _SSEAnswerCollector()
        for i in range(0, len(raw), chunk_size):
            collector.feed(raw[i : i + chunk_size])

        assert collector.finish() == "Hello world."

    def test_skipped_event_still_ends_at_blank_line(self):
        """A discarded event's blank line must still close it, so the next event parses."""
        collector = _SSEAnswerCollector()
        for byte in (
            b"event: ToolCallStarted\r\n"
            b'data: {"event":"ToolCallStarted"}\r\n'
            b"\r\n"
            b"event: RunContent\r\n"
            b'data: {"content":"kept"}\r\n'
            b"\r\n"
        ):
            collector.feed(bytes([byte]))

        assert collector.finish() == "kept"

    def test_multibyte_utf8_split_across_chunks(self):
        raw = 'data: {"event": "RunCompleted", "content": "Kia ora — ā ē ī 🌋"}\n\n'.encode()
        collector = _SSEAnswerCollector()
        for i in range(len(raw)):
            collector.feed(raw[i : i + 1])

        assert collector.finish() == "Kia ora — ā ē ī 🌋"

    @pytest.mark.parametrize(
        "body, expected",
        [
            # Multi-line data is joined with newlines before parsing.
            ('event: RunCompleted\ndata: {"event": "RunCompleted",\ndata: "content": "joined"}\n\n', "joined"),
            # id:, retry: and comment lines are ignored.
            (': keep-alive\nid: 7\nretry: 1000\ndata: {"event": "RunCompleted", "content": "ok"}\n\n', "ok"),
            # Blank lines before the first event don't make the body look plain.
            ('\n\ndata: {"event": "RunCompleted", "content": "ok"}\n\n', "ok"),
            # The event: line value is trimmed.
            ('event:   RunContent  \ndata: {"content": "trimmed"}\n\n', "trimmed"),
            # Invalid JSON, non-object JSON and non-string content are skipped, not fatal.
            (
                'data: {not json}\n\ndata: [1]\n\ndata: {"event": "RunCompleted", "content": 5}\n\n'
                'data: {"event": "RunContent", "content": "survived"}\n\n',
                "survived",
            ),
            # Unknown event types are ignored.
            ('data: {"event": "RunMetrics", "content": "noise"}\n\n', ""),
            # An empty RunCompleted falls back to the streamed chunks.
            (
                'data: {"event": "RunContent", "content": "chunk"}\n\n'
                'data: {"event": "RunCompleted", "content": ""}\n\n',
                "chunk",
            ),
            # RunCompleted wins even when chunks follow it.
            (
                'data: {"event": "RunCompleted", "content": "final"}\n\n'
                'data: {"event": "RunContent", "content": "late"}\n\n',
                "final",
            ),
            # A plain body without a trailing newline is returned exactly.
            ("no newline at end", "no newline at end"),
            ("", ""),
        ],
    )
    def test_answer_selection(self, body: str, expected: str):
        collector = _SSEAnswerCollector()
        collector.feed(body.encode())

        assert collector.finish() == expected

    def test_event_dropped_when_data_lines_exceed_cap_together(self):
        half = "x" * (MAX_EVENT_BYTES // 2 + 1)
        collector = _SSEAnswerCollector()
        collector.feed(
            f'data: {{"event": "RunCompleted",\ndata: "pad": "{half}",\ndata: "more": "{half}", "content": "big"}}\n\n'
            'data: {"event": "RunContent", "content": "next"}\n\n'.encode()
        )

        assert collector.finish() == "next"

    def test_oversized_plain_line_raises(self):
        collector = _SSEAnswerCollector()

        with pytest.raises(AnswerTooLargeError):
            collector.feed(b"plain " + b"y" * (MAX_EVENT_BYTES * 2))

    @pytest.mark.parametrize("body", [b": keep-alive\n\n", b": ping\n\n: ping\n\n"])
    def test_keep_alive_only_stream_has_no_answer(self, body: bytes):
        collector = _SSEAnswerCollector()
        collector.feed(body)

        assert collector.finish() == ""

    @pytest.mark.parametrize("body", [b"\n\n", b" \n", b"\r\n \r\n"])
    def test_blank_body_has_no_answer(self, body: bytes):
        collector = _SSEAnswerCollector()
        collector.feed(body)

        assert collector.finish() == ""

    def test_oversized_run_completed_keeps_complete_streamed_answer(self):
        """A RunCompleted inflated past the bound by metadata doesn't discard the streamed chunks."""
        heavy = "m" * (MAX_EVENT_BYTES + 1)
        collector = _SSEAnswerCollector()
        collector.feed(
            b'event: RunContent\ndata: {"content": "hel"}\n\n'
            b'event: RunContent\ndata: {"content": "lo"}\n\n'
            + f'event: RunCompleted\ndata: {{"content": "hello", "metrics": "{heavy}"}}\n\n'.encode()
        )

        assert collector.finish() == "hello"

    def test_bom_before_oversized_first_event_is_still_sse(self):
        big = "x" * (MAX_EVENT_BYTES + 1)
        collector = _SSEAnswerCollector()
        collector.feed(
            f'\ufeffdata: {{"event": "ToolCallCompleted", "content": "{big}"}}\n\n'.encode()
            + b'data: {"event": "RunCompleted", "content": "ANS"}\n\n'
        )

        assert collector.finish() == "ANS"

    def test_preamble_then_plain_line_is_returned_whole(self):
        collector = _SSEAnswerCollector()
        collector.feed(b"id: 42\nname: Ada\n")

        assert collector.finish() == "id: 42\nname: Ada\n"

    def test_oversized_preamble_line_raises(self):
        collector = _SSEAnswerCollector()

        with pytest.raises(AnswerTooLargeError):
            collector.feed(b"id: " + b"9" * (MAX_EVENT_BYTES + 1))

    def test_oversized_event_typed_only_in_json_is_dropped(self):
        """Without an ``event:`` line the type is unknown until parsed, so an oversized event
        is dropped rather than reported; Agno always sends the ``event:`` line."""
        big = "z" * (MAX_EVENT_BYTES + 1)
        collector = _SSEAnswerCollector()
        collector.feed(f'data: {{"event": "RunCompleted", "content": "{big}"}}\n\n'.encode())

        assert collector.finish() == ""

    def test_oversized_plain_body_stops_reading_at_cap(self):
        """An endless plain answer fails as soon as it passes the cap, not at the read timeout."""
        collector = _SSEAnswerCollector()
        collector.feed(b"plain answer\n")

        with pytest.raises(AnswerTooLargeError):
            collector.feed(b"y" * (MAX_EVENT_BYTES + 1))

    def test_blank_lines_in_preamble_only_body_are_kept(self):
        collector = _SSEAnswerCollector()
        collector.feed(b"id: 1\n\nhello")

        assert collector.finish() == "id: 1\n\nhello"

    def test_preamble_is_discarded_once_body_is_sse(self):
        collector = _SSEAnswerCollector()
        collector.feed(b'id: 1\nretry: 5\ndata: {"event": "RunCompleted", "content": "ok"}\n\n')

        assert collector.finish() == "ok"


class TestExtractAnswer:
    @pytest.mark.parametrize(
        "body, expected",
        [
            ({"content": "from content"}, "from content"),
            ({"message": "from message"}, "from message"),
            ({"other": 1}, ""),
            ("plain text", "plain text"),
            (_sse('data: {"event": "RunStarted"}'), ""),
            (None, ""),
        ],
    )
    def test_extract_answer(self, body: Any, expected: str):
        assert _extract_answer(body) == expected


# ---- Connected account ----


class TestConnectedAccountHandler:
    async def test_get_account_info_calls_health(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"status": "ok"})

        result = await AgnoConnectedAccountHandler().get_account_info(mock_context)

        mock_context.fetch.assert_called_once_with(
            "https://agno.example.com/health",
            method="GET",
            headers={"Authorization": "Bearer test-token"},
            timeout=10,
        )
        assert result.username == "my-agent @ https://agno.example.com"

    async def test_get_account_info_without_token_sends_no_auth_header(self, make_context):
        context = make_context(
            auth={"auth_type": "Custom", "credentials": {"api_url": "https://agno.example.com", "agent_id": "my-agent"}}
        )
        context.fetch.return_value = FetchResponse(status=200, headers={}, data={"status": "ok"})

        await AgnoConnectedAccountHandler().get_account_info(context)

        assert context.fetch.call_args.kwargs["headers"] == {}

    async def test_get_account_info_raises_on_failure(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        with pytest.raises(Exception, match="Connection refused"):
            await AgnoConnectedAccountHandler().get_account_info(mock_context)

    async def test_get_account_info_raises_on_missing_url(self, make_context):
        context = make_context(auth={"auth_type": "Custom", "credentials": {}})

        with pytest.raises(Exception, match="api_url"):
            await AgnoConnectedAccountHandler().get_account_info(context)
