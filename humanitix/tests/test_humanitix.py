"""
Tests for Humanitix Integration

Tests all 6 actions with mocked API responses to verify correct behavior
without making actual Humanitix API calls.
"""

from typing import Any

import pytest

from context import humanitix

pytestmark = pytest.mark.asyncio


class MockExecutionContext:
    """
    Mock execution context that simulates Humanitix API responses.

    Routes requests based on URL patterns and HTTP methods to return
    pre-configured responses for testing.
    """

    def __init__(self, responses: dict[str, Any]):
        self.auth = {
            "credentials": {
                "api_key": "test_api_key_123"
            }
        }
        self._responses = responses
        self._requests = []

    async def fetch(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs
    ):
        self._requests.append({
            "url": url,
            "method": method,
            "params": params,
            "data": data,
            "headers": headers
        })

        if "/check-out" in url and method == "POST":
            return self._responses.get("POST /check-out", {})

        if "/check-in" in url and method == "POST":
            return self._responses.get("POST /check-in", {})

        if "/tickets/" in url and method == "GET":
            return self._responses.get("GET /ticket", {})

        if "/tickets" in url and method == "GET":
            return self._responses.get("GET /tickets", {"tickets": [], "total": 0, "page": 1, "pageSize": 100})

        if "/orders/" in url and method == "GET":
            return self._responses.get("GET /order", {})

        if "/orders" in url and method == "GET":
            return self._responses.get("GET /orders", {"orders": [], "total": 0, "page": 1, "pageSize": 100})

        if "/events/" in url and method == "GET":
            return self._responses.get("GET /event", {})

        if "/events" in url and method == "GET":
            return self._responses.get("GET /events", {"events": [], "total": 0, "page": 1, "pageSize": 100})

        if "/tags/" in url and method == "GET":
            return self._responses.get("GET /tag", {})

        if "/tags" in url and method == "GET":
            return self._responses.get("GET /tags", {"tags": [], "total": 0, "page": 1, "pageSize": 100})

        return {}


# =============================================================================
# GET EVENTS TESTS
# =============================================================================

async def test_get_events_list():
    """Test listing events returns correct structure."""
    responses = {
        "GET /events": {
            "events": [
                {"_id": "evt_001", "name": "Tech Conference 2025", "status": "active"},
                {"_id": "evt_002", "name": "Music Festival", "status": "draft"}
            ],
            "total": 2,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_events", {}, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["events"]) == 2
    assert data["events"][0]["_id"] == "evt_001"
    assert data["events"][0]["name"] == "Tech Conference 2025"
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["pageSize"] == 100


async def test_get_events_empty():
    """Test listing events when no events exist."""
    responses = {
        "GET /events": {
            "events": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_events", {}, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["events"]) == 0
    assert data["total"] == 0


async def test_get_events_single_by_id():
    """Test fetching a single event by ID."""
    responses = {
        "GET /event": {
            "_id": "evt_001",
            "name": "Tech Conference 2025",
            "status": "active",
            "location": "Sydney"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_events", {
        "event_id": "evt_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["event"]["_id"] == "evt_001"
    assert data["event"]["name"] == "Tech Conference 2025"
    assert data["event"]["location"] == "Sydney"


async def test_get_events_with_pagination():
    """Test listing events with pagination parameters."""
    responses = {
        "GET /events": {
            "events": [
                {"_id": "evt_003", "name": "Workshop"}
            ],
            "total": 50,
            "page": 2,
            "pageSize": 10
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_events", {
        "page": 2,
        "page_size": 10
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["events"]) == 1
    assert data["page"] == 2
    assert data["pageSize"] == 10
    assert data["total"] == 50


async def test_get_events_with_since():
    """Test listing events filtered by since date."""
    responses = {
        "GET /events": {
            "events": [
                {"_id": "evt_005", "name": "Recent Event"}
            ],
            "total": 1,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_events", {
        "since": "2024-06-01T00:00:00.000Z"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["events"]) == 1
    assert data["events"][0]["name"] == "Recent Event"

    req = context._requests[0]
    assert "since=2024-06-01T00%3A00%3A00.000Z" in req["url"]


async def test_get_events_with_override_location():
    """Test listing events with override location."""
    responses = {
        "GET /events": {
            "events": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_events", {
        "override_location": "AU"
    }, context)
    data = result.result.data

    assert data["result"] is True
    req = context._requests[0]
    assert "overrideLocation=AU" in req["url"]


async def test_get_events_single_with_override_location():
    """Test fetching a single event with override location."""
    responses = {
        "GET /event": {
            "_id": "evt_001",
            "name": "Aussie Event"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_events", {
        "event_id": "evt_001",
        "override_location": "AU"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["event"]["_id"] == "evt_001"
    req = context._requests[0]
    assert "overrideLocation=AU" in req["url"]


async def test_get_events_api_error():
    """Test listing events when API returns an error."""
    responses = {
        "GET /events": {
            "statusCode": 401,
            "error": "Unauthorized",
            "message": "Invalid API key"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_events", {}, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 401
    assert data["error"] == "Unauthorized"
    assert data["message"] == "Invalid API key"


async def test_get_events_single_api_error():
    """Test fetching single event when API returns an error."""
    responses = {
        "GET /event": {
            "statusCode": 404,
            "error": "Not Found",
            "message": "Event not found"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_events", {
        "event_id": "nonexistent"
    }, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 404
    assert data["error"] == "Not Found"


async def test_get_events_auth_header():
    """Test that the API key is sent in the x-api-key header."""
    responses = {
        "GET /events": {
            "events": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    await humanitix.execute_action("get_events", {}, context)

    req = context._requests[0]
    assert req["headers"]["x-api-key"] == "test_api_key_123"
    assert req["headers"]["Accept"] == "application/json"


# =============================================================================
# GET ORDERS TESTS
# =============================================================================

async def test_get_orders_list():
    """Test listing orders for an event."""
    responses = {
        "GET /orders": {
            "orders": [
                {"_id": "ord_001", "buyerFirstName": "John", "buyerLastName": "Doe", "totalPaid": 50.00},
                {"_id": "ord_002", "buyerFirstName": "Jane", "buyerLastName": "Smith", "totalPaid": 75.00}
            ],
            "total": 2,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_orders", {
        "event_id": "evt_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["orders"]) == 2
    assert data["orders"][0]["_id"] == "ord_001"
    assert data["orders"][0]["buyerFirstName"] == "John"
    assert data["total"] == 2


async def test_get_orders_empty():
    """Test listing orders when no orders exist."""
    responses = {
        "GET /orders": {
            "orders": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_orders", {
        "event_id": "evt_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["orders"]) == 0
    assert data["total"] == 0


async def test_get_orders_single_by_id():
    """Test fetching a single order by ID."""
    responses = {
        "GET /order": {
            "_id": "ord_001",
            "buyerFirstName": "John",
            "buyerLastName": "Doe",
            "totalPaid": 50.00,
            "tickets": [{"_id": "tkt_001"}]
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_orders", {
        "event_id": "evt_001",
        "order_id": "ord_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["order"]["_id"] == "ord_001"
    assert data["order"]["buyerFirstName"] == "John"
    assert data["order"]["totalPaid"] == 50.00


async def test_get_orders_with_pagination():
    """Test listing orders with pagination."""
    responses = {
        "GET /orders": {
            "orders": [
                {"_id": "ord_010", "buyerFirstName": "Alice"}
            ],
            "total": 25,
            "page": 3,
            "pageSize": 5
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_orders", {
        "event_id": "evt_001",
        "page": 3,
        "page_size": 5
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["page"] == 3
    assert data["pageSize"] == 5
    assert data["total"] == 25


async def test_get_orders_with_event_date_id():
    """Test listing orders filtered by event date ID."""
    responses = {
        "GET /orders": {
            "orders": [
                {"_id": "ord_020", "buyerFirstName": "Bob"}
            ],
            "total": 1,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_orders", {
        "event_id": "evt_001",
        "event_date_id": "date_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    req = context._requests[0]
    assert "eventDateId=date_001" in req["url"]


async def test_get_orders_single_with_event_date_id():
    """Test fetching a single order with event date ID filter."""
    responses = {
        "GET /order": {
            "_id": "ord_001",
            "buyerFirstName": "John"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_orders", {
        "event_id": "evt_001",
        "order_id": "ord_001",
        "event_date_id": "date_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["order"]["_id"] == "ord_001"
    req = context._requests[0]
    assert "eventDateId=date_001" in req["url"]


async def test_get_orders_with_override_location():
    """Test listing orders with override location."""
    responses = {
        "GET /orders": {
            "orders": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_orders", {
        "event_id": "evt_001",
        "override_location": "NZ"
    }, context)
    data = result.result.data

    assert data["result"] is True
    req = context._requests[0]
    assert "overrideLocation=NZ" in req["url"]


async def test_get_orders_with_since():
    """Test listing orders filtered by since date."""
    responses = {
        "GET /orders": {
            "orders": [
                {"_id": "ord_030", "buyerFirstName": "Charlie"}
            ],
            "total": 1,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_orders", {
        "event_id": "evt_001",
        "since": "2024-01-01T00:00:00.000Z"
    }, context)
    data = result.result.data

    assert data["result"] is True
    req = context._requests[0]
    assert "since=" in req["url"]


async def test_get_orders_api_error():
    """Test listing orders when API returns an error."""
    responses = {
        "GET /orders": {
            "statusCode": 401,
            "error": "Unauthorized",
            "message": "Invalid API key"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_orders", {
        "event_id": "evt_001"
    }, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 401
    assert data["error"] == "Unauthorized"


async def test_get_orders_single_api_error():
    """Test fetching single order when API returns an error."""
    responses = {
        "GET /order": {
            "statusCode": 404,
            "error": "Not Found",
            "message": "Order not found"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_orders", {
        "event_id": "evt_001",
        "order_id": "nonexistent"
    }, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 404


async def test_get_orders_url_structure():
    """Test that orders URL includes the event_id."""
    responses = {
        "GET /orders": {
            "orders": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    await humanitix.execute_action("get_orders", {
        "event_id": "evt_001"
    }, context)

    req = context._requests[0]
    assert "events/evt_001/orders" in req["url"]


# =============================================================================
# GET TICKETS TESTS
# =============================================================================

async def test_get_tickets_list():
    """Test listing tickets for an event."""
    responses = {
        "GET /tickets": {
            "tickets": [
                {"_id": "tkt_001", "firstName": "John", "lastName": "Doe", "ticketTypeName": "General Admission"},
                {"_id": "tkt_002", "firstName": "Jane", "lastName": "Smith", "ticketTypeName": "VIP"}
            ],
            "total": 2,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tickets", {
        "event_id": "evt_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["tickets"]) == 2
    assert data["tickets"][0]["_id"] == "tkt_001"
    assert data["tickets"][0]["firstName"] == "John"
    assert data["tickets"][1]["ticketTypeName"] == "VIP"
    assert data["total"] == 2


async def test_get_tickets_empty():
    """Test listing tickets when no tickets exist."""
    responses = {
        "GET /tickets": {
            "tickets": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tickets", {
        "event_id": "evt_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["tickets"]) == 0
    assert data["total"] == 0


async def test_get_tickets_single_by_id():
    """Test fetching a single ticket by ID."""
    responses = {
        "GET /ticket": {
            "_id": "tkt_001",
            "firstName": "John",
            "lastName": "Doe",
            "ticketTypeName": "General Admission",
            "checkedIn": False
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tickets", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["ticket"]["_id"] == "tkt_001"
    assert data["ticket"]["firstName"] == "John"
    assert data["ticket"]["checkedIn"] is False


async def test_get_tickets_with_pagination():
    """Test listing tickets with pagination."""
    responses = {
        "GET /tickets": {
            "tickets": [
                {"_id": "tkt_010", "firstName": "Alice"}
            ],
            "total": 100,
            "page": 5,
            "pageSize": 20
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tickets", {
        "event_id": "evt_001",
        "page": 5,
        "page_size": 20
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["page"] == 5
    assert data["pageSize"] == 20
    assert data["total"] == 100


async def test_get_tickets_with_status_filter():
    """Test listing tickets filtered by status."""
    responses = {
        "GET /tickets": {
            "tickets": [
                {"_id": "tkt_020", "firstName": "Bob", "status": "complete"}
            ],
            "total": 1,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tickets", {
        "event_id": "evt_001",
        "status": "complete"
    }, context)
    data = result.result.data

    assert data["result"] is True
    req = context._requests[0]
    assert "status=complete" in req["url"]


async def test_get_tickets_with_event_date_id():
    """Test listing tickets filtered by event date ID."""
    responses = {
        "GET /tickets": {
            "tickets": [
                {"_id": "tkt_030", "firstName": "Carol"}
            ],
            "total": 1,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tickets", {
        "event_id": "evt_001",
        "event_date_id": "date_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    req = context._requests[0]
    assert "eventDateId=date_001" in req["url"]


async def test_get_tickets_with_since():
    """Test listing tickets filtered by since date."""
    responses = {
        "GET /tickets": {
            "tickets": [
                {"_id": "tkt_040", "firstName": "Dave"}
            ],
            "total": 1,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tickets", {
        "event_id": "evt_001",
        "since": "2024-06-01T00:00:00.000Z"
    }, context)
    data = result.result.data

    assert data["result"] is True
    req = context._requests[0]
    assert "since=" in req["url"]


async def test_get_tickets_with_override_location():
    """Test listing tickets with override location."""
    responses = {
        "GET /tickets": {
            "tickets": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tickets", {
        "event_id": "evt_001",
        "override_location": "US"
    }, context)
    data = result.result.data

    assert data["result"] is True
    req = context._requests[0]
    assert "overrideLocation=US" in req["url"]


async def test_get_tickets_single_api_error():
    """Test fetching single ticket when API returns an error."""
    responses = {
        "GET /ticket": {
            "statusCode": 404,
            "error": "Not Found",
            "message": "Ticket not found"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tickets", {
        "event_id": "evt_001",
        "ticket_id": "nonexistent"
    }, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 404
    assert data["error"] == "Not Found"


async def test_get_tickets_url_structure():
    """Test that tickets URL includes the event_id."""
    responses = {
        "GET /tickets": {
            "tickets": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    await humanitix.execute_action("get_tickets", {
        "event_id": "evt_001"
    }, context)

    req = context._requests[0]
    assert "events/evt_001/tickets" in req["url"]


# =============================================================================
# GET TAGS TESTS
# =============================================================================

async def test_get_tags_list():
    """Test listing tags."""
    responses = {
        "GET /tags": {
            "tags": [
                {"_id": "tag_001", "name": "Music", "colour": "#FF0000"},
                {"_id": "tag_002", "name": "Technology", "colour": "#00FF00"}
            ],
            "total": 2,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tags", {}, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["tags"]) == 2
    assert data["tags"][0]["_id"] == "tag_001"
    assert data["tags"][0]["name"] == "Music"
    assert data["total"] == 2


async def test_get_tags_empty():
    """Test listing tags when no tags exist."""
    responses = {
        "GET /tags": {
            "tags": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tags", {}, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["tags"]) == 0
    assert data["total"] == 0


async def test_get_tags_single_by_id():
    """Test fetching a single tag by ID."""
    responses = {
        "GET /tag": {
            "_id": "tag_001",
            "name": "Music",
            "colour": "#FF0000"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tags", {
        "tag_id": "tag_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["tag"]["_id"] == "tag_001"
    assert data["tag"]["name"] == "Music"
    assert data["tag"]["colour"] == "#FF0000"


async def test_get_tags_with_pagination():
    """Test listing tags with pagination."""
    responses = {
        "GET /tags": {
            "tags": [
                {"_id": "tag_010", "name": "Sports"}
            ],
            "total": 30,
            "page": 2,
            "pageSize": 10
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tags", {
        "page": 2,
        "page_size": 10
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["page"] == 2
    assert data["pageSize"] == 10
    assert data["total"] == 30


async def test_get_tags_single_api_error():
    """Test fetching single tag when API returns an error."""
    responses = {
        "GET /tag": {
            "statusCode": 404,
            "error": "Not Found",
            "message": "Tag not found"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tags", {
        "tag_id": "nonexistent"
    }, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 404
    assert data["error"] == "Not Found"


async def test_get_tags_api_error():
    """Test listing tags when API returns an error."""
    responses = {
        "GET /tags": {
            "statusCode": 500,
            "error": "Internal Server Error",
            "message": "Something went wrong"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("get_tags", {}, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 500
    assert data["error"] == "Internal Server Error"


async def test_get_tags_url_structure():
    """Test that tags URL is correct."""
    responses = {
        "GET /tags": {
            "tags": [],
            "total": 0,
            "page": 1,
            "pageSize": 100
        }
    }
    context = MockExecutionContext(responses)
    await humanitix.execute_action("get_tags", {}, context)

    req = context._requests[0]
    assert "/v1/tags" in req["url"]


# =============================================================================
# CHECK IN TESTS
# =============================================================================

async def test_check_in_success():
    """Test successfully checking in a ticket."""
    responses = {
        "POST /check-in": {
            "scanningMessages": [
                {"header": "Welcome", "message": "<p>Enjoy the event!</p>"}
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("check_in", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["scanningMessages"]) == 1
    assert data["scanningMessages"][0]["header"] == "Welcome"
    assert data["scanningMessages"][0]["message"] == "<p>Enjoy the event!</p>"


async def test_check_in_no_scanning_messages():
    """Test check-in when no scanning messages are configured."""
    responses = {
        "POST /check-in": {}
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("check_in", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["scanningMessages"] == []


async def test_check_in_with_override_location():
    """Test check-in with override location."""
    responses = {
        "POST /check-in": {
            "scanningMessages": []
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("check_in", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001",
        "override_location": "AU"
    }, context)
    data = result.result.data

    assert data["result"] is True
    req = context._requests[0]
    assert "overrideLocation=AU" in req["url"]


async def test_check_in_api_error():
    """Test check-in when API returns an error."""
    responses = {
        "POST /check-in": {
            "statusCode": 400,
            "error": "Bad Request",
            "message": "Ticket already checked in"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("check_in", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 400
    assert data["error"] == "Bad Request"
    assert data["message"] == "Ticket already checked in"


async def test_check_in_unauthorized():
    """Test check-in with invalid API key."""
    responses = {
        "POST /check-in": {
            "statusCode": 401,
            "error": "Unauthorized",
            "message": "Invalid API key"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("check_in", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 401
    assert data["error"] == "Unauthorized"


async def test_check_in_url_structure():
    """Test that check-in URL includes event_id and ticket_id."""
    responses = {
        "POST /check-in": {}
    }
    context = MockExecutionContext(responses)
    await humanitix.execute_action("check_in", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)

    req = context._requests[0]
    assert "events/evt_001/tickets/tkt_001/check-in" in req["url"]
    assert req["method"] == "POST"


async def test_check_in_headers():
    """Test that check-in sends correct headers."""
    responses = {
        "POST /check-in": {}
    }
    context = MockExecutionContext(responses)
    await humanitix.execute_action("check_in", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)

    req = context._requests[0]
    assert req["headers"]["x-api-key"] == "test_api_key_123"
    assert req["headers"]["Content-Type"] == "application/json"


# =============================================================================
# CHECK OUT TESTS
# =============================================================================

async def test_check_out_success():
    """Test successfully checking out a ticket."""
    responses = {
        "POST /check-out": {
            "scanningMessages": [
                {"header": "Goodbye", "message": "<p>Thanks for coming!</p>"}
            ]
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("check_out", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert len(data["scanningMessages"]) == 1
    assert data["scanningMessages"][0]["header"] == "Goodbye"
    assert data["scanningMessages"][0]["message"] == "<p>Thanks for coming!</p>"


async def test_check_out_no_scanning_messages():
    """Test check-out when no scanning messages are configured."""
    responses = {
        "POST /check-out": {}
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("check_out", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)
    data = result.result.data

    assert data["result"] is True
    assert data["scanningMessages"] == []


async def test_check_out_with_override_location():
    """Test check-out with override location."""
    responses = {
        "POST /check-out": {
            "scanningMessages": []
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("check_out", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001",
        "override_location": "NZ"
    }, context)
    data = result.result.data

    assert data["result"] is True
    req = context._requests[0]
    assert "overrideLocation=NZ" in req["url"]


async def test_check_out_api_error():
    """Test check-out when API returns an error."""
    responses = {
        "POST /check-out": {
            "statusCode": 400,
            "error": "Bad Request",
            "message": "Ticket not checked in"
        }
    }
    context = MockExecutionContext(responses)
    result = await humanitix.execute_action("check_out", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)
    data = result.result.data

    assert data["result"] is False
    assert data["statusCode"] == 400
    assert data["error"] == "Bad Request"
    assert data["message"] == "Ticket not checked in"


async def test_check_out_url_structure():
    """Test that check-out URL includes event_id and ticket_id."""
    responses = {
        "POST /check-out": {}
    }
    context = MockExecutionContext(responses)
    await humanitix.execute_action("check_out", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)

    req = context._requests[0]
    assert "events/evt_001/tickets/tkt_001/check-out" in req["url"]
    assert req["method"] == "POST"


async def test_check_out_headers():
    """Test that check-out sends correct headers."""
    responses = {
        "POST /check-out": {}
    }
    context = MockExecutionContext(responses)
    await humanitix.execute_action("check_out", {
        "event_id": "evt_001",
        "ticket_id": "tkt_001"
    }, context)

    req = context._requests[0]
    assert req["headers"]["x-api-key"] == "test_api_key_123"
    assert req["headers"]["Content-Type"] == "application/json"
