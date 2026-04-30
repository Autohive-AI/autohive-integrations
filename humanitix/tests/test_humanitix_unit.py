"""
Unit tests for the Humanitix integration.

Uses mocked context.fetch to test all actions without making real API calls.
"""

import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

os.chdir(_parent)
_spec = importlib.util.spec_from_file_location("humanitix_mod", os.path.join(_parent, "humanitix.py"))
_mod = importlib.util.module_from_spec(_spec)
# Register as "humanitix" so that actions/*.py can `from humanitix import humanitix`
sys.modules["humanitix"] = _mod
_spec.loader.exec_module(_mod)
sys.modules["humanitix_mod"] = _mod

humanitix = _mod.humanitix

pytestmark = pytest.mark.unit

API_BASE = "https://api.humanitix.com/v1"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"credentials": {"api_key": "test_api_key_123"}}  # nosec B105
    return ctx


# ---- get_events ----


class TestGetEvents:
    async def test_list_events(self, mock_context):
        mock_context.fetch.return_value = {
            "events": [{"_id": "evt_001", "name": "Tech Conference"}],
            "total": 1,
            "page": 1,
            "pageSize": 100,
        }

        result = await humanitix.execute_action("get_events", {}, mock_context)

        assert result.type != ResultType.ERROR
        data = result.result.data
        assert data["result"] is True
        assert len(data["events"]) == 1
        assert data["events"][0]["_id"] == "evt_001"
        assert data["total"] == 1

    async def test_list_events_url_and_auth(self, mock_context):
        mock_context.fetch.return_value = {"events": [], "total": 0, "page": 1, "pageSize": 100}

        await humanitix.execute_action("get_events", {}, mock_context)

        call = mock_context.fetch.call_args
        assert f"{API_BASE}/events" in call.args[0]
        assert call.kwargs["headers"]["x-api-key"] == "test_api_key_123"  # nosec B105

    async def test_single_event_by_id(self, mock_context):
        mock_context.fetch.return_value = {"_id": "evt_001", "name": "Tech Conference", "status": "active"}

        result = await humanitix.execute_action("get_events", {"event_id": "evt_001"}, mock_context)

        data = result.result.data
        assert data["result"] is True
        assert data["event"]["_id"] == "evt_001"
        assert data["event"]["name"] == "Tech Conference"
        call_url = mock_context.fetch.call_args.args[0]
        assert "events/evt_001" in call_url

    async def test_pagination_params(self, mock_context):
        mock_context.fetch.return_value = {"events": [], "total": 50, "page": 2, "pageSize": 10}

        await humanitix.execute_action("get_events", {"page": 2, "page_size": 10}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "page=2" in call_url
        assert "pageSize=10" in call_url

    async def test_override_location(self, mock_context):
        mock_context.fetch.return_value = {"events": [], "total": 0, "page": 1, "pageSize": 100}

        await humanitix.execute_action("get_events", {"override_location": "AU"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "overrideLocation=AU" in call_url

    async def test_since_filter(self, mock_context):
        mock_context.fetch.return_value = {"events": [], "total": 0, "page": 1, "pageSize": 100}

        await humanitix.execute_action("get_events", {"since": "2024-01-01T00:00:00.000Z"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "since=" in call_url

    async def test_api_error_response(self, mock_context):
        mock_context.fetch.return_value = {"statusCode": 401, "error": "Unauthorized", "message": "Invalid API key"}

        result = await humanitix.execute_action("get_events", {}, mock_context)

        data = result.result.data
        assert data["result"] is False
        assert data["statusCode"] == 401
        assert data["error"] == "Unauthorized"

    async def test_single_event_not_found(self, mock_context):
        mock_context.fetch.return_value = {"statusCode": 404, "error": "Not Found", "message": "Event not found"}

        result = await humanitix.execute_action("get_events", {"event_id": "nonexistent"}, mock_context)

        data = result.result.data
        assert data["result"] is False
        assert data["statusCode"] == 404


# ---- get_orders ----


class TestGetOrders:
    async def test_list_orders(self, mock_context):
        mock_context.fetch.return_value = {
            "orders": [{"_id": "ord_001", "buyerFirstName": "John"}],
            "total": 1,
            "page": 1,
            "pageSize": 100,
        }

        result = await humanitix.execute_action("get_orders", {"event_id": "evt_001"}, mock_context)

        data = result.result.data
        assert data["result"] is True
        assert len(data["orders"]) == 1
        assert data["orders"][0]["_id"] == "ord_001"

    async def test_list_orders_url_includes_event_id(self, mock_context):
        mock_context.fetch.return_value = {"orders": [], "total": 0, "page": 1, "pageSize": 100}

        await humanitix.execute_action("get_orders", {"event_id": "evt_001"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "events/evt_001/orders" in call_url

    async def test_single_order_by_id(self, mock_context):
        mock_context.fetch.return_value = {"_id": "ord_001", "buyerFirstName": "John", "totalPaid": 50.0}

        result = await humanitix.execute_action(
            "get_orders", {"event_id": "evt_001", "order_id": "ord_001"}, mock_context
        )

        data = result.result.data
        assert data["result"] is True
        assert data["order"]["_id"] == "ord_001"
        assert data["order"]["totalPaid"] == 50.0
        call_url = mock_context.fetch.call_args.args[0]
        assert "orders/ord_001" in call_url

    async def test_event_date_id_filter(self, mock_context):
        mock_context.fetch.return_value = {"orders": [], "total": 0, "page": 1, "pageSize": 100}

        await humanitix.execute_action("get_orders", {"event_id": "evt_001", "event_date_id": "date_001"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "eventDateId=date_001" in call_url

    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = {"statusCode": 401, "error": "Unauthorized", "message": "Invalid API key"}

        result = await humanitix.execute_action("get_orders", {"event_id": "evt_001"}, mock_context)

        data = result.result.data
        assert data["result"] is False
        assert data["statusCode"] == 401


# ---- get_tickets ----


class TestGetTickets:
    async def test_list_tickets(self, mock_context):
        mock_context.fetch.return_value = {
            "tickets": [{"_id": "tkt_001", "firstName": "Alice", "checkedIn": False}],
            "total": 1,
            "page": 1,
            "pageSize": 100,
        }

        result = await humanitix.execute_action("get_tickets", {"event_id": "evt_001"}, mock_context)

        data = result.result.data
        assert data["result"] is True
        assert len(data["tickets"]) == 1
        assert data["tickets"][0]["firstName"] == "Alice"

    async def test_list_tickets_url_includes_event_id(self, mock_context):
        mock_context.fetch.return_value = {"tickets": [], "total": 0, "page": 1, "pageSize": 100}

        await humanitix.execute_action("get_tickets", {"event_id": "evt_001"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "events/evt_001/tickets" in call_url

    async def test_single_ticket_by_id(self, mock_context):
        mock_context.fetch.return_value = {"_id": "tkt_001", "firstName": "Alice", "checkedIn": False}

        result = await humanitix.execute_action(
            "get_tickets", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        data = result.result.data
        assert data["result"] is True
        assert data["ticket"]["_id"] == "tkt_001"
        assert data["ticket"]["checkedIn"] is False

    async def test_status_filter(self, mock_context):
        mock_context.fetch.return_value = {"tickets": [], "total": 0, "page": 1, "pageSize": 100}

        await humanitix.execute_action("get_tickets", {"event_id": "evt_001", "status": "complete"}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "status=complete" in call_url

    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = {"statusCode": 404, "error": "Not Found", "message": "Ticket not found"}

        result = await humanitix.execute_action(
            "get_tickets", {"event_id": "evt_001", "ticket_id": "nonexistent"}, mock_context
        )

        data = result.result.data
        assert data["result"] is False
        assert data["statusCode"] == 404


# ---- get_tags ----


class TestGetTags:
    async def test_list_tags(self, mock_context):
        mock_context.fetch.return_value = {
            "tags": [{"_id": "tag_001", "name": "Music", "colour": "#FF0000"}],
            "total": 1,
            "page": 1,
            "pageSize": 100,
        }

        result = await humanitix.execute_action("get_tags", {}, mock_context)

        data = result.result.data
        assert data["result"] is True
        assert len(data["tags"]) == 1
        assert data["tags"][0]["name"] == "Music"

    async def test_list_tags_url(self, mock_context):
        mock_context.fetch.return_value = {"tags": [], "total": 0, "page": 1, "pageSize": 100}

        await humanitix.execute_action("get_tags", {}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert f"{API_BASE}/tags" in call_url

    async def test_single_tag_by_id(self, mock_context):
        mock_context.fetch.return_value = {"_id": "tag_001", "name": "Music", "colour": "#FF0000"}

        result = await humanitix.execute_action("get_tags", {"tag_id": "tag_001"}, mock_context)

        data = result.result.data
        assert data["result"] is True
        assert data["tag"]["_id"] == "tag_001"
        assert data["tag"]["name"] == "Music"

    async def test_pagination_params(self, mock_context):
        mock_context.fetch.return_value = {"tags": [], "total": 30, "page": 2, "pageSize": 10}

        await humanitix.execute_action("get_tags", {"page": 2, "page_size": 10}, mock_context)

        call_url = mock_context.fetch.call_args.args[0]
        assert "page=2" in call_url
        assert "pageSize=10" in call_url

    async def test_api_error(self, mock_context):
        mock_context.fetch.return_value = {
            "statusCode": 500,
            "error": "Internal Server Error",
            "message": "Something went wrong",
        }

        result = await humanitix.execute_action("get_tags", {}, mock_context)

        data = result.result.data
        assert data["result"] is False
        assert data["statusCode"] == 500


# ---- check_in ----


class TestCheckIn:
    async def test_check_in_success(self, mock_context):
        mock_context.fetch.return_value = {
            "scanningMessages": [{"header": "Welcome", "message": "<p>Enjoy the event!</p>"}]
        }

        result = await humanitix.execute_action(
            "check_in", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        data = result.result.data
        assert data["result"] is True
        assert len(data["scanningMessages"]) == 1
        assert data["scanningMessages"][0]["header"] == "Welcome"

    async def test_check_in_url_and_method(self, mock_context):
        mock_context.fetch.return_value = {}

        await humanitix.execute_action("check_in", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context)

        call = mock_context.fetch.call_args
        assert "events/evt_001/tickets/tkt_001/check-in" in call.args[0]
        assert call.kwargs["method"] == "POST"

    async def test_check_in_auth_and_content_type(self, mock_context):
        mock_context.fetch.return_value = {}

        await humanitix.execute_action("check_in", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context)

        headers = mock_context.fetch.call_args.kwargs["headers"]
        assert headers["x-api-key"] == "test_api_key_123"  # nosec B105
        assert headers["Content-Type"] == "application/json"

    async def test_check_in_no_scanning_messages(self, mock_context):
        mock_context.fetch.return_value = {}

        result = await humanitix.execute_action(
            "check_in", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        data = result.result.data
        assert data["result"] is True
        assert data["scanningMessages"] == []

    async def test_check_in_with_override_location(self, mock_context):
        mock_context.fetch.return_value = {"scanningMessages": []}

        await humanitix.execute_action(
            "check_in", {"event_id": "evt_001", "ticket_id": "tkt_001", "override_location": "AU"}, mock_context
        )

        call_url = mock_context.fetch.call_args.args[0]
        assert "overrideLocation=AU" in call_url

    async def test_check_in_api_error(self, mock_context):
        mock_context.fetch.return_value = {
            "statusCode": 400,
            "error": "Bad Request",
            "message": "Ticket already checked in",
        }

        result = await humanitix.execute_action(
            "check_in", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        data = result.result.data
        assert data["result"] is False
        assert data["statusCode"] == 400
        assert data["message"] == "Ticket already checked in"


# ---- check_out ----


class TestCheckOut:
    async def test_check_out_success(self, mock_context):
        mock_context.fetch.return_value = {
            "scanningMessages": [{"header": "Goodbye", "message": "<p>Thanks for coming!</p>"}]
        }

        result = await humanitix.execute_action(
            "check_out", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        data = result.result.data
        assert data["result"] is True
        assert len(data["scanningMessages"]) == 1
        assert data["scanningMessages"][0]["header"] == "Goodbye"

    async def test_check_out_url_and_method(self, mock_context):
        mock_context.fetch.return_value = {}

        await humanitix.execute_action("check_out", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context)

        call = mock_context.fetch.call_args
        assert "events/evt_001/tickets/tkt_001/check-out" in call.args[0]
        assert call.kwargs["method"] == "POST"

    async def test_check_out_no_scanning_messages(self, mock_context):
        mock_context.fetch.return_value = {}

        result = await humanitix.execute_action(
            "check_out", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        data = result.result.data
        assert data["result"] is True
        assert data["scanningMessages"] == []

    async def test_check_out_api_error(self, mock_context):
        mock_context.fetch.return_value = {
            "statusCode": 400,
            "error": "Bad Request",
            "message": "Ticket not checked in",
        }

        result = await humanitix.execute_action(
            "check_out", {"event_id": "evt_001", "ticket_id": "tkt_001"}, mock_context
        )

        data = result.result.data
        assert data["result"] is False
        assert data["statusCode"] == 400
        assert data["message"] == "Ticket not checked in"
