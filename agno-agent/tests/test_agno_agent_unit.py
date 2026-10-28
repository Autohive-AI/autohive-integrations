"""Unit tests for the agno-agent integration (Agno AgentOS API)."""

import asyncio
import gzip
import json
import tracemalloc
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

from agno_agent import (
    MAX_ERROR_BODY_BYTES,
    MAX_EVENT_BYTES,
    AgnoConnectedAccountHandler,
    AgentRunError,
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


def _feed_in_chunks(raw: bytes, chunk_size: int) -> _SSEAnswerCollector:
    collector = _SSEAnswerCollector()
    for i in range(0, len(raw), chunk_size):
        collector.feed(raw[i : i + chunk_size])
    return collector


def _large_tool_result_body() -> bytes:
    """An Agno run whose ToolCallCompleted event carries ~48 MB of SQL rows."""
    return b"".join(
        [
            b'event: RunStarted\ndata: {"event":"RunStarted"}\n\n',
            b'event: ToolCallCompleted\ndata: {"event":"ToolCallCompleted","tool":{"result":"',
            b"row," * (12 * 1024 * 1024),
            b'"}}\n\n',
            b'event: RunCompleted\ndata: {"event":"RunCompleted","content":"12 accounts dropped 20% or more."}\n\n',
        ]
    )


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
        if not data and self._error:
            raise self._error
        return data


class _FakeResponse:
    def __init__(
        self,
        body: bytes,
        status: int,
        content_type: str,
        chunk_size: int,
        error: Exception | None,
        headers: dict[str, str] | None = None,
    ):
        self.status = status
        self.headers = headers or {}
        # aiohttp's parsed media type: lowercased, parameters stripped.
        self.content_type = content_type.split(";")[0].strip().lower()
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
    headers: dict[str, str] | None = None,
) -> _FakeResponse:
    """Build a fake AgentOS HTTP response. Dict bodies are sent as JSON; ``error`` is
    raised mid-stream after the body has been delivered."""
    if isinstance(body, dict):
        body, content_type = json.dumps(body), "application/json"
    raw = body if isinstance(body, bytes) else body.encode("utf-8")
    return _FakeResponse(raw, status, content_type, chunk_size, error, headers)


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

    async def test_parses_bare_cr_framed_sse(self, mock_context, agentos):
        agentos.queue(_reply('event: RunCompleted\rdata: {"event": "RunCompleted", "content": "cr works"}\r\r'))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "cr works"

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
    @pytest.mark.parametrize(
        "answer", ["id: 42 name: Ada", "event: launch moved to Friday\nTeam notified.", ": note\nTotal is 42."]
    )
    async def test_plain_answer_starting_with_sse_field_name_is_kept(
        self, mock_context, agentos, content_type: str, answer: str
    ):
        """Text that merely starts like SSE metadata has no ``data:`` line, so it is a plain answer."""
        agentos.queue(_reply(answer, content_type=content_type))

        result = await _ask(mock_context)

        assert result.result.data["response"] == answer

    @pytest.mark.parametrize("content_type", ["Application/JSON", "APPLICATION/JSON; charset=utf-8"])
    async def test_json_content_type_is_case_insensitive(self, mock_context, agentos, content_type: str):
        agentos.queue(_reply('{"content": "case ok"}', content_type=content_type))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "case ok"

    @pytest.mark.parametrize("content_type", ["", "application/problem+json", "text/json"])
    async def test_non_json_media_type_body_is_returned_as_text(self, mock_context, agentos, content_type: str):
        """Only application/json is parsed as JSON; anything else is returned as plain text."""
        agentos.queue(_reply('{"content": "x"}', content_type=content_type))

        result = await _ask(mock_context)

        assert result.result.data["response"] == '{"content": "x"}'

    async def test_json_string_body_is_returned_as_answer(self, mock_context, agentos):
        agentos.queue(_reply('"There are 42 active users."', content_type="application/json"))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "There are 42 active users."

    async def test_invalid_utf8_json_body_falls_back_to_text(self, mock_context, agentos):
        agentos.queue(_reply(b"caf\xe9 answer", content_type="application/json"))

        result = await _ask(mock_context)

        assert result.result.data["response"] == "caf\ufffd answer"

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

    @pytest.mark.parametrize(
        "error", [aiohttp.ClientPayloadError("Response payload is not completed"), asyncio.TimeoutError()]
    )
    async def test_gateway_status_kept_when_error_body_read_fails(
        self, mock_context, agentos, no_sleep, error: Exception
    ):
        """A 503 that drops or times out while its error body is read is still a retryable gateway error."""
        agentos.queue(
            _reply("partial", status=503, content_type="text/html", error=error),
            _reply(_sse('data: {"event": "RunCompleted", "content": "ok"}')),
        )

        result = await _ask(mock_context)

        assert result.result.data["response"] == "ok"
        assert len(agentos.calls) == 2

    async def test_client_error_status_kept_when_error_body_read_fails(self, mock_context, agentos, no_sleep):
        agentos.queue(
            _reply("partial", status=400, content_type="text/plain", error=aiohttp.ClientPayloadError("cut off"))
        )

        with pytest.raises(HTTPError) as exc_info:
            await _ask(mock_context)

        assert exc_info.value.status == 400
        assert len(agentos.calls) == 1

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

    async def test_non_gateway_errors_are_not_retried(self, mock_context, agentos, no_sleep):
        agentos.queue(_reply("error", status=500, content_type="text/plain"))

        with pytest.raises(HTTPError) as exc_info:
            await _ask(mock_context)

        assert exc_info.value.status == 500
        assert not isinstance(exc_info.value, RateLimitError)
        assert len(agentos.calls) == 1
        no_sleep.assert_not_awaited()

    @pytest.mark.parametrize(
        "headers, retry_after",
        [
            ({"Retry-After": "17"}, 17),
            ({}, 60),
            ({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, 60),
            ({"Retry-After": "-5"}, 0),
            ({"Retry-After": "0"}, 0),
            ({"Retry-After": " 17 "}, 17),
            ({"Retry-After": "1.5"}, 60),
        ],
    )
    async def test_rate_limit_raises_rate_limit_error_with_retry_after(
        self, mock_context, agentos, no_sleep, headers: dict, retry_after: int
    ):
        """Matches context.fetch: a 429 raises RateLimitError carrying Retry-After and is not retried."""
        agentos.queue(_reply("slow down", status=429, content_type="text/plain", headers=headers))

        with pytest.raises(RateLimitError) as exc_info:
            await _ask(mock_context)

        assert exc_info.value.status == 429
        assert exc_info.value.retry_after == retry_after
        assert exc_info.value.message == "Rate limit exceeded"
        assert exc_info.value.response_data == "slow down"
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

    @pytest.mark.parametrize("api_url", ["agno.example.com", "htps://agno.example.com", "http://"])
    async def test_invalid_api_url_returns_action_error(self, mock_context, no_sleep, api_url: str):
        """Uses the real aiohttp client, which rejects these URLs before sending anything."""
        mock_context.auth["credentials"]["api_url"] = api_url

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API URL is not a valid" in result.result.message
        no_sleep.assert_not_awaited()


class TestAskAgentMemoryBounds:
    """The run stream is read incrementally so large tool results can't exhaust memory."""

    async def test_large_tool_result_is_not_buffered(self, mock_context, agentos):
        """Regression: a 'return the full table' query streamed ~50 MB of ToolCallCompleted
        SQL results and the action ran out of memory. Non-answer events must be discarded
        as they stream, not held in memory."""
        body = _large_tool_result_body()
        assert len(body) > 40 * 1024 * 1024
        agentos.queue(_reply(body, chunk_size=64 * 1024))

        tracemalloc.start()
        try:
            result = await _ask(mock_context, query="full table")
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert result.result.data["response"] == "12 accounts dropped 20% or more."
        assert peak < 2 * 1024 * 1024

    async def test_large_gzip_tool_result_over_real_http_is_not_buffered(self, mock_context):
        """Regression: aiohttp before 3.14 inflated a whole gzip chunk at once, so a compressed
        ~48 MB tool result was buffered before the collector saw it. Uses the real transport."""
        body = gzip.compress(_large_tool_result_body(), compresslevel=1)

        async def runs(request: web.Request) -> web.Response:
            return web.Response(body=body, content_type="text/event-stream", headers={"Content-Encoding": "gzip"})

        app = web.Application()
        app.router.add_post("/agents/my-agent/runs", runs)
        async with TestServer(app) as server:
            mock_context.auth["credentials"]["api_url"] = str(server.make_url(""))
            tracemalloc.start()
            try:
                result = await _ask(mock_context, query="full table")
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

        assert result.result.data["response"] == "12 accounts dropped 20% or more."
        assert peak < 8 * 1024 * 1024

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

    async def test_oversized_untyped_answer_returns_action_error_not_draft(self, mock_context, agentos):
        """Older deployments type events only in the JSON; an oversized one may be the final answer."""
        big = "c" * (MAX_EVENT_BYTES + 1)
        agentos.queue(
            _reply(
                _sse(
                    'data: {"event": "RunContent", "content": "draft"}',
                    f'data: {{"event": "RunCompleted", "content": "{big}"}}',
                ),
                chunk_size=64 * 1024,
            )
        )

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "too large" in result.result.message

    async def test_run_error_returns_action_error_with_agent_reason(self, mock_context, agentos):
        """Regression: a failed run (e.g. a huge SQL result overflowing the model's context) used to
        come back as "No response from agent." with the reason lost."""
        reason = "Your input exceeds the context window of this model."
        agentos.queue(
            _reply(
                'event: RunStarted\ndata: {"event":"RunStarted"}\n\n'
                'event: RunContent\ndata: {"content":"Let me run"}\n\n'
                f'event: RunError\ndata: {{"event":"RunError","content":"{reason}"}}\n\n'
            )
        )

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == f"The agent could not finish this request: {reason}"

    async def test_oversized_run_error_returns_action_error_not_draft(self, mock_context, agentos):
        big = "e" * (MAX_EVENT_BYTES + 1)
        agentos.queue(
            _reply(
                'event: RunContent\ndata: {"content":"partial draft"}\n\n'
                f'event: RunError\ndata: {{"content":"{big}"}}\n\n',
                chunk_size=64 * 1024,
            )
        )

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message.startswith("The agent could not finish this request: ")

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

    @pytest.mark.parametrize(
        "before, completed",
        [
            ('event: RunStarted\ndata: {"event": "RunStarted"}', '"content": "{big}"'),
            # The chunks are only a draft: a post-hook may have rewritten the dropped final answer.
            ('event: RunContent\ndata: {"content": "draft"}', '"content": "final", "session_state": "{big}"'),
        ],
    )
    async def test_oversized_run_completed_returns_action_error(
        self, mock_context, agentos, before: str, completed: str
    ):
        big = "c" * (MAX_EVENT_BYTES + 1)
        completed = completed.replace("{big}", big)
        agentos.queue(_reply(f"{before}\n\nevent: RunCompleted\ndata: {{{completed}}}\n\n", chunk_size=64 * 1024))

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

    async def test_answer_limit_counts_utf8_bytes(self, mock_context, agentos):
        """Emoji are 4 bytes each, so these chunks pass the byte limit while staying under it in characters."""
        chunk = "😀" * 25_000
        events = [json.dumps({"event": "RunContent", "content": chunk}) for _ in range(30)]
        assert 30 * len(chunk) < MAX_EVENT_BYTES < 30 * len(chunk.encode())
        agentos.queue(_reply(_sse(*[f"data: {e}" for e in events]), chunk_size=64 * 1024))

        result = await _ask(mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "too large" in result.result.message

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
        collector = _feed_in_chunks(raw, chunk_size)

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

    @pytest.mark.parametrize("line_end", ["\r", "\r\n"])
    @pytest.mark.parametrize("chunk_size", [1, 2, 5, 64 * 1024])
    def test_cr_and_crlf_line_ends_match_lf(self, line_end: str, chunk_size: int):
        raw = AGNO_WIRE_BODY.replace("\n", line_end).encode()
        collector = _feed_in_chunks(raw, chunk_size)

        assert collector.finish() == "Hello world."

    def test_mixed_line_ends_in_one_stream(self):
        collector = _SSEAnswerCollector()
        collector.feed(b'event: RunContent\rdata: {"content":"a"}\n\r\nevent: RunContent\r\ndata: {"content":"b"}\r\n')

        assert collector.finish() == "ab"

    def test_crlf_split_across_chunks_is_one_line_end(self):
        """The LF after a chunk-final CR must not read as a blank line ending the event early."""
        collector = _SSEAnswerCollector()
        collector.feed(b'event: RunCompleted\r\ndata: {"event": "RunCompleted",\r')
        collector.feed(b'\ndata: "content": "joined"}\r')
        collector.feed(b"\n\r")
        collector.feed(b"\n")

        assert collector.finish() == "joined"

    def test_cr_then_lf_in_next_chunk_after_blank_line_is_not_another_blank_line(self):
        collector = _SSEAnswerCollector()
        collector.feed(b'event: RunContent\rdata: {"content":"one"}\r\r')
        collector.feed(b'\nevent: RunContent\rdata: {"content":"two"}\r\r')

        assert collector.finish() == "onetwo"

    def test_skipped_event_still_ends_at_bare_cr_blank_line(self):
        collector = _SSEAnswerCollector()
        for byte in (
            b'event: ToolCallStarted\rdata: {"event":"ToolCallStarted"}\r\r'
            b'event: RunContent\rdata: {"content":"kept"}\r\r'
        ):
            collector.feed(bytes([byte]))

        assert collector.finish() == "kept"

    def test_oversized_skipped_event_with_bare_cr_line_ends(self):
        huge = "x" * (MAX_EVENT_BYTES + 1024)
        raw = (
            f'event: ToolCallCompleted\rdata: {{"content": "{huge}"}}\r\r'
            'event: RunContent\rdata: {"content":"kept"}\r\r'
        ).encode()
        collector = _feed_in_chunks(raw, 64 * 1024)

        assert collector.finish() == "kept"

    def test_preamble_with_bare_cr_line_ends_is_still_sse(self):
        collector = _SSEAnswerCollector()
        collector.feed(b'id: 1\rretry: 500\r\rdata: {"event": "RunCompleted", "content": "after preamble"}\r\r')

        assert collector.finish() == "after preamble"

    @pytest.mark.parametrize("line_end", [b"\r", b"\r\n"])
    def test_plain_text_lines_ending_in_cr_are_joined_with_lf(self, line_end: bytes):
        collector = _SSEAnswerCollector()
        collector.feed(b"first line" + line_end + b"second")

        assert collector.finish() == "first line\nsecond"

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
            # The oldest Agno chunk name, RunResponse, is still collected.
            (
                'data: {"event": "RunResponse", "content": "leg"}\n\n'
                'data: {"event": "RunResponse", "content": "acy"}\n\n',
                "legacy",
            ),
            # Between two answer types, the payload's event field wins over the event: line.
            (
                'event: RunContent\ndata: {"event": "RunCompleted", "content": "final"}\n\n'
                'event: RunContent\ndata: {"content": "late"}\n\n',
                "final",
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

    def test_untyped_event_over_cap_across_data_lines_is_reported(self):
        """The dropped event may have been the answer, so later chunks aren't returned in its place."""
        half = "x" * (MAX_EVENT_BYTES // 2 + 1)
        collector = _SSEAnswerCollector()
        collector.feed(
            f'data: {{"event": "RunCompleted",\ndata: "pad": "{half}",\ndata: "more": "{half}", "content": "big"}}\n\n'
            'data: {"event": "RunContent", "content": "next"}\n\n'.encode()
        )

        with pytest.raises(AnswerTooLargeError):
            collector.finish()

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

    @pytest.mark.parametrize("chunk_size", [7, 64 * 1024, MAX_EVENT_BYTES * 2])
    def test_oversized_run_completed_is_not_replaced_by_streamed_chunks(self, chunk_size: int):
        """A post-hook can rewrite the final answer, so the chunks are only a draft of a dropped RunCompleted."""
        heavy = "m" * (MAX_EVENT_BYTES + 1)
        raw = (
            'event: RunContent\ndata: {"content": "dra"}\n\n'
            'event: RunContent\ndata: {"content": "ft"}\n\n'
            f'event: RunCompleted\ndata: {{"content": "final", "session_state": "{heavy}"}}\n\n'
        ).encode()
        collector = _feed_in_chunks(raw, chunk_size)

        with pytest.raises(AnswerTooLargeError):
            collector.finish()

    def test_oversized_non_answer_event_does_not_block_chunk_answer(self):
        heavy = "m" * (MAX_EVENT_BYTES + 1)
        collector = _SSEAnswerCollector()
        collector.feed(
            f'event: RunStarted\ndata: {{"pad": "{heavy}"}}\n\n'.encode()
            + b'event: RunContent\ndata: {"content": "kept"}\n\n'
        )

        assert collector.finish() == "kept"

    def test_bom_before_oversized_first_event_is_still_sse(self):
        big = "x" * (MAX_EVENT_BYTES + 1)
        collector = _SSEAnswerCollector()
        collector.feed(
            f'\ufeffdata: {{"event": "ToolCallCompleted", "content": "{big}"}}\n\n'.encode()
            + b'data: {"event": "RunCompleted", "content": "ANS"}\n\n'
        )

        assert collector.finish() == "ANS"

    @pytest.mark.parametrize(
        "body",
        [
            b"event: launch moved to Friday\nTeam notified.\n",
            b"event: launch moved to Friday",
            b"id: 42\nevent: signup\nretry: tomorrow",
            b": note\nTotal is 42.",
            b"\xef\xbb\xbfevent: launch moved\nok",
        ],
    )
    def test_plain_answer_starting_with_sse_field_names_is_kept(self, body: bytes):
        """Only a data: line makes a body SSE, so a plain answer that starts like SSE metadata is kept."""
        collector = _SSEAnswerCollector()
        collector.feed(body)

        assert collector.finish() == body.removeprefix(b"\xef\xbb\xbf").decode()

    @pytest.mark.parametrize("chunk_size", [1, 3, 64 * 1024])
    def test_event_line_before_first_data_line_still_types_the_event(self, chunk_size: int):
        raw = (
            b'event: RunContent\ndata: {"content": "a"}\n\n'
            b'event: ToolCallCompleted\ndata: {"content": "noise"}\n\n'
            b'event: RunContent\ndata: {"content": "b"}\n\n'
        )
        collector = _feed_in_chunks(raw, chunk_size)

        assert collector.finish() == "ab"

    def test_oversized_first_tool_event_is_dropped(self):
        """Before the first data: line nothing is skipped, so the first event is bounded by the cap instead."""
        huge = "x" * (MAX_EVENT_BYTES * 3)
        raw = (
            f'event: ToolCallCompleted\ndata: {{"event": "ToolCallCompleted", "content": "{huge}"}}\n\n'
            'event: RunCompleted\ndata: {"content": "ANS"}\n\n'
        ).encode()
        collector = _feed_in_chunks(raw, 64 * 1024)

        assert collector.finish() == "ANS"

    def test_pending_cr_is_cleared_by_a_chunk_without_line_end(self):
        """A CR ending one chunk only pairs with an LF at the very start of the next chunk."""
        collector = _SSEAnswerCollector()
        collector.feed(b"event: RunContent\r")
        collector.feed(b'data: {"content": "x"}')
        collector.feed(b'\n\nevent: RunContent\ndata: {"content": "y"}\n\n')

        assert collector.finish() == "xy"

    def test_cr_in_middle_of_chunk_does_not_swallow_lf_starting_next_chunk(self):
        collector = _SSEAnswerCollector()
        collector.feed(b'event: RunContent\rdata: {"content": "a"}')
        collector.feed(b'\n\nevent: RunContent\ndata: {"content": "b"}\n\n')

        assert collector.finish() == "ab"

    def test_every_data_line_of_a_skipped_event_is_discarded(self):
        collector = _SSEAnswerCollector()
        collector.feed(
            b'event: RunStarted\ndata: {"event": "RunStarted"}\n\n'
            b"event: ToolCallCompleted\n"
            b'data: {"content": "rows"}\n'
            b'data: {"event": "RunContent", "content": "leak"}\n'
            b"\n"
            b'event: RunContent\ndata: {"content": "kept"}\n\n'
        )

        assert collector.finish() == "kept"

    @pytest.mark.parametrize("field", [b": ", b"id: ", b"retry: "])
    def test_oversized_non_data_line_after_sse_starts_is_dropped(self, field: bytes):
        raw = (
            b'data: {"event": "RunStarted"}\n\n'
            + field
            + b"x" * (MAX_EVENT_BYTES + 1)
            + b'\n\ndata: {"event": "RunCompleted", "content": "ok"}\n\n'
        )
        collector = _feed_in_chunks(raw, 64 * 1024)

        assert collector.finish() == "ok"

    def test_streamed_answer_exactly_at_cap_is_returned(self):
        half = "h" * (MAX_EVENT_BYTES // 2)
        collector = _SSEAnswerCollector()
        for _ in range(2):
            collector.feed(f'event: RunContent\ndata: {{"content": "{half}"}}\n\n'.encode())

        assert collector.finish() == half * 2

    def test_streamed_answer_one_byte_over_cap_raises(self):
        half = "h" * (MAX_EVENT_BYTES // 2)
        collector = _SSEAnswerCollector()
        for content in (half, half + "!"):
            collector.feed(f'event: RunContent\ndata: {{"content": "{content}"}}\n\n'.encode())

        with pytest.raises(AnswerTooLargeError):
            collector.finish()

    def test_preamble_only_body_over_cap_raises(self):
        collector = _SSEAnswerCollector()
        collector.feed(b"id: 1\n" * (MAX_EVENT_BYTES // 6 + 10))

        with pytest.raises(AnswerTooLargeError):
            collector.finish()

    @pytest.mark.parametrize(
        "body",
        [
            'event: RunError\ndata: {"content":"boom"}\n\n',
            'data: {"event":"RunError","content":"boom"}\n\n',
            'event: RunContent\ndata: {"content":"partial"}\n\nevent: RunError\ndata: {"content":"boom"}\n\n',
            'event: RunError\rdata: {"content":"boom"}\r\r',
        ],
    )
    def test_run_error_raises_with_agent_reason(self, body: str):
        collector = _feed_in_chunks(body.encode(), 3)

        with pytest.raises(AgentRunError, match="^boom$"):
            collector.finish()

    @pytest.mark.parametrize("chunk_size", [1024, 64 * 1024])
    def test_oversized_run_error_still_fails_the_run(self, chunk_size: int):
        """Regression: a RunError over the size bound was dropped, so the partial draft came back as success."""
        big = "e" * (MAX_EVENT_BYTES + 1)
        raw = (
            'event: RunContent\ndata: {"content":"partial draft"}\n\n'
            f'event: RunError\ndata: {{"content":"{big}"}}\n\n'
        ).encode()
        collector = _feed_in_chunks(raw, chunk_size)

        with pytest.raises(AgentRunError, match="too large to show"):
            collector.finish()

    def test_run_completed_wins_over_run_error(self):
        collector = _SSEAnswerCollector()
        collector.feed(
            b'event: RunError\ndata: {"content":"retrying"}\n\nevent: RunCompleted\ndata: {"content":"final"}\n\n'
        )

        assert collector.finish() == "final"

    def test_run_error_reason_is_capped(self):
        collector = _SSEAnswerCollector()
        collector.feed(f'event: RunError\ndata: {{"content":"{"e" * 5000}"}}\n\n'.encode())

        with pytest.raises(AgentRunError) as exc_info:
            collector.finish()

        assert len(str(exc_info.value)) == 500

    def test_run_error_without_reason_still_raises(self):
        collector = _SSEAnswerCollector()
        collector.feed(b'event: RunError\ndata: {"content":""}\n\n')

        with pytest.raises(AgentRunError):
            collector.finish()

    def test_preamble_then_plain_line_is_returned_whole(self):
        collector = _SSEAnswerCollector()
        collector.feed(b"id: 42\nname: Ada\n")

        assert collector.finish() == "id: 42\nname: Ada\n"

    def test_oversized_preamble_line_raises(self):
        collector = _SSEAnswerCollector()

        with pytest.raises(AnswerTooLargeError):
            collector.feed(b"id: " + b"9" * (MAX_EVENT_BYTES + 1))

    @pytest.mark.parametrize(
        "after",
        [
            "",
            'data: {"event": "RunContent", "content": "draft"}\n\n',
        ],
    )
    def test_oversized_event_typed_only_in_json_is_reported(self, after: str):
        """Without an ``event:`` line an oversized event can't be typed, so it may have been the answer:
        report it rather than return no answer or the draft chunks."""
        big = "z" * (MAX_EVENT_BYTES + 1)
        collector = _SSEAnswerCollector()
        collector.feed((f'data: {{"event": "RunCompleted", "content": "{big}"}}\n\n' + after).encode())

        with pytest.raises(AnswerTooLargeError):
            collector.finish()

    def test_run_completed_before_oversized_untyped_event_is_returned(self):
        big = "z" * (MAX_EVENT_BYTES + 1)
        collector = _SSEAnswerCollector()
        collector.feed(
            b'data: {"event": "RunCompleted", "content": "final"}\n\n'
            + f'data: {{"event": "ToolCallCompleted", "content": "{big}"}}\n\n'.encode()
        )

        assert collector.finish() == "final"

    def test_event_line_after_oversized_data_line_still_types_the_event(self):
        """The type is read when the event ends, so an ``event:`` line after the data still counts."""
        big = "z" * (MAX_EVENT_BYTES + 1)
        collector = _SSEAnswerCollector()
        collector.feed(
            b'event: RunStarted\ndata: {"event": "RunStarted"}\n\n'
            + f'data: {{"content": "{big}"}}\nevent: ToolCallCompleted\n\n'.encode()
            + b'event: RunContent\ndata: {"content": "kept"}\n\n'
        )

        assert collector.finish() == "kept"

    def test_run_completed_after_oversized_untyped_event_is_returned(self):
        big = "z" * (MAX_EVENT_BYTES + 1)
        collector = _SSEAnswerCollector()
        collector.feed(
            f'data: {{"event": "ToolCallCompleted", "content": "{big}"}}\n\n'
            'data: {"event": "RunContent", "content": "draft"}\n\n'
            'data: {"event": "RunCompleted", "content": "final"}\n\n'.encode()
        )

        assert collector.finish() == "final"

    def test_oversized_typed_tool_event_does_not_block_chunk_answer(self):
        """An ``event:`` line naming a non-answer type is trusted, so its size doesn't matter."""
        big = "z" * (MAX_EVENT_BYTES + 1)
        collector = _SSEAnswerCollector()
        collector.feed(
            b'event: RunStarted\ndata: {"event": "RunStarted"}\n\n'
            + f'event: ToolCallCompleted\ndata: {{"content": "{big}"}}\n\n'.encode()
            + b'event: RunContent\ndata: {"content": "kept"}\n\n'
        )

        assert collector.finish() == "kept"

    def test_lone_surrogates_count_toward_answer_limit(self):
        """Each lone surrogate counts 3 bytes, so these chunks pass the bound and are reported."""
        chunk = json.dumps({"content": "\ud83d" * 100_000})
        collector = _SSEAnswerCollector()
        for _ in range(8):
            collector.feed(f"event: RunContent\ndata: {chunk}\n\n".encode())

        with pytest.raises(AnswerTooLargeError):
            collector.finish()

    def test_lone_surrogate_in_streamed_chunk_is_counted(self):
        collector = _SSEAnswerCollector()
        collector.feed(b'event: RunContent\ndata: {"content": "a\\ud83d"}\n\n')

        assert collector.finish() == "a\ud83d"

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
            ({"content": 5}, ""),
            ({"content": ["x"]}, ""),
            ({"content": None, "message": "from message"}, "from message"),
            (b"plain text", "plain text"),
            (_sse('data: {"event": "RunStarted"}').encode(), ""),
            (_sse('data: {"event": "RunCompleted", "content": "sse"}').encode(), "sse"),
            ("plain text", "plain text"),
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
