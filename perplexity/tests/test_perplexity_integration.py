"""
End-to-end integration tests for the Perplexity search integration.

These tests call the real Perplexity API and require a valid API key
set in the PERPLEXITY_API_KEY environment variable (via .env or export).

Run with:
    pytest perplexity/tests/test_perplexity_integration.py -m integration

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "perplexity_mod", os.path.join(_parent, "perplexity.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

perplexity = _mod.perplexity

pytestmark = pytest.mark.integration

API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")


@pytest.fixture
def live_context():
    """Execution context that uses a real fetch (via the SDK's context.fetch mock pattern).

    For e2e tests we still use a MagicMock context but with a real async HTTP call
    wired through context.fetch. Since the integration calls context.fetch() directly,
    we need to provide a real async HTTP client.
    """
    if not API_KEY:
        pytest.skip("PERPLEXITY_API_KEY not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers) as resp:
                data = await resp.json()
                return FetchResponse(
                    status=resp.status, headers=dict(resp.headers), data=data
                )

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {}
    return ctx


class TestBasicSearch:
    @pytest.mark.asyncio
    async def test_simple_query_returns_results(self, live_context):
        result = await perplexity.execute_action(
            "search_web", {"query": "Python programming language"}, live_context
        )

        data = result.result.data
        assert "results" in data
        assert data["total_results"] > 0
        assert len(data["results"]) > 0

    @pytest.mark.asyncio
    async def test_result_structure(self, live_context):
        result = await perplexity.execute_action(
            "search_web", {"query": "what is pytest"}, live_context
        )

        data = result.result.data
        first_result = data["results"][0]
        assert "title" in first_result
        assert "url" in first_result
        assert first_result["url"].startswith("http")

    @pytest.mark.asyncio
    async def test_cost_is_set(self, live_context):
        result = await perplexity.execute_action(
            "search_web", {"query": "test"}, live_context
        )

        assert result.result.cost_usd == 0.005


class TestMaxResults:
    @pytest.mark.asyncio
    async def test_respects_max_results(self, live_context):
        result = await perplexity.execute_action(
            "search_web",
            {"query": "artificial intelligence", "max_results": 3},
            live_context,
        )

        data = result.result.data
        assert data["total_results"] <= 3

    @pytest.mark.asyncio
    async def test_single_result(self, live_context):
        result = await perplexity.execute_action(
            "search_web", {"query": "SpaceX launch", "max_results": 1}, live_context
        )

        data = result.result.data
        assert data["total_results"] >= 1
        assert len(data["results"]) >= 1


class TestContentDepth:
    @pytest.mark.asyncio
    async def test_quick_depth(self, live_context):
        result = await perplexity.execute_action(
            "search_web",
            {"query": "climate change", "max_results": 2, "content_depth": "quick"},
            live_context,
        )

        data = result.result.data
        assert data["total_results"] > 0

    @pytest.mark.asyncio
    async def test_detailed_depth(self, live_context):
        result = await perplexity.execute_action(
            "search_web",
            {
                "query": "quantum computing",
                "max_results": 2,
                "content_depth": "detailed",
            },
            live_context,
        )

        data = result.result.data
        assert data["total_results"] > 0


class TestCountryFilter:
    @pytest.mark.asyncio
    async def test_country_filter_us(self, live_context):
        result = await perplexity.execute_action(
            "search_web",
            {"query": "tech companies", "max_results": 5, "country": "US"},
            live_context,
        )

        data = result.result.data
        assert data["total_results"] > 0


class TestMultiQuery:
    @pytest.mark.asyncio
    async def test_multi_query(self, live_context):
        result = await perplexity.execute_action(
            "search_web",
            {"query": ["machine learning", "deep learning"], "max_results": 3},
            live_context,
        )

        data = result.result.data
        assert "results" in data


class TestAllParametersCombined:
    @pytest.mark.asyncio
    async def test_all_params(self, live_context):
        result = await perplexity.execute_action(
            "search_web",
            {
                "query": "renewable energy",
                "max_results": 5,
                "content_depth": "default",
                "country": "GB",
            },
            live_context,
        )

        data = result.result.data
        assert data["total_results"] > 0
        assert len(data["results"]) <= 5
