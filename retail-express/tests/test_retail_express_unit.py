import importlib.util
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

_spec = importlib.util.spec_from_file_location("retail_express_mod", os.path.join(_parent, "retail_express.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

retail_express = _mod.retail_express

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    context = MagicMock(name="ExecutionContext")
    context.auth = {"auth_type": "Custom", "credentials": {"api_key": "test-api-key"}}
    context.fetch = AsyncMock(name="fetch")
    return context


class TestListInventoryLevels:
    async def test_returns_inventory_levels_and_pagination(self, mock_context):
        level = {
            "product_id": 101,
            "outlet_id": 7,
            "available": 12,
            "stock_on_hand": 15,
            "allocated": 3,
            "on_order": 4,
        }
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"access_token": "token"}),  # nosec B105
            FetchResponse(
                status=200,
                headers={},
                data={"data": [level], "page_number": 2, "page_size": 50, "total_records": 51},
            ),
        ]

        result = await retail_express.execute_action(
            "list_inventory_levels",
            {"outlet_id": "7", "product_id": "101", "page_number": 2, "page_size": 50},
            mock_context,
        )

        assert result.result.data == {
            "inventory_levels": [level],
            "page_number": 2,
            "page_size": 50,
            "total_records": 51,
            "result": True,
        }
        inventory_call = mock_context.fetch.await_args_list[1]
        assert inventory_call.args[0].endswith("/v2.1/inventory")
        assert inventory_call.kwargs["method"] == "GET"
        assert inventory_call.kwargs["params"] == {
            "page_number": 2,
            "page_size": 50,
            "outlet_id": "7",
            "product_id": "101",
        }

    async def test_passes_incremental_sync_and_filter_parameters(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"access_token": "token"}),  # nosec B105
            FetchResponse(
                status=200,
                headers={},
                data={"data": [], "page_number": 1, "page_size": 20, "total_records": 0},
            ),
        ]
        inputs = {
            "sales_channel_id": "14,3",
            "sku": "SKU-1,SKU-2",
            "modified_since": "2026-01-01T00:00:00+13:00",
            "filter_by": "stock_on_hand:gte:0",
            "order_by": "modified_on desc",
        }

        await retail_express.execute_action("list_inventory_levels", inputs, mock_context)

        params = mock_context.fetch.await_args_list[1].kwargs["params"]
        assert params == inputs

    async def test_treats_nullable_data_as_empty_inventory(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"access_token": "token"}),  # nosec B105
            FetchResponse(
                status=200,
                headers={},
                data={"data": None, "page_number": 1, "page_size": 20, "total_records": 0},
            ),
        ]

        result = await retail_express.execute_action("list_inventory_levels", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {
            "inventory_levels": [],
            "page_number": 1,
            "page_size": 20,
            "total_records": 0,
            "result": True,
        }

    async def test_returns_structured_error(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("inventory unavailable")

        result = await retail_express.execute_action("list_inventory_levels", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "inventory unavailable"


class TestListInventoryMovements:
    async def test_returns_inventory_movements(self, mock_context):
        movement = {
            "id": 9001,
            "movement_type": "Invoice",
            "product": {"id": 101},
            "outlet": {"id": 7},
            "quantity_available": {"before": 12, "delta": -1, "after": 11},
        }
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"access_token": "token"}),  # nosec B105
            FetchResponse(
                status=200,
                headers={},
                data={"data": [movement], "page_number": 1, "page_size": 20, "total_records": 1},
            ),
        ]

        result = await retail_express.execute_action(
            "list_inventory_movements",
            {"plu": "SKU-123", "movement_types": "PO,Invoice"},
            mock_context,
        )

        assert result.result.data["inventory_movements"] == [movement]
        assert result.result.data["total_records"] == 1
        movement_call = mock_context.fetch.await_args_list[1]
        assert movement_call.args[0].endswith("/v2.1/inventorymovementlogs")
        assert movement_call.kwargs["params"] == {"plu": "SKU-123", "movement_types": "PO,Invoice"}

    async def test_passes_reference_filter_order_and_pagination(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"access_token": "token"}),  # nosec B105
            FetchResponse(
                status=200,
                headers={},
                data={"data": [], "page_number": 3, "page_size": 100, "total_records": 0},
            ),
        ]
        inputs = {
            "reference_ids": "1,5,23-00000001",
            "filter_by": "created_on:gte:2026-01-01T00:00:00+13:00",
            "order_by": "created_on desc",
            "page_number": 3,
            "page_size": 100,
        }

        await retail_express.execute_action("list_inventory_movements", inputs, mock_context)

        assert mock_context.fetch.await_args_list[1].kwargs["params"] == inputs

    async def test_treats_nullable_data_as_empty_movements(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"access_token": "token"}),  # nosec B105
            FetchResponse(
                status=200,
                headers={},
                data={"data": None, "page_number": 1, "page_size": 20, "total_records": 0},
            ),
        ]

        result = await retail_express.execute_action("list_inventory_movements", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {
            "inventory_movements": [],
            "page_number": 1,
            "page_size": 20,
            "total_records": 0,
            "result": True,
        }

    async def test_returns_structured_error(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("movement log unavailable")

        result = await retail_express.execute_action("list_inventory_movements", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message == "movement log unavailable"
