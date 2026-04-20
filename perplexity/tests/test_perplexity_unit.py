import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk.integration import ValidationError  # noqa: E402

_spec = importlib.util.spec_from_file_location("perplexity_mod", os.path.join(_parent, "perplexity.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

perplexity = _mod.perplexity
parse_response = _mod.parse_response

pytestmark = pytest.mark.unit

PERPLEXITY_API_URL = "https://api.perplexity.ai/search"

SAMPLE_RESULTS = [
    {
        "title": "AI Breakthroughs 2025",
        "url": "https://example.com/ai-2025",
        "snippet": "Major developments in artificial intelligence...",
        "date": "2025-03-15",
        "last_updated": "2025-03-20",
    },
    {
        "title": "Machine Learning Trends",
        "url": "https://example.com/ml-trends",
        "snippet": "The latest trends in machine learning...",
        "date": "2025-02-10",
        "last_updated": None,
    },
]


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {}
    return ctx


# ---- Helper Function Tests ----


class TestParseResponse:
    @pytest.mark.asyncio
    async def test_dict_response_passthrough(self):
        response = {"results": [], "id": "abc"}
        result = await parse_response(response)
        assert result == {"results": [], "id": "abc"}

    @pytest.mark.asyncio
    async def test_response_with_json_method(self):
        response = MagicMock()
        response.json = AsyncMock(return_value={"results": [{"title": "Test"}]})
        result = await parse_response(response)
        assert result == {"results": [{"title": "Test"}]}

    @pytest.mark.asyncio
    async def test_string_response_passthrough(self):
        result = await parse_response("raw text")
        assert result == "raw text"

    @pytest.mark.asyncio
    async def test_list_response_passthrough(self):
        result = await parse_response([1, 2, 3])
        assert result == [1, 2, 3]


# ---- API Key Handling ----


class TestApiKeyHandling:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {}, clear=True)
    async def test_missing_api_key(self, mock_context):
        os.environ.pop("PERPLEXITY_API_KEY", None)

        result = await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        data = result.result.data
        assert data["results"] == []
        assert data["total_results"] == 0
        assert "PERPLEXITY_API_KEY" in data["error"]
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": ""})
    async def test_empty_api_key(self, mock_context):
        result = await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        data = result.result.data
        assert data["results"] == []
        assert "PERPLEXITY_API_KEY" in data["error"]
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key-123"})  # nosec B105
    async def test_api_key_sent_in_header(self, mock_context):
        mock_context.fetch.return_value = {"results": [], "id": "req-1"}

        await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        call_kwargs = mock_context.fetch.call_args
        headers = call_kwargs.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-key-123"
        assert headers["Content-Type"] == "application/json"


# ---- Search Web Action: Happy Path ----


class TestSearchWebBasic:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_basic_search(self, mock_context):
        mock_context.fetch.return_value = {"results": SAMPLE_RESULTS, "id": "req-123"}

        result = await perplexity.execute_action("search_web", {"query": "AI developments"}, mock_context)

        data = result.result.data
        assert data["total_results"] == 2
        assert len(data["results"]) == 2
        assert data["results"][0]["title"] == "AI Breakthroughs 2025"
        assert data["id"] == "req-123"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = {"results": [], "id": "req-1"}

        await perplexity.execute_action("search_web", {"query": "test query"}, mock_context)

        mock_context.fetch.assert_called_once()
        call_args = mock_context.fetch.call_args
        assert call_args.args[0] == PERPLEXITY_API_URL
        assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_basic_payload(self, mock_context):
        mock_context.fetch.return_value = {"results": [], "id": "req-1"}

        await perplexity.execute_action("search_web", {"query": "quantum computing"}, mock_context)

        call_kwargs = mock_context.fetch.call_args.kwargs
        assert call_kwargs["json"] == {"query": "quantum computing"}

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_cost_usd_set(self, mock_context):
        mock_context.fetch.return_value = {"results": [], "id": "req-1"}

        result = await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        assert result.result.cost_usd == 0.005

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_multi_query_search(self, mock_context):
        mock_context.fetch.return_value = {"results": SAMPLE_RESULTS, "id": "req-multi"}

        queries = ["AI trends", "ML applications", "neural networks"]
        result = await perplexity.execute_action("search_web", {"query": queries}, mock_context)

        call_kwargs = mock_context.fetch.call_args.kwargs
        assert call_kwargs["json"]["query"] == queries
        assert result.result.data["total_results"] == 2

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = {"results": [], "id": "req-empty"}

        result = await perplexity.execute_action("search_web", {"query": "xyznonexistent"}, mock_context)

        data = result.result.data
        assert data["results"] == []
        assert data["total_results"] == 0

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_response_without_results_key(self, mock_context):
        mock_context.fetch.return_value = {"id": "req-no-results"}

        with pytest.raises(ValidationError):
            await perplexity.execute_action("search_web", {"query": "test"}, mock_context)


# ---- Optional Parameters ----


class TestOptionalParameters:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_max_results(self, mock_context):
        mock_context.fetch.return_value = {"results": SAMPLE_RESULTS[:1], "id": "req-1"}

        await perplexity.execute_action("search_web", {"query": "test", "max_results": 5}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["max_results"] == 5

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_content_depth_quick(self, mock_context):
        mock_context.fetch.return_value = {"results": [], "id": "req-1"}

        await perplexity.execute_action("search_web", {"query": "test", "content_depth": "quick"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["max_tokens_per_page"] == 512

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_content_depth_default(self, mock_context):
        mock_context.fetch.return_value = {"results": [], "id": "req-1"}

        await perplexity.execute_action("search_web", {"query": "test", "content_depth": "default"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["max_tokens_per_page"] == 2048

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_content_depth_detailed(self, mock_context):
        mock_context.fetch.return_value = {"results": [], "id": "req-1"}

        await perplexity.execute_action("search_web", {"query": "test", "content_depth": "detailed"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["max_tokens_per_page"] == 8192

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_content_depth_unknown_rejected_by_schema(self, mock_context):
        with pytest.raises(ValidationError):
            await perplexity.execute_action("search_web", {"query": "test", "content_depth": "unknown"}, mock_context)

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_country_filter(self, mock_context):
        mock_context.fetch.return_value = {"results": [], "id": "req-1"}

        await perplexity.execute_action("search_web", {"query": "test", "country": "US"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["country"] == "US"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_empty_country_rejected_by_schema(self, mock_context):
        with pytest.raises(ValidationError):
            await perplexity.execute_action("search_web", {"query": "test", "country": ""}, mock_context)

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_all_params_combined(self, mock_context):
        mock_context.fetch.return_value = {"results": SAMPLE_RESULTS, "id": "req-full"}

        inputs = {"query": "climate change", "max_results": 10, "content_depth": "detailed", "country": "GB"}
        result = await perplexity.execute_action("search_web", inputs, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["query"] == "climate change"
        assert payload["max_results"] == 10
        assert payload["max_tokens_per_page"] == 8192
        assert payload["country"] == "GB"
        assert result.result.data["total_results"] == 2

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_no_optional_params(self, mock_context):
        mock_context.fetch.return_value = {"results": [], "id": "req-1"}

        await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload == {"query": "test"}


# ---- Error Handling ----


class TestErrorHandling:
    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_rate_limit_429(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 429: rate limit exceeded")

        result = await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        data = result.result.data
        assert data["results"] == []
        assert data["total_results"] == 0
        assert "Rate limit exceeded" in data["error"]

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_rate_limit_text_match(self, mock_context):
        mock_context.fetch.side_effect = Exception("Too many requests, rate limit hit")

        result = await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        assert "Rate limit exceeded" in result.result.data["error"]

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_unauthorized_401(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 401: unauthorized")

        result = await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        data = result.result.data
        assert data["results"] == []
        assert "Invalid API key" in data["error"]
        assert "PERPLEXITY_API_KEY" in data["error"]

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_forbidden_403(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 403: forbidden")

        result = await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        data = result.result.data
        assert data["results"] == []
        assert "Access forbidden" in data["error"]
        assert "perplexity.ai/settings/api" in data["error"]

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_generic_exception(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection timeout")

        result = await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        data = result.result.data
        assert data["results"] == []
        assert data["total_results"] == 0
        assert "Failed to search" in data["error"]
        assert "Connection timeout" in data["error"]

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"})  # nosec B105
    async def test_runtime_error(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("Network unreachable")

        result = await perplexity.execute_action("search_web", {"query": "test"}, mock_context)

        data = result.result.data
        assert data["results"] == []
        assert "Failed to search" in data["error"]
