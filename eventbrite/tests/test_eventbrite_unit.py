import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest
from unittest.mock import AsyncMock, MagicMock

from autohive_integrations_sdk import FetchResponse, ResultType
from eventbrite.eventbrite import eventbrite

pytestmark = pytest.mark.unit

BASE_URL = "https://www.eventbriteapi.com/v3"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


# ---- User ----


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "1", "name": "Alice"})

        result = await eventbrite.execute_action("get_current_user", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["user"]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("unauthorized")

        result = await eventbrite.execute_action("get_current_user", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "unauthorized" in result.result.message


class TestListOrganizations:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"organizations": [{"id": "1"}], "pagination": {"page_count": 1}})

        result = await eventbrite.execute_action("list_organizations", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["organizations"] == [{"id": "1"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("list_organizations", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Events ----


class TestGetEvent:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "e1", "name": {"text": "My Event"}})

        result = await eventbrite.execute_action("get_event", {"event_id": "e1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["event"]["id"] == "e1"

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("get_event", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert "event_id" in result.result["message"]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("get_event", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListEvents:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"events": [{"id": "e1"}], "pagination": {"page_count": 1}})

        result = await eventbrite.execute_action("list_events", {"organization_id": "org1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["events"] == [{"id": "e1"}]

    @pytest.mark.asyncio
    async def test_missing_organization_id(self, mock_context):
        result = await eventbrite.execute_action("list_events", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert "organization_id" in result.result["message"]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("list_events", {"organization_id": "org1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCreateEvent:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "e1", "name": {"text": "New Event"}})

        inputs = {
            "organization_id": "org1",
            "name": "New Event",
            "start_utc": "2024-12-25T18:00:00Z",
            "end_utc": "2024-12-25T20:00:00Z",
            "timezone": "America/Los_Angeles",
            "currency": "USD",
        }

        result = await eventbrite.execute_action("create_event", inputs, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["event"]["id"] == "e1"

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, mock_context):
        result = await eventbrite.execute_action("create_event", {"organization_id": "org1"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        inputs = {
            "organization_id": "org1",
            "name": "New Event",
            "start_utc": "2024-12-25T18:00:00Z",
            "end_utc": "2024-12-25T20:00:00Z",
            "timezone": "America/Los_Angeles",
            "currency": "USD",
        }

        result = await eventbrite.execute_action("create_event", inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateEvent:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "e1", "name": {"text": "Updated"}})

        result = await eventbrite.execute_action("update_event", {"event_id": "e1", "name": "Updated"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["event"]["id"] == "e1"

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("update_event", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_no_fields_to_update(self, mock_context):
        result = await eventbrite.execute_action("update_event", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "No fields to update" in result.result.message

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("update_event", {"event_id": "e1", "name": "Updated"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteEvent:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await eventbrite.execute_action("delete_event", {"event_id": "e1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("delete_event", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("delete_event", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestPublishEvent:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"published": True})

        result = await eventbrite.execute_action("publish_event", {"event_id": "e1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["published"] is True

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("publish_event", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("publish_event", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUnpublishEvent:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"unpublished": True})

        result = await eventbrite.execute_action("unpublish_event", {"event_id": "e1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["unpublished"] is True

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("unpublish_event", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("unpublish_event", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCancelEvent:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await eventbrite.execute_action("cancel_event", {"event_id": "e1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["canceled"] is True

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("cancel_event", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("cancel_event", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCopyEvent:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "e2"})

        result = await eventbrite.execute_action("copy_event", {"event_id": "e1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["event"]["id"] == "e2"

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("copy_event", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("copy_event", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetEventDescription:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"description": "<p>Hello</p>"})

        result = await eventbrite.execute_action("get_event_description", {"event_id": "e1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["description"] == "<p>Hello</p>"

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("get_event_description", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("get_event_description", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Venues ----


class TestGetVenue:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "v1", "name": "Venue"})

        result = await eventbrite.execute_action("get_venue", {"venue_id": "v1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["venue"]["id"] == "v1"

    @pytest.mark.asyncio
    async def test_missing_venue_id(self, mock_context):
        result = await eventbrite.execute_action("get_venue", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("get_venue", {"venue_id": "v1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListVenues:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"venues": [{"id": "v1"}], "pagination": {}})

        result = await eventbrite.execute_action("list_venues", {"organization_id": "org1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["venues"] == [{"id": "v1"}]

    @pytest.mark.asyncio
    async def test_missing_organization_id(self, mock_context):
        result = await eventbrite.execute_action("list_venues", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("list_venues", {"organization_id": "org1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCreateVenue:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "v1", "name": "New Venue"})

        result = await eventbrite.execute_action(
            "create_venue", {"organization_id": "org1", "name": "New Venue"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["venue"]["id"] == "v1"

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, mock_context):
        result = await eventbrite.execute_action("create_venue", {"organization_id": "org1"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action(
            "create_venue", {"organization_id": "org1", "name": "New Venue"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Orders ----


class TestGetOrder:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "o1"})

        result = await eventbrite.execute_action("get_order", {"order_id": "o1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["order"]["id"] == "o1"

    @pytest.mark.asyncio
    async def test_missing_order_id(self, mock_context):
        result = await eventbrite.execute_action("get_order", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("get_order", {"order_id": "o1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListOrdersByEvent:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"orders": [{"id": "o1"}], "pagination": {}})

        result = await eventbrite.execute_action("list_orders_by_event", {"event_id": "e1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["orders"] == [{"id": "o1"}]

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("list_orders_by_event", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("list_orders_by_event", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListOrdersByOrganization:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"orders": [{"id": "o1"}], "pagination": {}})

        result = await eventbrite.execute_action(
            "list_orders_by_organization", {"organization_id": "org1"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["orders"] == [{"id": "o1"}]

    @pytest.mark.asyncio
    async def test_missing_organization_id(self, mock_context):
        result = await eventbrite.execute_action("list_orders_by_organization", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action(
            "list_orders_by_organization", {"organization_id": "org1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Attendees ----


class TestGetAttendee:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "a1"})

        result = await eventbrite.execute_action("get_attendee", {"event_id": "e1", "attendee_id": "a1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["attendee"]["id"] == "a1"

    @pytest.mark.asyncio
    async def test_missing_ids(self, mock_context):
        result = await eventbrite.execute_action("get_attendee", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("get_attendee", {"event_id": "e1", "attendee_id": "a1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListAttendees:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"attendees": [{"id": "a1"}], "pagination": {}})

        result = await eventbrite.execute_action("list_attendees", {"event_id": "e1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["attendees"] == [{"id": "a1"}]

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("list_attendees", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("list_attendees", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Ticket Classes ----


class TestGetTicketClass:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "t1"})

        result = await eventbrite.execute_action(
            "get_ticket_class", {"event_id": "e1", "ticket_class_id": "t1"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["ticket_class"]["id"] == "t1"

    @pytest.mark.asyncio
    async def test_missing_ids(self, mock_context):
        result = await eventbrite.execute_action("get_ticket_class", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action(
            "get_ticket_class", {"event_id": "e1", "ticket_class_id": "t1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestListTicketClasses:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"ticket_classes": [{"id": "t1"}], "pagination": {}})

        result = await eventbrite.execute_action("list_ticket_classes", {"event_id": "e1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["ticket_classes"] == [{"id": "t1"}]

    @pytest.mark.asyncio
    async def test_missing_event_id(self, mock_context):
        result = await eventbrite.execute_action("list_ticket_classes", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("list_ticket_classes", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCreateTicketClass:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "t1"})

        inputs = {"event_id": "e1", "name": "General", "quantity_total": 100}
        result = await eventbrite.execute_action("create_ticket_class", inputs, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["ticket_class"]["id"] == "t1"

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, mock_context):
        result = await eventbrite.execute_action("create_ticket_class", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        inputs = {"event_id": "e1", "name": "General", "quantity_total": 100}
        result = await eventbrite.execute_action("create_ticket_class", inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateTicketClass:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "t1", "name": "Updated"})

        result = await eventbrite.execute_action(
            "update_ticket_class",
            {"event_id": "e1", "ticket_class_id": "t1", "name": "Updated"},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["ticket_class"]["name"] == "Updated"

    @pytest.mark.asyncio
    async def test_missing_ids(self, mock_context):
        result = await eventbrite.execute_action("update_ticket_class", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_no_fields_to_update(self, mock_context):
        result = await eventbrite.execute_action(
            "update_ticket_class", {"event_id": "e1", "ticket_class_id": "t1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "No fields to update" in result.result.message

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action(
            "update_ticket_class",
            {"event_id": "e1", "ticket_class_id": "t1", "name": "Updated"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestDeleteTicketClass:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await eventbrite.execute_action(
            "delete_ticket_class", {"event_id": "e1", "ticket_class_id": "t1"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_missing_ids(self, mock_context):
        result = await eventbrite.execute_action("delete_ticket_class", {"event_id": "e1"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action(
            "delete_ticket_class", {"event_id": "e1", "ticket_class_id": "t1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Categories ----


class TestListCategories:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"categories": [{"id": "c1"}]})

        result = await eventbrite.execute_action("list_categories", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["categories"] == [{"id": "c1"}]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("list_categories", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetCategory:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "c1", "name": "Music"})

        result = await eventbrite.execute_action("get_category", {"category_id": "c1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["category"]["name"] == "Music"

    @pytest.mark.asyncio
    async def test_missing_category_id(self, mock_context):
        result = await eventbrite.execute_action("get_category", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await eventbrite.execute_action("get_category", {"category_id": "c1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
