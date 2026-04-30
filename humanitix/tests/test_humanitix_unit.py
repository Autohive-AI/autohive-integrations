"""
Unit tests for the Humanitix integration.

Uses mocked context.fetch to test all actions without making real API calls.
"""

import os
import sys
import importlib
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_original_cwd = os.getcwd()
os.chdir(_parent)
_spec = importlib.util.spec_from_file_location("humanitix_mod", os.path.join(_parent, "humanitix.py"))
_mod = importlib.util.module_from_spec(_spec)
# Register as "humanitix" so that actions/*.py can `from humanitix import humanitix`
sys.modules["humanitix"] = _mod
_spec.loader.exec_module(_mod)
os.chdir(_original_cwd)
sys.modules["humanitix_mod"] = _mod

humanitix = _mod.humanitix

pytestmark = pytest.mark.unit

API_BASE = "https://api.humanitix.com/v1"


def ok(data: dict) -> FetchResponse:
    return FetchResponse(status=200, headers={}, data=data)


def err(status: int, message: str) -> FetchResponse:
    return FetchResponse(status=status, headers={}, data={"message": message, "statusCode": status})


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"credentials": {"api_key": "test_api_key_123"}}  # nosec B105
    return ctx


# ---- get_events ----


class TestGetEvents:
    async def test_list_events(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"events": [{"_id": "evt_001", "name": "Tech Conference"}], "total": 1, "page": 1, "pageSize": 100}
        )

        result = await humanitix.execute_action("get_events", {}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert len(data["events"]) == 1
        assert data["events"][0]["_id"] == "evt_001"
        assert data["total"] == 1

    async def test_list_events_url_and_auth(self, mock_context):
        mock_context.fetch.return_value = ok({"events": [], "total": 0, "page": 1, "pageSize": 100})

        await humanitix.execute_action("get_events", {}, mock_context)

        call = mock_context.fetch.call_args
        assert f"{API_BASE}/events" in call.args[0]
        assert call.kwargs["headers"]["x-api-key"] == "test_api_key_123"  # nosec B105

    async def test_single_event_by_id(self, mock_context):
        mock_context.fetch.return_value = ok({"_id": "evt_001", "name": "Tech Conference", "status": "active"})

        result = await humanitix.execute_action("get_events", {"event_id": "evt_001"}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert data["event"]["_id"] == "evt_001"
        call_url = mock_context.fetch.call_args.args[0]
        assert "events/evt_001" in call_url

    async def test_pagination_params(self, mock_context):
        mock_context.fetch.return_value = ok({"events": [], "total": 50, "page": 2, "pageSize": 10})

        await humanitix.execute_action("get_events", {"page": 2, "page_size": 10}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "page=2" in call_url
        assert "pageSize=10" in call_url

    async def test_override_location(self, mock_context):
        mock_context.fetch.return_value = ok({"events": [], "total": 0, "page": 1, "pageSize": 100})

        await humanitix.execute_action("get_events", {"override_location": "AU"}, mock_context)

        assert "overrideLocation=AU" in mock_context.fetch.call_args.args[0]

    async def test_since_filter(self, mock_context):
        mock_context.fetch.return_value = ok({"events": [], "total": 0, "page": 1, "pageSize": 100})

        await humanitix.execute_action("get_events", {"since": "2024-01-01T00:00:00.000Z"}, mock_context)

        assert "since=" in mock_context.fetch.call_args.args[0]

    async def test_api_error_response(self, mock_context):
        mock_context.fetch.return_value = err(401, "Invalid API key")

        result = await humanitix.execute_action("get_events", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid API key" in result.result.message

    async def test_single_event_not_found(self, mock_context):
        mock_context.fetch.return_value = err(404, "Event not found")

        result = await humanitix.execute_action("get_events", {"event_id": "nonexistent"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Event not found" in result.result.message


# ---- get_orders ----


class TestGetOrders:
    async def test_list_orders(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"orders": [{"_id": "ord_001", "buyerFirstName": "John"}], "total": 1, "page": 1, "pageSize": 100}
        )

        result = await humanitix.execute_action("get_orders", {"event_id": "evt_001"}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert data["orders"][0]["_id"] == "ord_001"

    async def test_list_orders_url_includes_event_id(self, mock_context):
        mock_context.fetch.return_value = ok({"orders": [], "total": 0, "page": 1, "pageSize": 100})

        await humanitix.execute_action("get_orders", {"event_id": "evt_001"}, mock_context)

        assert "events/evt_001/orders" in mock_context.fetch.call_args.args[0]

    async def test_single_order_by_id(self, mock_context):
        mock_context.fetch.return_value = ok({"_id": "ord_001", "buyerFirstName": "John", "totalPaid": 50.0})

        result = await humanitix.execute_action(
            "get_orders", {"event_id": "evt_001", "order_id": "ord_001"}, mock_context
        )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["order"]["_id"] == "ord_001"
        assert "orders/ord_001" in mock_context.fetch.call_args.args[0]

    async def test_event_date_id_filter(self, mock_context):
        mock_context.fetch.return_value = ok({"orders": [], "total": 0, "page": 1, "pageSize": 100})

        await humanitix.execute_action("get_orders", {"event_id": "evt_001", "event_date_id": "date_001"}, mock_context)

        assert "eventDateId=date_001" in mock_context.fetch.call_args.args[0]

    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = err(401, "Invalid API key")

        result = await humanitix.execute_action("get_orders", {"event_id": "evt_001"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- get_tickets ----


class TestGetTickets:
    async def test_list_tickets(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "tickets": [{"_id": "tkt_001", "firstName": "Alice", "checkedIn": False}],
                "total": 1,
                "page": 1,
                "pageSize": 100,
            }
        )

        result = await humanitix.execute_action("get_tickets", {"event_id": "evt_001"}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert data["tickets"][0]["firstName"] == "Alice"

    async def test_list_tickets_url_includes_event_id(self, mock_context):
        mock_context.fetch.return_value = ok({"tickets": [], "total": 0, "page": 1, "pageSize": 100})

        await humanitix.execute_action("get_tickets", {"event_id": "evt_001"}, mock_context)

        assert "events/evt_001/tickets" in mock_context.fetch.call_args.args[0]

    async def test_single_ticket_by_id(self, mock_context):
        mock_context.fetch.return_value = ok({"_id": "tkt_001", "firstName": "Alice", "checkedIn": False})

        result = await humanitix.execute_action(
            "get_tickets", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["ticket"]["_id"] == "tkt_001"

    async def test_status_filter(self, mock_context):
        mock_context.fetch.return_value = ok({"tickets": [], "total": 0, "page": 1, "pageSize": 100})

        await humanitix.execute_action("get_tickets", {"event_id": "evt_001", "status": "complete"}, mock_context)

        assert "status=complete" in mock_context.fetch.call_args.args[0]

    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = err(404, "Ticket not found")

        result = await humanitix.execute_action(
            "get_tickets", {"event_id": "evt_001", "ticket_id": "nonexistent"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_tags ----


class TestGetTags:
    async def test_list_tags(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"tags": [{"_id": "tag_001", "name": "Music", "colour": "#FF0000"}], "total": 1, "page": 1, "pageSize": 100}
        )

        result = await humanitix.execute_action("get_tags", {}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert data["tags"][0]["name"] == "Music"

    async def test_list_tags_url(self, mock_context):
        mock_context.fetch.return_value = ok({"tags": [], "total": 0, "page": 1, "pageSize": 100})

        await humanitix.execute_action("get_tags", {}, mock_context)

        assert f"{API_BASE}/tags" in mock_context.fetch.call_args.args[0]

    async def test_single_tag_by_id(self, mock_context):
        mock_context.fetch.return_value = ok({"_id": "tag_001", "name": "Music", "colour": "#FF0000"})

        result = await humanitix.execute_action("get_tags", {"tag_id": "tag_001"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["tag"]["name"] == "Music"

    async def test_pagination_params(self, mock_context):
        mock_context.fetch.return_value = ok({"tags": [], "total": 30, "page": 2, "pageSize": 10})

        await humanitix.execute_action("get_tags", {"page": 2, "page_size": 10}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "page=2" in call_url
        assert "pageSize=10" in call_url

    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = err(500, "Something went wrong")

        result = await humanitix.execute_action("get_tags", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- check_in ----


class TestCheckIn:
    async def test_check_in_success(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"scanningMessages": [{"header": "Welcome", "message": "<p>Enjoy the event!</p>"}]}
        )

        result = await humanitix.execute_action(
            "check_in", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert data["scanningMessages"][0]["header"] == "Welcome"

    async def test_check_in_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({})

        await humanitix.execute_action("check_in", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context)

        call = mock_context.fetch.call_args
        assert "events/evt_001/tickets/tkt_001/check-in" in call.args[0]
        assert call.kwargs["method"] == "POST"

    async def test_check_in_auth_header(self, mock_context):
        mock_context.fetch.return_value = ok({})

        await humanitix.execute_action("check_in", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context)

        headers = mock_context.fetch.call_args.kwargs["headers"]
        assert headers["x-api-key"] == "test_api_key_123"  # nosec B105
        assert headers["Content-Type"] == "application/json"

    async def test_check_in_no_scanning_messages(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await humanitix.execute_action(
            "check_in", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        assert result.result.data["scanningMessages"] == []

    async def test_check_in_api_error(self, mock_context):
        mock_context.fetch.return_value = err(400, "Ticket already checked in")

        result = await humanitix.execute_action(
            "check_in", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Ticket already checked in" in result.result.message


# ---- check_out ----


class TestCheckOut:
    async def test_check_out_success(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"scanningMessages": [{"header": "Goodbye", "message": "<p>Thanks for coming!</p>"}]}
        )

        result = await humanitix.execute_action(
            "check_out", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["scanningMessages"][0]["header"] == "Goodbye"

    async def test_check_out_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({})

        await humanitix.execute_action("check_out", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context)

        call = mock_context.fetch.call_args
        assert "events/evt_001/tickets/tkt_001/check-out" in call.args[0]
        assert call.kwargs["method"] == "POST"

    async def test_check_out_no_scanning_messages(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await humanitix.execute_action(
            "check_out", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        assert result.result.data["scanningMessages"] == []

    async def test_check_out_api_error(self, mock_context):
        mock_context.fetch.return_value = err(400, "Ticket not checked in")

        result = await humanitix.execute_action(
            "check_out", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Ticket not checked in" in result.result.message
