import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("powerbi_mod", os.path.join(_parent, "powerbi.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

powerbi = _mod.powerbi

pytestmark = pytest.mark.unit

POWERBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


# ---- Queries ----


class TestExecuteQueries:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"results": [{"tables": [{"rows": [{"Revenue": 1000}]}]}]},
        )

        result = await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert len(result.result.data["results"]) == 1

    @pytest.mark.asyncio
    async def test_request_method_is_post(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_request_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        queries = [{"query": "EVALUATE VALUES(Sales)"}]
        await powerbi.execute_action("execute_queries", {"dataset_id": "ds-1", "queries": queries}, mock_context)

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["queries"] == queries
        assert payload["serializerSettings"]["includeNulls"] is True

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "workspace_id": "ws-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/groups/ws-1/datasets/ds-1/executeQueries"

    @pytest.mark.asyncio
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert mock_context.fetch.call_args.args[0] == f"{POWERBI_API_BASE}/datasets/ds-1/executeQueries"

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})

        result = await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert result.result.data["results"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Query failed")

        result = await powerbi.execute_action(
            "execute_queries",
            {"dataset_id": "ds-1", "queries": [{"query": "EVALUATE VALUES(Sales)"}]},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Query failed" in result.result.message
