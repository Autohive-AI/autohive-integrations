import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "xero_mod", os.path.join(_parent, "xero.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

xero = _mod.xero
XeroRateLimitExceededException = _mod.XeroRateLimitExceededException

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


SAMPLE_PO = {
    "PurchaseOrderID": "po-001",
    "PurchaseOrderNumber": "PO-001",
    "Status": "DRAFT",
    "Contact": {"ContactID": "c-001", "Name": "Supplier"},
    "LineItems": [
        {
            "Description": "Parts",
            "Quantity": 10,
            "UnitAmount": 50.0,
            "LineAmount": 500.0,
        }
    ],
    "Total": 500.0,
}

SAMPLE_PO_RESPONSE = {"PurchaseOrders": [SAMPLE_PO]}


# ---- get_purchase_orders ----


class TestGetPurchaseOrders:
    @pytest.mark.asyncio
    async def test_returns_purchase_orders(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_PO_RESPONSE)

            result = await xero.execute_action(
                "get_purchase_orders", {"tenant_id": "t-001"}, mock_context
            )

        assert "PurchaseOrders" in result.result.data
        assert len(result.result.data["PurchaseOrders"]) == 1

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_PO_RESPONSE)

            await xero.execute_action(
                "get_purchase_orders", {"tenant_id": "t-001"}, mock_context
            )

            call_args = mock_limiter.make_request.call_args
            assert "PurchaseOrders" in call_args.args[1]
            assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_specific_po_by_id(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_PO_RESPONSE)

            await xero.execute_action(
                "get_purchase_orders",
                {"tenant_id": "t-001", "purchase_order_id": "po-001"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "po-001" in call_args.args[1]

    @pytest.mark.asyncio
    async def test_where_and_page_filters(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_PO_RESPONSE)

            await xero.execute_action(
                "get_purchase_orders",
                {"tenant_id": "t-001", "where": 'Status=="AUTHORISED"', "page": 1},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert call_args.kwargs["params"]["where"] == 'Status=="AUTHORISED"'
            assert call_args.kwargs["params"]["page"] == "1"

    @pytest.mark.asyncio
    async def test_rate_limit_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(150, 60, "t-001")
            )

            result = await xero.execute_action(
                "get_purchase_orders", {"tenant_id": "t-001"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "rate limit" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=Exception("Network error")
            )

            result = await xero.execute_action(
                "get_purchase_orders", {"tenant_id": "t-001"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message


# ---- create_purchase_order ----


class TestCreatePurchaseOrder:
    @pytest.mark.asyncio
    async def test_creates_purchase_order(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_PO_RESPONSE)

            result = await xero.execute_action(
                "create_purchase_order",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [
                        {
                            "Description": "Parts",
                            "UnitAmount": 50.0,
                            "AccountCode": "400",
                        }
                    ],
                },
                mock_context,
            )

        assert "PurchaseOrders" in result.result.data

    @pytest.mark.asyncio
    async def test_posts_to_purchase_orders_endpoint(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_PO_RESPONSE)

            await xero.execute_action(
                "create_purchase_order",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [
                        {
                            "Description": "Parts",
                            "UnitAmount": 50.0,
                            "AccountCode": "400",
                        }
                    ],
                },
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "api.xero.com/api.xro/2.0/PurchaseOrders" in call_args.args[1]
            assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_optional_delivery_fields(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_PO_RESPONSE)

            await xero.execute_action(
                "create_purchase_order",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [
                        {
                            "Description": "Parts",
                            "UnitAmount": 50.0,
                            "AccountCode": "400",
                        }
                    ],
                    "delivery_address": "123 Main St",
                    "attention_to": "Jane Doe",
                    "telephone": "+1-555-0000",
                    "delivery_instructions": "Leave at door",
                },
                mock_context,
            )

            payload = mock_limiter.make_request.call_args.kwargs["json"]
            po = payload["PurchaseOrders"][0]
            assert po["DeliveryAddress"] == "123 Main St"
            assert po["AttentionTo"] == "Jane Doe"
            assert po["Telephone"] == "+1-555-0000"
            assert po["DeliveryInstructions"] == "Leave at door"

    @pytest.mark.asyncio
    async def test_rate_limit_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(200, 60, "t-001")
            )

            result = await xero.execute_action(
                "create_purchase_order",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [
                        {"Description": "P", "UnitAmount": 1.0, "AccountCode": "400"}
                    ],
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("API error"))

            result = await xero.execute_action(
                "create_purchase_order",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [
                        {"Description": "P", "UnitAmount": 1.0, "AccountCode": "400"}
                    ],
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- update_purchase_order ----


class TestUpdatePurchaseOrder:
    @pytest.mark.asyncio
    async def test_updates_purchase_order(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "PurchaseOrders": [
                        {"PurchaseOrderID": "po-001", "Status": "AUTHORISED"}
                    ]
                }
            )

            result = await xero.execute_action(
                "update_purchase_order",
                {
                    "tenant_id": "t-001",
                    "purchase_order_id": "po-001",
                    "status": "AUTHORISED",
                },
                mock_context,
            )

        assert "PurchaseOrders" in result.result.data

    @pytest.mark.asyncio
    async def test_posts_to_correct_url(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_PO_RESPONSE)

            await xero.execute_action(
                "update_purchase_order",
                {"tenant_id": "t-001", "purchase_order_id": "po-001"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "po-001" in call_args.args[1]
            assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Error"))

            result = await xero.execute_action(
                "update_purchase_order",
                {"tenant_id": "t-001", "purchase_order_id": "po-001"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- delete_purchase_order ----


class TestDeletePurchaseOrder:
    @pytest.mark.asyncio
    async def test_deletes_purchase_order(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "PurchaseOrders": [
                        {"PurchaseOrderID": "po-001", "Status": "DELETED"}
                    ]
                }
            )

            result = await xero.execute_action(
                "delete_purchase_order",
                {"tenant_id": "t-001", "purchase_order_id": "po-001"},
                mock_context,
            )

        assert result.result.data["PurchaseOrders"][0]["Status"] == "DELETED"

    @pytest.mark.asyncio
    async def test_payload_sets_status_deleted(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_PO_RESPONSE)

            await xero.execute_action(
                "delete_purchase_order",
                {"tenant_id": "t-001", "purchase_order_id": "po-001"},
                mock_context,
            )

            payload = mock_limiter.make_request.call_args.kwargs["json"]
            assert payload["PurchaseOrders"][0]["Status"] == "DELETED"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Error"))

            result = await xero.execute_action(
                "delete_purchase_order",
                {"tenant_id": "t-001", "purchase_order_id": "po-001"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_purchase_order_history ----


class TestGetPurchaseOrderHistory:
    @pytest.mark.asyncio
    async def test_returns_history(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "HistoryRecords": [
                        {"Details": "PO created", "DateUTC": "2024-01-10"}
                    ]
                }
            )

            result = await xero.execute_action(
                "get_purchase_order_history",
                {"tenant_id": "t-001", "purchase_order_id": "po-001"},
                mock_context,
            )

        assert "HistoryRecords" in result.result.data

    @pytest.mark.asyncio
    async def test_calls_history_endpoint(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value={"HistoryRecords": []})

            await xero.execute_action(
                "get_purchase_order_history",
                {"tenant_id": "t-001", "purchase_order_id": "po-001"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "po-001/History" in call_args.args[1]
            assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Error"))

            result = await xero.execute_action(
                "get_purchase_order_history",
                {"tenant_id": "t-001", "purchase_order_id": "po-001"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- add_note_to_purchase_order ----


class TestAddNoteToPurchaseOrder:
    @pytest.mark.asyncio
    async def test_adds_note(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "HistoryRecords": [
                        {"Details": "Test note", "DateUTC": "2024-01-15"}
                    ]
                }
            )

            result = await xero.execute_action(
                "add_note_to_purchase_order",
                {
                    "tenant_id": "t-001",
                    "purchase_order_id": "po-001",
                    "note": "Test note",
                },
                mock_context,
            )

        assert "HistoryRecords" in result.result.data

    @pytest.mark.asyncio
    async def test_calls_history_endpoint_with_put(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value={"HistoryRecords": []})

            await xero.execute_action(
                "add_note_to_purchase_order",
                {
                    "tenant_id": "t-001",
                    "purchase_order_id": "po-001",
                    "note": "My note",
                },
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "po-001/History" in call_args.args[1]
            assert call_args.kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_payload_includes_note(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value={"HistoryRecords": []})

            await xero.execute_action(
                "add_note_to_purchase_order",
                {
                    "tenant_id": "t-001",
                    "purchase_order_id": "po-001",
                    "note": "My note",
                },
                mock_context,
            )

            payload = mock_limiter.make_request.call_args.kwargs["json"]
            assert payload["HistoryRecords"][0]["Details"] == "My note"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Error"))

            result = await xero.execute_action(
                "add_note_to_purchase_order",
                {"tenant_id": "t-001", "purchase_order_id": "po-001", "note": "Note"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
