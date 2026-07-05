import os
import sys
import importlib
import json

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("google_looker_mod", os.path.join(_parent, "google_looker.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

google_looker = _mod.google_looker

pytestmark = pytest.mark.unit

AUTH_RESPONSE = FetchResponse(
    status=200,
    headers={},
    data={"access_token": "mock_token_123", "expires_in": 3600},  # nosec B105
)


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {
            "base_url": "https://test-looker.looker.com",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",  # nosec B105
        },
    }
    return ctx


# ---- List Dashboards ----


class TestListDashboards:
    @pytest.mark.asyncio
    async def test_returns_dashboards(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(
                status=200, headers={}, data=[{"id": "1", "title": "Sales"}, {"id": "2", "title": "Marketing"}]
            ),
        ]

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["dashboards"]) == 2
        assert result.result.data["dashboards"][0]["title"] == "Sales"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, FetchResponse(status=200, headers={}, data=[])]

        await google_looker.execute_action("list_dashboards", {}, mock_context)

        api_call = mock_context.fetch.call_args_list[1]
        assert "/api/4.0/dashboards" in api_call.args[0]
        assert api_call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_passes_fields_param(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, FetchResponse(status=200, headers={}, data=[])]

        await google_looker.execute_action(
            "list_dashboards", {"fields": "id,title", "page": 2, "per_page": 10}, mock_context
        )

        api_call = mock_context.fetch.call_args_list[1]
        assert api_call.kwargs["params"]["fields"] == "id,title"
        assert api_call.kwargs["params"]["page"] == 2
        assert api_call.kwargs["params"]["per_page"] == 10

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, FetchResponse(status=200, headers={}, data=[])]

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["dashboards"] == []

    @pytest.mark.asyncio
    async def test_fetch_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, Exception("Connection refused")]

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    @pytest.mark.asyncio
    async def test_auth_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Invalid credentials")

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_missing_credentials_returns_action_error(self, mock_context):
        mock_context.auth = {"auth_type": "Custom", "credentials": {}}

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "missing required configuration" in result.result.message.lower()


# ---- Get Dashboard ----


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_returns_dashboard(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={"id": "123", "title": "Test Dashboard"}),
        ]

        result = await google_looker.execute_action("get_dashboard", {"dashboard_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["dashboard"]["id"] == "123"
        assert result.result.data["dashboard"]["title"] == "Test Dashboard"

    @pytest.mark.asyncio
    async def test_request_url_contains_id(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, FetchResponse(status=200, headers={}, data={})]

        await google_looker.execute_action("get_dashboard", {"dashboard_id": "abc-123"}, mock_context)

        api_call = mock_context.fetch.call_args_list[1]
        assert "/api/4.0/dashboards/abc-123" in api_call.args[0]

    @pytest.mark.asyncio
    async def test_missing_dashboard_id_validation_error(self, mock_context):
        result = await google_looker.execute_action("get_dashboard", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_fetch_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, Exception("Not found")]

        result = await google_looker.execute_action("get_dashboard", {"dashboard_id": "999"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Not found" in result.result.message


# ---- Execute LookML Query ----


class TestExecuteLookMLQuery:
    @pytest.mark.asyncio
    async def test_returns_query_results(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={"id": "q123"}),
            FetchResponse(status=200, headers={}, data=[{"orders.status": "complete", "orders.count": 42}]),
        ]

        result = await google_looker.execute_action(
            "execute_lookml_query",
            {"model": "sales", "explore": "orders", "dimensions": ["orders.status"], "measures": ["orders.count"]},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        query_data = json.loads(result.result.data["query_results"])
        assert query_data[0]["orders.count"] == 42

    @pytest.mark.asyncio
    async def test_query_payload_uses_view_not_explore(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={"id": "q1"}),
            FetchResponse(status=200, headers={}, data=[]),
        ]

        await google_looker.execute_action(
            "execute_lookml_query",
            {"model": "sales_model", "explore": "orders"},
            mock_context,
        )

        query_call = mock_context.fetch.call_args_list[1]
        payload = query_call.kwargs["json"]
        assert payload["model"] == "sales_model"
        assert payload["view"] == "orders"
        assert "explore" not in payload

    @pytest.mark.asyncio
    async def test_dimensions_and_measures_merged_into_fields(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={"id": "q2"}),
            FetchResponse(status=200, headers={}, data=[]),
        ]

        await google_looker.execute_action(
            "execute_lookml_query",
            {"model": "m", "explore": "e", "dimensions": ["d1", "d2"], "measures": ["m1"]},
            mock_context,
        )

        query_call = mock_context.fetch.call_args_list[1]
        assert query_call.kwargs["json"]["fields"] == ["d1", "d2", "m1"]
        assert "dimensions" not in query_call.kwargs["json"]
        assert "measures" not in query_call.kwargs["json"]

    @pytest.mark.asyncio
    async def test_limit_converted_to_string(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={"id": "q3"}),
            FetchResponse(status=200, headers={}, data=[]),
        ]

        await google_looker.execute_action(
            "execute_lookml_query",
            {"model": "m", "explore": "e", "limit": 100},
            mock_context,
        )

        query_call = mock_context.fetch.call_args_list[1]
        assert query_call.kwargs["json"]["limit"] == "100"
        assert isinstance(query_call.kwargs["json"]["limit"], str)

    @pytest.mark.asyncio
    async def test_no_fields_when_no_dimensions_or_measures(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={"id": "q4"}),
            FetchResponse(status=200, headers={}, data=[]),
        ]

        await google_looker.execute_action("execute_lookml_query", {"model": "m", "explore": "e"}, mock_context)

        query_call = mock_context.fetch.call_args_list[1]
        assert "fields" not in query_call.kwargs["json"]

    @pytest.mark.asyncio
    async def test_missing_model_validation_error(self, mock_context):
        result = await google_looker.execute_action("execute_lookml_query", {"explore": "orders"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_query_creation_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, Exception("Model not found")]

        result = await google_looker.execute_action(
            "execute_lookml_query", {"model": "bad", "explore": "orders"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Model not found" in result.result.message

    @pytest.mark.asyncio
    async def test_no_query_id_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={}),  # no 'id' key
        ]

        result = await google_looker.execute_action(
            "execute_lookml_query", {"model": "m", "explore": "e"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "No query ID" in result.result.message


# ---- List Models ----


class TestListModels:
    @pytest.mark.asyncio
    async def test_returns_models(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data=[{"name": "sales"}, {"name": "marketing"}]),
        ]

        result = await google_looker.execute_action("list_models", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["models"]) == 2

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, FetchResponse(status=200, headers={}, data=[])]

        await google_looker.execute_action("list_models", {}, mock_context)

        api_call = mock_context.fetch.call_args_list[1]
        assert "/api/4.0/lookml_models" in api_call.args[0]
        assert api_call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_fetch_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, Exception("Server error")]

        result = await google_looker.execute_action("list_models", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Get Model ----


class TestGetModel:
    @pytest.mark.asyncio
    async def test_returns_model(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={"name": "sales", "explores": []}),
        ]

        result = await google_looker.execute_action("get_model", {"model_name": "sales"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["model"]["name"] == "sales"

    @pytest.mark.asyncio
    async def test_request_url_contains_model_name(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, FetchResponse(status=200, headers={}, data={})]

        await google_looker.execute_action("get_model", {"model_name": "my_model"}, mock_context)

        api_call = mock_context.fetch.call_args_list[1]
        assert "/api/4.0/lookml_models/my_model" in api_call.args[0]

    @pytest.mark.asyncio
    async def test_missing_model_name_validation_error(self, mock_context):
        result = await google_looker.execute_action("get_model", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_fetch_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, Exception("Model not found")]

        result = await google_looker.execute_action("get_model", {"model_name": "nonexistent"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Model not found" in result.result.message


# ---- Execute SQL Query ----


class TestExecuteSQLQuery:
    @pytest.mark.asyncio
    async def test_returns_slug_and_results(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={"slug": "sql_abc"}),
            FetchResponse(status=200, headers={}, data=[{"col": "val"}]),
        ]

        result = await google_looker.execute_action(
            "execute_sql_query",
            {"sql": "SELECT * FROM orders LIMIT 10", "connection_name": "warehouse"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["slug"] == "sql_abc"
        results = json.loads(result.result.data["query_results"])
        assert results[0]["col"] == "val"

    @pytest.mark.asyncio
    async def test_connection_name_in_payload(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={"slug": "s1"}),
            FetchResponse(status=200, headers={}, data=[]),
        ]

        await google_looker.execute_action(
            "execute_sql_query",
            {"sql": "SELECT 1", "connection_name": "my_db"},
            mock_context,
        )

        sql_call = mock_context.fetch.call_args_list[1]
        assert sql_call.kwargs["json"]["connection_name"] == "my_db"
        assert "model_name" not in sql_call.kwargs["json"]

    @pytest.mark.asyncio
    async def test_model_name_used_when_no_connection(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={"slug": "s2"}),
            FetchResponse(status=200, headers={}, data=[]),
        ]

        await google_looker.execute_action(
            "execute_sql_query",
            {"sql": "SELECT 1", "model_name": "my_model"},
            mock_context,
        )

        sql_call = mock_context.fetch.call_args_list[1]
        assert sql_call.kwargs["json"]["model_name"] == "my_model"
        assert "connection_name" not in sql_call.kwargs["json"]

    @pytest.mark.asyncio
    async def test_no_connection_or_model_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE]

        result = await google_looker.execute_action("execute_sql_query", {"sql": "SELECT 1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "connection_name" in result.result.message or "model_name" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_sql_validation_error(self, mock_context):
        result = await google_looker.execute_action("execute_sql_query", {"connection_name": "db"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_no_slug_returned_action_error(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(status=200, headers={}, data={}),  # no 'slug' key
        ]

        result = await google_looker.execute_action(
            "execute_sql_query",
            {"sql": "SELECT 1", "connection_name": "db"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "No slug" in result.result.message

    @pytest.mark.asyncio
    async def test_fetch_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, Exception("DB connection failed")]

        result = await google_looker.execute_action(
            "execute_sql_query",
            {"sql": "SELECT 1", "connection_name": "db"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "DB connection failed" in result.result.message


# ---- List Connections ----


class TestListConnections:
    @pytest.mark.asyncio
    async def test_returns_connections(self, mock_context):
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            FetchResponse(
                status=200,
                headers={},
                data=[
                    {"name": "warehouse", "dialect_name": "bigquery"},
                    {"name": "analytics", "dialect_name": "postgres"},
                ],
            ),
        ]

        result = await google_looker.execute_action("list_connections", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["connections"]) == 2
        assert result.result.data["connections"][0]["name"] == "warehouse"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, FetchResponse(status=200, headers={}, data=[])]

        await google_looker.execute_action("list_connections", {}, mock_context)

        api_call = mock_context.fetch.call_args_list[1]
        assert "/api/4.0/connections" in api_call.args[0]
        assert api_call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_fetch_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, Exception("Unauthorized")]

        result = await google_looker.execute_action("list_connections", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message
