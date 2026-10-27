"""
Read-only end-to-end tests for the Agno Data Agent integration.

These tests call a real Agno AgentOS deployment (Autohive's Dash) and require
AGNO_AGENT_API_URL and AGNO_AGENT_API_TOKEN (and optionally AGNO_AGENT_AGENT_ID,
default "dash") in .env or the environment. In TeamCity they come from
tests/teamcity.env and AWS SSM.

Every test only asks the agent questions or calls /health; nothing is written.

Run with:
    pytest agno-agent/tests/test_agno_agent_integration.py -m "integration and not destructive"

The default pytest configuration and test_*_integration.py name exclude this
file from CI.
"""

import re
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
import pytest_asyncio
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

from agno_agent import AgnoConnectedAccountHandler, agno_agent

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def live_context(env_credentials):
    api_url = env_credentials("AGNO_AGENT_API_URL")
    api_token = env_credentials("AGNO_AGENT_API_TOKEN")
    if not api_url or not api_token:
        pytest.skip("AGNO_AGENT_API_URL / AGNO_AGENT_API_TOKEN not set — skipping integration tests")

    ctx = MagicMock(name="ExecutionContext")
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "api_url": api_url,
            "api_token": api_token,
            "agent_id": env_credentials("AGNO_AGENT_AGENT_ID") or "dash",
        },
    }

    # ask_agent calls aiohttp itself; context.fetch is only used by the connected-account health check.
    async with aiohttp.ClientSession() as session:

        async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, timeout=None, **kwargs):
            client_timeout = aiohttp.ClientTimeout(total=timeout or 30)
            async with session.request(
                method, url, json=json, headers=headers, params=params, timeout=client_timeout
            ) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    data = await resp.json(content_type=None)
                else:
                    data = await resp.text()
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", data)
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data), data)
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

        ctx.fetch = AsyncMock(side_effect=real_fetch)
        yield ctx


async def _ask(context, query: str):
    return await agno_agent.execute_action("ask_agent", {"query": query}, context)


# ---- Read-Only Tests ----


class TestAskAgent:
    async def test_simple_question_returns_an_answer(self, live_context):
        result = await _ask(live_context, "Reply with the single word pong and nothing else.")

        assert result.type == ResultType.ACTION, result.result
        assert "pong" in result.result.data["response"].lower()

    async def test_warehouse_question_returns_a_number(self, live_context):
        """Runs SQL through the agent's tools, so the stream carries tool events before the answer."""
        result = await _ask(live_context, "How many paid Autohive plans do we have right now? Answer with the number.")

        assert result.type == ResultType.ACTION, result.result
        response = result.result.data["response"]
        assert response != "No response from agent."
        assert re.search(r"\d", response)

    async def test_large_tool_result_is_streamed_not_buffered(self, live_context):
        """Regression for the out-of-memory crash: the SQL result (thousands of rows) streams through
        as one multi-MB tool event that the integration must skip without holding it."""
        result = await _ask(
            live_context,
            "Return every row of autohive_prod.llm_usage for 14 October 2026 (UTC) with no LIMIT, "
            "then tell me how many rows there were.",
        )

        # The agent either answers, or Agno fails the run (the rows can overflow the model's context);
        # both must reach the caller instead of a crash or a bare "No response from agent."
        if result.type == ResultType.ACTION_ERROR:
            assert result.result.message.startswith("The agent could not finish this request: ")
        else:
            assert result.type == ResultType.ACTION, result.result
            assert re.search(r"\d", result.result.data["response"])


class TestAuth:
    async def test_invalid_token_is_rejected(self, live_context):
        live_context.auth["credentials"]["api_token"] = "not-a-valid-token"  # nosec B105

        with pytest.raises(HTTPError) as exc_info:
            await _ask(live_context, "ping")

        assert exc_info.value.status in (401, 403, 429)


class TestConnectedAccount:
    async def test_health_check_returns_account_info(self, live_context):
        credentials = live_context.auth["credentials"]

        info = await AgnoConnectedAccountHandler().get_account_info(live_context)

        assert info.username == f"{credentials['agent_id']} @ {credentials['api_url'].rstrip('/')}"
