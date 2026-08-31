import importlib
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("google_looker_mod", os.path.join(_parent, "google_looker.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

google_looker = _mod.google_looker

pytestmark = pytest.mark.unit

TEST_CLIENT_ID = "test_client_id"
TEST_CLIENT_SECRET = "test_client_secret"  # nosec B105
TEST_ACCESS_TOKEN = "mock_token_123"  # nosec B105

AUTH_RESPONSE = FetchResponse(
    status=200,
    headers={},
    data={"access_token": TEST_ACCESS_TOKEN, "expires_in": 3600},
)


@pytest.fixture
def mock_context():
    context = MagicMock(name="ExecutionContext")
    context.fetch = AsyncMock(name="fetch")
    context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "base_url": "https://test-looker.looker.com",
            "client_id": TEST_CLIENT_ID,
            "client_secret": TEST_CLIENT_SECRET,
        },
    }
    return context


def fetch_response(data):
    return FetchResponse(status=200, headers={}, data=data)


def assert_action_error(result, message=None):
    assert result.type == ResultType.ACTION_ERROR
    if message:
        assert message in result.result.message


def test_action_input_schemas_avoid_unsupported_top_level_combinators():
    with open(os.path.join(_parent, "config.json"), encoding="utf-8") as config_file:
        config = json.load(config_file)

    unsupported = {"oneOf", "allOf", "anyOf"}
    for action_name, action in config["actions"].items():
        found = unsupported.intersection(action["input_schema"])
        assert not found, f"{action_name} uses unsupported top-level schema combinators: {sorted(found)}"


class TestAuthentication:
    @pytest.mark.asyncio
    async def test_uses_form_login_and_looker_token_scheme(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response([])]

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert result.type == ResultType.ACTION
        login_call, api_call = mock_context.fetch.call_args_list
        assert login_call.args[0] == "https://test-looker.looker.com/api/4.0/login"
        assert login_call.kwargs == {
            "method": "POST",
            "data": {"client_id": TEST_CLIENT_ID, "client_secret": TEST_CLIENT_SECRET},
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        }
        assert api_call.kwargs["headers"] == {"Authorization": "token mock_token_123"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "base_url",
        [
            "http://test-looker.looker.com",
            "https://user:pass@test-looker.looker.com",
            "https://test-looker.looker.com/path",
            "https://test-looker.looker.com?query=true",
        ],
    )
    async def test_rejects_unsafe_base_urls(self, mock_context, base_url):
        mock_context.auth["credentials"]["base_url"] = base_url

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert_action_error(result, "base_url must be an HTTPS origin")
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_normalizes_trailing_slash(self, mock_context):
        mock_context.auth["credentials"]["base_url"] = "https://test-looker.looker.com/"
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response([])]

        await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert mock_context.fetch.call_args_list[0].args[0] == "https://test-looker.looker.com/api/4.0/login"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "auth_data, message",
        [
            ({"expires_in": 3600}, "valid access_token"),
            ({"access_token": TEST_ACCESS_TOKEN, "expires_in": "never"}, "invalid expires_in"),
            ({"access_token": TEST_ACCESS_TOKEN, "expires_in": 0}, "invalid expires_in"),
        ],
    )
    async def test_rejects_invalid_login_responses(self, mock_context, auth_data, message):
        mock_context.fetch.return_value = fetch_response(auth_data)

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert_action_error(result, message)

    @pytest.mark.asyncio
    async def test_missing_credentials_returns_validation_error(self, mock_context):
        mock_context.auth = {"auth_type": "Custom", "credentials": {}}

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert result.result["source"] == "auth"


class TestListDashboards:
    @pytest.mark.asyncio
    async def test_returns_dashboards(self, mock_context):
        dashboards = [{"id": "1", "title": "Sales"}, {"id": "2", "title": "Marketing"}]
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response(dashboards)]

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["dashboards"] == dashboards

    @pytest.mark.asyncio
    async def test_only_sends_supported_fields_parameter(self, mock_context):
        dashboards = [{"id": str(index)} for index in range(25)]
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response(dashboards)]

        result = await google_looker.execute_action(
            "list_dashboards",
            {"fields": "id,title"},
            mock_context,
        )

        api_call = mock_context.fetch.call_args_list[1]
        assert api_call.args[0].endswith("/api/4.0/dashboards")
        assert api_call.kwargs["method"] == "GET"
        assert api_call.kwargs["params"] == {"fields": "id,title"}
        assert result.result.data["dashboards"] == dashboards

    @pytest.mark.asyncio
    async def test_rejects_malformed_provider_response(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response({"value": []})]

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert_action_error(result, "expected an array of objects")

    @pytest.mark.asyncio
    async def test_fetch_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, Exception("Connection refused")]

        result = await google_looker.execute_action("list_dashboards", {}, mock_context)

        assert_action_error(result, "Connection refused")


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_returns_dashboard_and_encodes_id(self, mock_context):
        dashboard = {"id": "folder/dashboard", "title": "Test Dashboard"}
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response(dashboard)]

        result = await google_looker.execute_action(
            "get_dashboard",
            {"dashboard_id": "folder/dashboard", "fields": "id,title"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["dashboard"] == dashboard
        api_call = mock_context.fetch.call_args_list[1]
        assert api_call.args[0].endswith("/api/4.0/dashboards/folder%2Fdashboard")
        assert api_call.kwargs["params"] == {"fields": "id,title"}

    @pytest.mark.asyncio
    async def test_missing_dashboard_id_validation_error(self, mock_context):
        result = await google_looker.execute_action("get_dashboard", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_rejects_malformed_provider_response(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response([])]

        result = await google_looker.execute_action("get_dashboard", {"dashboard_id": "123"}, mock_context)

        assert_action_error(result, "expected an object")


class TestExecuteLookMLQuery:
    @pytest.mark.asyncio
    async def test_executes_inline_query_with_supported_parameters(self, mock_context):
        query_rows = [{"orders.count": 7}]
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response(query_rows)]

        result = await google_looker.execute_action(
            "execute_lookml_query",
            {
                "model": "commerce",
                "explore": "orders",
                "dimensions": ["orders.status"],
                "measures": ["orders.count"],
                "filters": {"orders.status": "complete"},
                "sorts": ["orders.count desc"],
                "limit": 10,
                "result_format": "json",
                "apply_formatting": False,
                "apply_vis": True,
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert json.loads(result.result.data["query_results"]) == query_rows
        api_call = mock_context.fetch.call_args_list[1]
        assert api_call.args[0].endswith("/api/4.0/queries/run/json")
        assert api_call.kwargs["method"] == "POST"
        assert api_call.kwargs["json"] == {
            "model": "commerce",
            "view": "orders",
            "fields": ["orders.status", "orders.count"],
            "filters": {"orders.status": "complete"},
            "sorts": ["orders.count desc"],
            "limit": "10",
        }
        assert api_call.kwargs["params"] == {"apply_formatting": "false", "apply_vis": "true"}

    @pytest.mark.asyncio
    async def test_returns_text_format_without_json_encoding(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response("status,count\ncomplete,7")]

        result = await google_looker.execute_action(
            "execute_lookml_query",
            {"model": "commerce", "explore": "orders", "result_format": "csv"},
            mock_context,
        )

        assert result.result.data["query_results"] == "status,count\ncomplete,7"

    @pytest.mark.asyncio
    async def test_omits_empty_optional_query_fields(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response([])]

        await google_looker.execute_action(
            "execute_lookml_query",
            {"model": "commerce", "explore": "orders", "dimensions": [], "measures": []},
            mock_context,
        )

        assert mock_context.fetch.call_args_list[1].kwargs["json"] == {"model": "commerce", "view": "orders"}

    @pytest.mark.asyncio
    async def test_missing_model_validation_error(self, mock_context):
        result = await google_looker.execute_action("execute_lookml_query", {"explore": "orders"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_rejects_non_text_non_json_result(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response(b"binary")]

        result = await google_looker.execute_action(
            "execute_lookml_query",
            {"model": "commerce", "explore": "orders"},
            mock_context,
        )

        assert_action_error(result, "expected text or JSON")


class TestListModels:
    @pytest.mark.asyncio
    async def test_returns_models_and_passes_supported_options(self, mock_context):
        models = [{"name": "commerce"}]
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response(models)]

        result = await google_looker.execute_action(
            "list_models",
            {
                "fields": "name,explores",
                "limit": 25,
                "offset": 5,
                "exclude_empty": True,
                "exclude_hidden": False,
                "include_internal": True,
                "include_self_service": False,
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["models"] == models
        api_call = mock_context.fetch.call_args_list[1]
        assert api_call.args[0].endswith("/api/4.0/lookml_models")
        assert api_call.kwargs["params"] == {
            "fields": "name,explores",
            "limit": 25,
            "offset": 5,
            "exclude_empty": "true",
            "exclude_hidden": "false",
            "include_internal": "true",
            "include_self_service": "false",
        }

    @pytest.mark.asyncio
    async def test_rejects_malformed_provider_response(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response({})]

        result = await google_looker.execute_action("list_models", {}, mock_context)

        assert_action_error(result, "expected an array of objects")

    @pytest.mark.asyncio
    async def test_fetch_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, Exception("Server error")]

        result = await google_looker.execute_action("list_models", {}, mock_context)

        assert_action_error(result, "Server error")


class TestGetModel:
    @pytest.mark.asyncio
    async def test_returns_model_and_encodes_name(self, mock_context):
        model = {"name": "sales/model"}
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response(model)]

        result = await google_looker.execute_action(
            "get_model",
            {"model_name": "sales/model", "fields": "name,explores"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["model"] == model
        api_call = mock_context.fetch.call_args_list[1]
        assert api_call.args[0].endswith("/api/4.0/lookml_models/sales%2Fmodel")
        assert api_call.kwargs["params"] == {"fields": "name,explores"}

    @pytest.mark.asyncio
    async def test_missing_model_name_validation_error(self, mock_context):
        result = await google_looker.execute_action("get_model", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_rejects_malformed_provider_response(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response([])]

        result = await google_looker.execute_action("get_model", {"model_name": "commerce"}, mock_context)

        assert_action_error(result, "expected an object")


class TestExecuteSQLQuery:
    @pytest.mark.asyncio
    async def test_executes_connection_query_and_returns_results(self, mock_context):
        rows = [{"answer": 1}]
        mock_context.fetch.side_effect = [
            AUTH_RESPONSE,
            fetch_response({"slug": "sql/abc?"}),
            fetch_response(rows),
        ]

        result = await google_looker.execute_action(
            "execute_sql_query",
            {
                "sql": "SELECT 1 AS answer",
                "connection_name": "warehouse",
                "vis_config": {"type": "table"},
                "result_format": "json",
                "download": "false",
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data == {"slug": "sql/abc?", "query_results": json.dumps(rows)}
        create_call = mock_context.fetch.call_args_list[1]
        assert create_call.args[0].endswith("/api/4.0/sql_queries")
        assert create_call.kwargs["json"] == {
            "sql": "SELECT 1 AS answer",
            "connection_name": "warehouse",
            "vis_config": {"type": "table"},
        }
        run_call = mock_context.fetch.call_args_list[2]
        assert run_call.args[0].endswith("/api/4.0/sql_queries/sql%2Fabc%3F/run/json")
        assert run_call.kwargs["params"] == {"download": "false"}

    @pytest.mark.asyncio
    async def test_uses_model_name_as_connection_selector(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response({"slug": "abc"}), fetch_response("[]")]

        await google_looker.execute_action(
            "execute_sql_query",
            {"sql": "SELECT 1", "model_name": "commerce"},
            mock_context,
        )

        assert mock_context.fetch.call_args_list[1].kwargs["json"] == {
            "sql": "SELECT 1",
            "model_name": "commerce",
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "inputs",
        [
            {"sql": "SELECT 1"},
            {"sql": "SELECT 1", "connection_name": "warehouse", "model_name": "commerce"},
        ],
    )
    async def test_requires_exactly_one_connection_selector(self, mock_context, inputs):
        result = await google_looker.execute_action("execute_sql_query", inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "exactly one" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_sql_validation_error(self, mock_context):
        result = await google_looker.execute_action(
            "execute_sql_query",
            {"connection_name": "warehouse"},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_rejects_missing_slug(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response({})]

        result = await google_looker.execute_action(
            "execute_sql_query",
            {"sql": "SELECT 1", "connection_name": "warehouse"},
            mock_context,
        )

        assert_action_error(result, "valid slug")

    @pytest.mark.asyncio
    async def test_rejects_non_text_non_json_result(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response({"slug": "abc"}), fetch_response(b"binary")]

        result = await google_looker.execute_action(
            "execute_sql_query",
            {"sql": "SELECT 1", "connection_name": "warehouse"},
            mock_context,
        )

        assert_action_error(result, "expected text or JSON")


class TestListConnections:
    @pytest.mark.asyncio
    async def test_returns_connections_and_passes_fields(self, mock_context):
        connections = [{"name": "warehouse", "dialect": {"label": "PostgreSQL"}}]
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response(connections)]

        result = await google_looker.execute_action(
            "list_connections",
            {"fields": "name,dialect"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["connections"] == connections
        api_call = mock_context.fetch.call_args_list[1]
        assert api_call.args[0].endswith("/api/4.0/connections")
        assert api_call.kwargs["params"] == {"fields": "name,dialect"}

    @pytest.mark.asyncio
    async def test_rejects_malformed_provider_response(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, fetch_response(None)]

        result = await google_looker.execute_action("list_connections", {}, mock_context)

        assert_action_error(result, "expected an array of objects")

    @pytest.mark.asyncio
    async def test_fetch_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = [AUTH_RESPONSE, Exception("Unauthorized")]

        result = await google_looker.execute_action("list_connections", {}, mock_context)

        assert_action_error(result, "Unauthorized")
