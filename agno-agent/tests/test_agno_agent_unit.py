"""Tests for the agno-agent integration (Agno AgentOS API)."""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from autohive_integrations_sdk import ActionError, FetchResponse

# Add integration directory to path so imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _sse(*events: str) -> str:
    """Build an SSE response body from already-encoded ``data: ...`` lines."""
    return "\n\n".join(events) + "\n\n"


def _resp(data: Any, status: int = 200) -> FetchResponse:
    """Wrap a body in a FetchResponse, as SDK 2.0.0's context.fetch returns."""
    return FetchResponse(status=status, headers={}, data=data)


@pytest.mark.unit
class TestAskAgentHandler:
    """Test the ask_agent action handler."""

    @pytest.mark.asyncio
    async def test_ask_agent_returns_run_completed_content(self):
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        sse_body = _sse(
            'data: {"event": "RunStarted"}',
            'data: {"event": "RunResponseContent", "content": "thinking..."}',
            'data: {"event": "RunCompleted", "content": "There are 42 active users, up 15% from last month."}',
        )
        context.fetch = AsyncMock(return_value=_resp(sse_body))

        result = await handler.execute({"query": "How many active users?"}, context)

        context.fetch.assert_called_once_with(
            "https://agno.example.com/agents/my-agent/runs",
            method="POST",
            content_type="application/x-www-form-urlencoded",
            data={"message": "How many active users?", "stream": "true"},
            headers={
                "Accept": "text/event-stream",
                "Authorization": "Bearer test-token",
            },
            timeout=120,
        )
        assert result.data["response"] == "There are 42 active users, up 15% from last month."

    @pytest.mark.asyncio
    async def test_ask_agent_falls_back_to_run_content_chunks(self):
        """Default Agno streaming emits RunContent chunks with no RunCompleted — concatenate them."""
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        sse_body = _sse(
            'data: {"event": "RunStarted"}',
            'data: {"event": "RunContent", "content": "Hello "}',
            'data: {"event": "RunContent", "content": "world."}',
        )
        context.fetch = AsyncMock(return_value=_resp(sse_body))

        result = await handler.execute({"query": "test"}, context)

        assert result.data["response"] == "Hello world."

    @pytest.mark.asyncio
    async def test_ask_agent_falls_back_to_legacy_chunk_names(self):
        """Older Agno deployments stream RunResponseContent — still supported."""
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        sse_body = _sse(
            'data: {"event": "RunResponseContent", "content": "Hello "}',
            'data: {"event": "RunResponseContent", "content": "world."}',
        )
        context.fetch = AsyncMock(return_value=_resp(sse_body))

        result = await handler.execute({"query": "test"}, context)

        assert result.data["response"] == "Hello world."

    @pytest.mark.asyncio
    async def test_ask_agent_parses_agno_wire_format_with_event_lines(self):
        """Agno/AgentOS emits both ``event:`` and ``data:`` lines per SSE block.
        The parser reads the JSON ``event`` field from ``data:``, so the
        ``event:`` line is informational — confirm a real-shape body still parses."""
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        # Real Agno wire format: each block has an `event:` line followed by `data:` JSON.
        sse_body = (
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
        context.fetch = AsyncMock(return_value=_resp(sse_body))

        result = await handler.execute({"query": "test"}, context)

        assert result.data["response"] == "Hello world."

    @pytest.mark.asyncio
    async def test_ask_agent_parses_event_from_sse_event_line_only(self):
        """Canonical SSE: event type on the ``event:`` line, payload carrying only
        ``content``. The parser falls back to the event-line value when the JSON
        has no ``event`` field — without this, the chunks would be silently
        dropped and the action would return "No response from agent."."""
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        sse_body = (
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
        context.fetch = AsyncMock(return_value=_resp(sse_body))

        result = await handler.execute({"query": "test"}, context)

        assert result.data["response"] == "Hello world."

    @pytest.mark.asyncio
    async def test_ask_agent_parses_crlf_framed_sse(self):
        """SSE bodies framed with CRLF (\\r\\n\\r\\n) parse the same as LF."""
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        crlf_body = 'data: {"event": "RunCompleted", "content": "crlf works"}\r\n\r\n'
        context.fetch = AsyncMock(return_value=_resp(crlf_body))

        result = await handler.execute({"query": "test"}, context)

        assert result.data["response"] == "crlf works"

    @pytest.mark.asyncio
    async def test_ask_agent_handles_empty_response(self):
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        context.fetch = AsyncMock(return_value=_resp(_sse('data: {"event": "RunStarted"}')))

        result = await handler.execute({"query": "test"}, context)

        assert result.data["response"] == "No response from agent."

    @pytest.mark.asyncio
    async def test_ask_agent_preserves_plain_text_body(self):
        """A plain (non-SSE) text body is returned as the answer, not discarded."""
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        context.fetch = AsyncMock(return_value=_resp("Plain text response with no SSE framing"))

        result = await handler.execute({"query": "test"}, context)

        assert result.data["response"] == "Plain text response with no SSE framing"

    @pytest.mark.asyncio
    async def test_ask_agent_preserves_non_sse_json_body(self):
        """A non-SSE JSON body falls back to its content/message field rather than being lost."""
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        context.fetch = AsyncMock(return_value=_resp({"content": "There are 42 active users."}))

        result = await handler.execute({"query": "test"}, context)

        assert result.data["response"] == "There are 42 active users."

    @pytest.mark.asyncio
    async def test_ask_agent_strips_trailing_slash_from_url(self):
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com/",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        context.fetch = AsyncMock(return_value=_resp(_sse('data: {"event": "RunCompleted", "content": "ok"}')))

        await handler.execute({"query": "test"}, context)

        call_url = context.fetch.call_args[0][0]
        assert call_url == "https://agno.example.com/agents/my-agent/runs"


@pytest.mark.unit
class TestAskAgentRetry:
    """Test the gateway-retry behavior for ask_agent."""

    @pytest.mark.asyncio
    async def test_retries_on_transient_504_then_succeeds(self):
        from agno_agent import AskAgentHandler
        from autohive_integrations_sdk import HTTPError

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        success_body = _sse('data: {"event": "RunCompleted", "content": "answer"}')
        context.fetch = AsyncMock(
            side_effect=[
                HTTPError(504, "<html>504</html>"),
                HTTPError(504, "<html>504</html>"),
                _resp(success_body),
            ]
        )

        with patch("agno_agent.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            result = await handler.execute({"query": "test"}, context)

        assert result.data["response"] == "answer"
        assert context.fetch.call_count == 3
        # Exponential backoff: 2**0 = 1s, 2**1 = 2s
        sleep_mock.assert_any_await(1)
        sleep_mock.assert_any_await(2)

    @pytest.mark.asyncio
    async def test_retries_on_502_and_503(self):
        from agno_agent import AskAgentHandler
        from autohive_integrations_sdk import HTTPError

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        success_body = _sse('data: {"event": "RunCompleted", "content": "ok"}')
        context.fetch = AsyncMock(
            side_effect=[
                HTTPError(502, "bad gateway"),
                HTTPError(503, "service unavailable"),
                _resp(success_body),
            ]
        )

        with patch("agno_agent.asyncio.sleep", new=AsyncMock()):
            result = await handler.execute({"query": "test"}, context)

        assert result.data["response"] == "ok"
        assert context.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_action_error_after_max_retries(self):
        """After exhausted gateway retries, return ActionError (not raise) so the
        user sees a clean message and error tracking isn't paged for a
        service-availability condition."""
        from agno_agent import AskAgentHandler
        from autohive_integrations_sdk import HTTPError

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        context.fetch = AsyncMock(side_effect=HTTPError(504, "<html>504</html>"))

        with patch("agno_agent.asyncio.sleep", new=AsyncMock()):
            result = await handler.execute({"query": "test"}, context)

        assert isinstance(result, ActionError)
        assert "504" in result.message
        assert "temporarily unavailable" in result.message
        assert context.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_does_not_retry_on_4xx(self):
        from agno_agent import AskAgentHandler
        from autohive_integrations_sdk import HTTPError

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        context.fetch = AsyncMock(side_effect=HTTPError(400, "bad request"))

        with patch("agno_agent.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            with pytest.raises(HTTPError) as exc_info:
                await handler.execute({"query": "test"}, context)

        assert exc_info.value.status == 400
        assert context.fetch.call_count == 1
        sleep_mock.assert_not_awaited()


@pytest.mark.unit
class TestConnectedAccountHandler:
    """Test the connected account handler."""

    @pytest.mark.asyncio
    async def test_get_account_info_calls_health(self):
        from agno_agent import AgnoConnectedAccountHandler

        handler = AgnoConnectedAccountHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        context.fetch = AsyncMock(return_value=_resp({"status": "ok"}))

        result = await handler.get_account_info(context)

        context.fetch.assert_called_once_with(
            "https://agno.example.com/health",
            method="GET",
            headers={"Authorization": "Bearer test-token"},
            timeout=10,
        )
        assert result.username == "my-agent @ https://agno.example.com"

    @pytest.mark.asyncio
    async def test_get_account_info_raises_on_failure(self):
        from agno_agent import AgnoConnectedAccountHandler

        handler = AgnoConnectedAccountHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://bad-url.example.com",
                "api_token": "bad-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }
        context.fetch = AsyncMock(side_effect=Exception("Connection refused"))

        with pytest.raises(Exception, match="Connection refused"):
            await handler.get_account_info(context)

    @pytest.mark.asyncio
    async def test_get_account_info_raises_on_missing_url(self):
        from agno_agent import AgnoConnectedAccountHandler

        handler = AgnoConnectedAccountHandler()
        context = MagicMock()
        context.auth = {"credentials": {}}

        with pytest.raises(Exception, match="api_url"):
            await handler.get_account_info(context)


@pytest.mark.unit
class TestValidation:
    """Test input and credential validation."""

    @pytest.mark.asyncio
    async def test_ask_agent_raises_on_missing_query(self):
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {
            "credentials": {
                "api_url": "https://agno.example.com",
                "api_token": "test-token",  # nosec B105
                "agent_id": "my-agent",
            }
        }

        with pytest.raises(Exception, match="query"):
            await handler.execute({}, context)

    @pytest.mark.asyncio
    async def test_ask_agent_raises_on_missing_credentials(self):
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {"credentials": {}}

        with pytest.raises(Exception, match="api_url"):
            await handler.execute({"query": "test"}, context)

    @pytest.mark.asyncio
    async def test_ask_agent_raises_on_missing_agent_id(self):
        from agno_agent import AskAgentHandler

        handler = AskAgentHandler()
        context = MagicMock()
        context.auth = {"credentials": {"api_url": "https://agno.example.com"}}

        with pytest.raises(Exception, match="agent_id"):
            await handler.execute({"query": "test"}, context)
