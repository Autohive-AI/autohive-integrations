import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
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


def _dax_response(rows):
    return FetchResponse(status=200, headers={}, data={"results": [{"tables": [{"rows": rows}]}]})


class TestGetDatasetSchema:
    @pytest.mark.asyncio
    async def test_happy_path_joins_tables_and_columns(self, mock_context):
        mock_context.fetch.side_effect = [
            _dax_response([{"[ID]": "t1", "[Name]": "Sales"}]),
            _dax_response(
                [
                    {"[TableID]": "t1", "[ExplicitName]": "Amount"},
                    {"[TableID]": "t1", "[ExplicitName]": "Region"},
                ]
            ),
        ]

        result = await powerbi.execute_action("get_dataset_schema", {"dataset_id": "ds-1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["columns_available"] is True
        assert data["tables"] == [{"id": "t1", "name": "Sales", "columns": ["Amount", "Region"]}]

    @pytest.mark.asyncio
    async def test_info_tables_failure_returns_clear_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Failed to execute the DAX query.")

        result = await powerbi.execute_action("get_dataset_schema", {"dataset_id": "ds-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "does not support DAX schema introspection" in result.result.message
        assert "clone_report" in result.result.message
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_info_columns_failure_still_returns_tables(self, mock_context):
        mock_context.fetch.side_effect = [
            _dax_response([{"[ID]": "t1", "[Name]": "Sales"}]),
            Exception("Failed to execute the DAX query."),
        ]

        result = await powerbi.execute_action("get_dataset_schema", {"dataset_id": "ds-1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["columns_available"] is False
        assert data["tables"] == [{"id": "t1", "name": "Sales", "columns": []}]

    @pytest.mark.asyncio
    async def test_no_tables_returns_empty_list(self, mock_context):
        mock_context.fetch.side_effect = [_dax_response([]), _dax_response([])]

        result = await powerbi.execute_action("get_dataset_schema", {"dataset_id": "ds-1"}, mock_context)

        assert result.result.data["tables"] == []

    @pytest.mark.asyncio
    async def test_url_with_workspace(self, mock_context):
        mock_context.fetch.side_effect = [_dax_response([]), _dax_response([])]

        await powerbi.execute_action("get_dataset_schema", {"dataset_id": "ds-1", "workspace_id": "ws-1"}, mock_context)

        first_call_url = mock_context.fetch.call_args_list[0].args[0]
        assert first_call_url == f"{POWERBI_API_BASE}/groups/ws-1/datasets/ds-1/executeQueries"

    @pytest.mark.asyncio
    async def test_url_without_workspace(self, mock_context):
        mock_context.fetch.side_effect = [_dax_response([]), _dax_response([])]

        await powerbi.execute_action("get_dataset_schema", {"dataset_id": "ds-1"}, mock_context)

        first_call_url = mock_context.fetch.call_args_list[0].args[0]
        assert first_call_url == f"{POWERBI_API_BASE}/datasets/ds-1/executeQueries"

    @pytest.mark.asyncio
    async def test_first_query_is_info_tables(self, mock_context):
        mock_context.fetch.side_effect = [_dax_response([]), _dax_response([])]

        await powerbi.execute_action("get_dataset_schema", {"dataset_id": "ds-1"}, mock_context)

        first_payload = mock_context.fetch.call_args_list[0].kwargs["json"]
        assert first_payload["queries"] == [{"query": "EVALUATE INFO.TABLES()"}]

    @pytest.mark.asyncio
    async def test_falls_back_to_scanner_when_dax_fails_and_workspace_given(self, mock_context):
        mock_context.fetch.side_effect = [
            Exception("Failed to execute the DAX query."),
            FetchResponse(status=202, headers={}, data={"id": "scan-1"}),
            FetchResponse(status=200, headers={}, data={"status": "Succeeded"}),
            FetchResponse(
                status=200,
                headers={},
                data={
                    "workspaces": [
                        {
                            "datasets": [
                                {
                                    "id": "ds-1",
                                    "tables": [
                                        {
                                            "name": "Sales",
                                            "columns": [{"name": "Amount"}],
                                            "measures": [{"name": "Total Sales"}],
                                        }
                                    ],
                                }
                            ]
                        }
                    ]
                },
            ),
        ]

        result = await powerbi.execute_action(
            "get_dataset_schema", {"dataset_id": "ds-1", "workspace_id": "ws-1"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["tables"] == [{"id": None, "name": "Sales", "columns": ["Amount", "Total Sales"]}]
        assert result.result.data["columns_available"] is True

    @pytest.mark.asyncio
    async def test_scanner_fallback_not_attempted_without_workspace_id(self, mock_context):
        mock_context.fetch.side_effect = Exception("Failed to execute the DAX query.")

        result = await powerbi.execute_action("get_dataset_schema", {"dataset_id": "ds-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 1
        assert "workspace_id" in result.result.message
        assert "clone_report" in result.result.message

    @pytest.mark.asyncio
    async def test_both_dax_and_scanner_fail_returns_combined_error(self, mock_context):
        mock_context.fetch.side_effect = [
            Exception("Failed to execute the DAX query."),
            Exception("AccessDenied: user is not a tenant admin"),
        ]

        result = await powerbi.execute_action(
            "get_dataset_schema", {"dataset_id": "ds-1", "workspace_id": "ws-1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "admin metadata scan fallback also failed" in result.result.message
        assert "clone_report" in result.result.message

    @pytest.mark.asyncio
    async def test_scanner_scan_never_succeeds_raises_after_retries(self, mock_context):
        mock_context.fetch.side_effect = [
            Exception("Failed to execute the DAX query."),
            FetchResponse(status=202, headers={}, data={"id": "scan-1"}),
        ] + [FetchResponse(status=200, headers={}, data={"status": "Running"})] * 10

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await powerbi.execute_action(
                "get_dataset_schema", {"dataset_id": "ds-1", "workspace_id": "ws-1"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "did not complete in time" in result.result.message
