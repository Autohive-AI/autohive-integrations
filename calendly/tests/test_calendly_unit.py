"""
Unit tests for the Calendly integration using mocked fetch.

All tests are CI-safe: fetch is mocked, no credentials required. Covers every
action's success path, its ActionError path (fetch raises), and validation
errors for missing required inputs.
"""

import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import calendly as calendly_mod  # noqa: E402

calendly_integration = calendly_mod.calendly

pytestmark = pytest.mark.unit


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def make_ctx(response_data):
    """Context whose fetch returns a single FetchResponse."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data))
    ctx.auth = {}
    return ctx


def make_ctx_error(exc=None):
    """Context whose fetch raises — exercises the ActionError path."""
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=exc or Exception("API request failed"))
    ctx.auth = {}
    return ctx


# =============================================================================
# GET CURRENT USER
# =============================================================================


@pytest.mark.asyncio
async def test_get_current_user_success():
    ctx = make_ctx({"resource": {"uri": "https://api.calendly.com/users/AAA", "name": "Jane Doe"}})
    result = await calendly_integration.execute_action("get_current_user", {}, ctx)
    assert result.result.data["user"]["name"] == "Jane Doe"
    ctx.fetch.assert_called_once()
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert url.endswith("/users/me")


@pytest.mark.asyncio
async def test_get_current_user_falls_back_to_body_when_no_resource():
    ctx = make_ctx({"uri": "https://api.calendly.com/users/AAA", "name": "No Resource Key"})
    result = await calendly_integration.execute_action("get_current_user", {}, ctx)
    assert result.result.data["user"]["name"] == "No Resource Key"


@pytest.mark.asyncio
async def test_get_current_user_error():
    ctx = make_ctx_error(Exception("401 Unauthorized"))
    result = await calendly_integration.execute_action("get_current_user", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "401 Unauthorized" in result.result.message


# =============================================================================
# GET USER
# =============================================================================


@pytest.mark.asyncio
async def test_get_user_success():
    ctx = make_ctx({"resource": {"uri": "https://api.calendly.com/users/BBB", "name": "Bob"}})
    result = await calendly_integration.execute_action("get_user", {"user_uuid": "BBB"}, ctx)
    assert result.result.data["user"]["name"] == "Bob"
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert url.endswith("/users/BBB")


@pytest.mark.asyncio
async def test_get_user_missing_uuid_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("get_user", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_user_error():
    ctx = make_ctx_error(Exception("404 Not Found"))
    result = await calendly_integration.execute_action("get_user", {"user_uuid": "BBB"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "404 Not Found" in result.result.message


# =============================================================================
# LIST EVENT TYPES
# =============================================================================


@pytest.mark.asyncio
async def test_list_event_types_success():
    ctx = make_ctx(
        {
            "collection": [{"uri": "et1", "name": "30 Minute Meeting"}],
            "pagination": {"count": 1, "next_page": None},
        }
    )
    result = await calendly_integration.execute_action("list_event_types", {"count": 10}, ctx)
    data = result.result.data
    assert len(data["event_types"]) == 1
    assert data["event_types"][0]["name"] == "30 Minute Meeting"
    assert data["pagination"]["count"] == 1


@pytest.mark.asyncio
async def test_list_event_types_empty_defaults():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("list_event_types", {}, ctx)
    assert result.result.data["event_types"] == []
    assert result.result.data["pagination"] == {}


@pytest.mark.asyncio
async def test_list_event_types_forwards_params():
    ctx = make_ctx({"collection": []})
    await calendly_integration.execute_action("list_event_types", {"user": "u1", "active": True, "count": 5}, ctx)
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params == {"user": "u1", "active": True, "count": 5}


@pytest.mark.asyncio
async def test_list_event_types_no_params_sends_none():
    ctx = make_ctx({"collection": []})
    await calendly_integration.execute_action("list_event_types", {}, ctx)
    assert ctx.fetch.call_args.kwargs.get("params") is None


@pytest.mark.asyncio
async def test_list_event_types_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("list_event_types", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET EVENT TYPE
# =============================================================================


@pytest.mark.asyncio
async def test_get_event_type_success():
    ctx = make_ctx({"resource": {"uri": "et1", "name": "Intro Call", "duration": 30}})
    result = await calendly_integration.execute_action("get_event_type", {"event_type_uuid": "et1"}, ctx)
    assert result.result.data["event_type"]["duration"] == 30


@pytest.mark.asyncio
async def test_get_event_type_missing_uuid_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("get_event_type", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_event_type_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("get_event_type", {"event_type_uuid": "et1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST SCHEDULED EVENTS
# =============================================================================


@pytest.mark.asyncio
async def test_list_scheduled_events_success():
    ctx = make_ctx(
        {
            "collection": [{"uri": "ev1", "name": "Meeting", "status": "active"}],
            "pagination": {"count": 1},
        }
    )
    result = await calendly_integration.execute_action("list_scheduled_events", {"status": "active"}, ctx)
    data = result.result.data
    assert data["events"][0]["status"] == "active"
    assert data["pagination"]["count"] == 1


@pytest.mark.asyncio
async def test_list_scheduled_events_forwards_params():
    ctx = make_ctx({"collection": []})
    await calendly_integration.execute_action(
        "list_scheduled_events",
        {"organization": "org1", "min_start_time": "2025-01-01T00:00:00Z", "count": 20},
        ctx,
    )
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["organization"] == "org1"
    assert params["min_start_time"] == "2025-01-01T00:00:00Z"
    assert params["count"] == 20


@pytest.mark.asyncio
async def test_list_scheduled_events_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("list_scheduled_events", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET SCHEDULED EVENT
# =============================================================================


@pytest.mark.asyncio
async def test_get_scheduled_event_success():
    ctx = make_ctx({"resource": {"uri": "ev1", "name": "Standup"}})
    result = await calendly_integration.execute_action("get_scheduled_event", {"event_uuid": "ev1"}, ctx)
    assert result.result.data["event"]["name"] == "Standup"


@pytest.mark.asyncio
async def test_get_scheduled_event_missing_uuid_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("get_scheduled_event", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_scheduled_event_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("get_scheduled_event", {"event_uuid": "ev1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CANCEL SCHEDULED EVENT
# =============================================================================


@pytest.mark.asyncio
async def test_cancel_scheduled_event_success():
    ctx = make_ctx({"resource": {"canceled_by": "Host"}})
    result = await calendly_integration.execute_action(
        "cancel_scheduled_event", {"event_uuid": "ev1", "reason": "Conflict"}, ctx
    )
    assert result.result.data["canceled"] is True
    assert ctx.fetch.call_args.kwargs.get("method") == "POST"
    assert ctx.fetch.call_args.kwargs.get("json") == {"reason": "Conflict"}


@pytest.mark.asyncio
async def test_cancel_scheduled_event_without_reason_sends_no_body():
    ctx = make_ctx({})
    await calendly_integration.execute_action("cancel_scheduled_event", {"event_uuid": "ev1"}, ctx)
    assert ctx.fetch.call_args.kwargs.get("json") is None


@pytest.mark.asyncio
async def test_cancel_scheduled_event_missing_uuid_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("cancel_scheduled_event", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_cancel_scheduled_event_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("cancel_scheduled_event", {"event_uuid": "ev1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST EVENT INVITEES
# =============================================================================


@pytest.mark.asyncio
async def test_list_event_invitees_success():
    ctx = make_ctx(
        {
            "collection": [{"uri": "inv1", "email": "a@example.com", "status": "active"}],
            "pagination": {"count": 1},
        }
    )
    result = await calendly_integration.execute_action("list_event_invitees", {"event_uuid": "ev1", "count": 10}, ctx)
    assert result.result.data["invitees"][0]["email"] == "a@example.com"
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert url.endswith("/scheduled_events/ev1/invitees")


@pytest.mark.asyncio
async def test_list_event_invitees_missing_uuid_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("list_event_invitees", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_list_event_invitees_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("list_event_invitees", {"event_uuid": "ev1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET INVITEE
# =============================================================================


@pytest.mark.asyncio
async def test_get_invitee_success():
    ctx = make_ctx({"resource": {"uri": "inv1", "name": "Carol", "email": "carol@example.com"}})
    result = await calendly_integration.execute_action(
        "get_invitee", {"event_uuid": "ev1", "invitee_uuid": "inv1"}, ctx
    )
    assert result.result.data["invitee"]["name"] == "Carol"
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert url.endswith("/scheduled_events/ev1/invitees/inv1")


@pytest.mark.asyncio
async def test_get_invitee_missing_invitee_uuid_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("get_invitee", {"event_uuid": "ev1"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_invitee_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action(
        "get_invitee", {"event_uuid": "ev1", "invitee_uuid": "inv1"}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET EVENT TYPE AVAILABLE TIMES
# =============================================================================


@pytest.mark.asyncio
async def test_get_event_type_available_times_success():
    ctx = make_ctx({"collection": [{"start_time": "2025-02-01T10:00:00Z", "status": "available"}]})
    result = await calendly_integration.execute_action(
        "get_event_type_available_times",
        {
            "event_type": "https://api.calendly.com/event_types/et1",
            "start_time": "2025-02-01T00:00:00Z",
            "end_time": "2025-02-07T00:00:00Z",
        },
        ctx,
    )
    assert result.result.data["available_times"][0]["status"] == "available"
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["event_type"].endswith("/et1")


@pytest.mark.asyncio
async def test_get_event_type_available_times_missing_field_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("get_event_type_available_times", {"event_type": "et1"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_event_type_available_times_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action(
        "get_event_type_available_times",
        {"event_type": "et1", "start_time": "2025-02-01T00:00:00Z", "end_time": "2025-02-07T00:00:00Z"},
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET USER BUSY TIMES
# =============================================================================


@pytest.mark.asyncio
async def test_get_user_busy_times_success():
    ctx = make_ctx({"collection": [{"start_time": "2025-02-01T10:00:00Z", "end_time": "2025-02-01T11:00:00Z"}]})
    result = await calendly_integration.execute_action(
        "get_user_busy_times",
        {
            "user": "https://api.calendly.com/users/u1",
            "start_time": "2025-02-01T00:00:00Z",
            "end_time": "2025-02-07T00:00:00Z",
        },
        ctx,
    )
    assert len(result.result.data["busy_times"]) == 1


@pytest.mark.asyncio
async def test_get_user_busy_times_missing_field_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("get_user_busy_times", {"user": "u1"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_user_busy_times_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action(
        "get_user_busy_times",
        {"user": "u1", "start_time": "2025-02-01T00:00:00Z", "end_time": "2025-02-07T00:00:00Z"},
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST USER AVAILABILITY SCHEDULES
# =============================================================================


@pytest.mark.asyncio
async def test_list_user_availability_schedules_success():
    ctx = make_ctx({"collection": [{"uri": "sch1", "name": "Working hours"}]})
    result = await calendly_integration.execute_action(
        "list_user_availability_schedules", {"user": "https://api.calendly.com/users/u1"}, ctx
    )
    assert result.result.data["availability_schedules"][0]["name"] == "Working hours"


@pytest.mark.asyncio
async def test_list_user_availability_schedules_missing_user_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("list_user_availability_schedules", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_list_user_availability_schedules_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("list_user_availability_schedules", {"user": "u1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST ORGANIZATION MEMBERSHIPS
# =============================================================================


@pytest.mark.asyncio
async def test_list_organization_memberships_success():
    ctx = make_ctx(
        {
            "collection": [{"uri": "mem1", "role": "admin"}],
            "pagination": {"count": 1},
        }
    )
    result = await calendly_integration.execute_action("list_organization_memberships", {"count": 10}, ctx)
    assert result.result.data["memberships"][0]["role"] == "admin"


@pytest.mark.asyncio
async def test_list_organization_memberships_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("list_organization_memberships", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST WEBHOOKS
# =============================================================================


@pytest.mark.asyncio
async def test_list_webhooks_success():
    ctx = make_ctx(
        {
            "collection": [{"uri": "wh1", "callback_url": "https://example.com/hook", "state": "active"}],
            "pagination": {"count": 1},
        }
    )
    result = await calendly_integration.execute_action(
        "list_webhooks", {"organization": "https://api.calendly.com/organizations/org1"}, ctx
    )
    assert result.result.data["webhooks"][0]["state"] == "active"


@pytest.mark.asyncio
async def test_list_webhooks_missing_organization_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("list_webhooks", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_list_webhooks_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("list_webhooks", {"organization": "org1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET WEBHOOK
# =============================================================================


@pytest.mark.asyncio
async def test_get_webhook_success():
    ctx = make_ctx({"resource": {"uri": "wh1", "state": "active"}})
    result = await calendly_integration.execute_action("get_webhook", {"webhook_uuid": "wh1"}, ctx)
    assert result.result.data["webhook"]["state"] == "active"


@pytest.mark.asyncio
async def test_get_webhook_missing_uuid_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("get_webhook", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_webhook_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("get_webhook", {"webhook_uuid": "wh1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CREATE WEBHOOK
# =============================================================================


@pytest.mark.asyncio
async def test_create_webhook_success():
    ctx = make_ctx({"resource": {"uri": "wh_new", "state": "active"}})
    result = await calendly_integration.execute_action(
        "create_webhook",
        {
            "url": "https://example.com/hook",
            "events": ["invitee.created", "invitee.canceled"],
            "organization": "https://api.calendly.com/organizations/org1",
            "scope": "organization",
        },
        ctx,
    )
    assert result.result.data["webhook"]["uri"] == "wh_new"
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["url"] == "https://example.com/hook"
    assert body["events"] == ["invitee.created", "invitee.canceled"]
    assert body["scope"] == "organization"
    assert "user" not in body
    assert "signing_key" not in body


@pytest.mark.asyncio
async def test_create_webhook_includes_optional_fields():
    ctx = make_ctx({"resource": {"uri": "wh_new"}})
    await calendly_integration.execute_action(
        "create_webhook",
        {
            "url": "https://example.com/hook",
            "events": ["invitee.created"],
            "organization": "org1",
            "scope": "user",
            "user": "https://api.calendly.com/users/u1",
            "signing_key": "secret",
        },
        ctx,
    )
    body = ctx.fetch.call_args.kwargs.get("json", {})
    assert body["user"].endswith("/u1")
    assert body["signing_key"] == "secret"


@pytest.mark.asyncio
async def test_create_webhook_missing_required_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("create_webhook", {"url": "https://example.com/hook"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_webhook_error():
    ctx = make_ctx_error(Exception("402 Payment Required"))
    result = await calendly_integration.execute_action(
        "create_webhook",
        {
            "url": "https://example.com/hook",
            "events": ["invitee.created"],
            "organization": "org1",
            "scope": "organization",
        },
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "402 Payment Required" in result.result.message


# =============================================================================
# DELETE WEBHOOK
# =============================================================================


@pytest.mark.asyncio
async def test_delete_webhook_success():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("delete_webhook", {"webhook_uuid": "wh1"}, ctx)
    assert result.result.data["deleted"] is True
    assert ctx.fetch.call_args.kwargs.get("method") == "DELETE"
    url = ctx.fetch.call_args.args[0] if ctx.fetch.call_args.args else ctx.fetch.call_args.kwargs["url"]
    assert url.endswith("/webhook_subscriptions/wh1")


@pytest.mark.asyncio
async def test_delete_webhook_missing_uuid_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("delete_webhook", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_delete_webhook_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("delete_webhook", {"webhook_uuid": "wh1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST ROUTING FORMS
# =============================================================================


@pytest.mark.asyncio
async def test_list_routing_forms_success():
    ctx = make_ctx(
        {
            "collection": [{"uri": "rf1", "name": "Contact Form"}],
            "pagination": {"count": 1},
        }
    )
    result = await calendly_integration.execute_action(
        "list_routing_forms", {"organization": "https://api.calendly.com/organizations/org1"}, ctx
    )
    assert result.result.data["routing_forms"][0]["name"] == "Contact Form"


@pytest.mark.asyncio
async def test_list_routing_forms_forwards_optional_params():
    ctx = make_ctx({"collection": []})
    await calendly_integration.execute_action(
        "list_routing_forms",
        {"organization": "org1", "count": 5, "page_token": "tok"},  # nosec B105
        ctx,
    )
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params == {"organization": "org1", "count": 5, "page_token": "tok"}  # nosec B105


@pytest.mark.asyncio
async def test_list_routing_forms_missing_organization_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("list_routing_forms", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_list_routing_forms_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("list_routing_forms", {"organization": "org1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# GET ROUTING FORM
# =============================================================================


@pytest.mark.asyncio
async def test_get_routing_form_success():
    ctx = make_ctx({"resource": {"uri": "rf1", "name": "Contact Form", "status": "published"}})
    result = await calendly_integration.execute_action("get_routing_form", {"routing_form_uuid": "rf1"}, ctx)
    assert result.result.data["routing_form"]["status"] == "published"


@pytest.mark.asyncio
async def test_get_routing_form_missing_uuid_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("get_routing_form", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_routing_form_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("get_routing_form", {"routing_form_uuid": "rf1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# LIST ROUTING FORM SUBMISSIONS
# =============================================================================


@pytest.mark.asyncio
async def test_list_routing_form_submissions_success():
    ctx = make_ctx(
        {
            "collection": [{"uri": "sub1", "submitter": "x@example.com"}],
            "pagination": {"count": 1},
        }
    )
    result = await calendly_integration.execute_action(
        "list_routing_form_submissions",
        {"routing_form": "https://api.calendly.com/routing_forms/rf1"},
        ctx,
    )
    assert result.result.data["submissions"][0]["submitter"] == "x@example.com"


@pytest.mark.asyncio
async def test_list_routing_form_submissions_maps_form_param():
    ctx = make_ctx({"collection": []})
    await calendly_integration.execute_action("list_routing_form_submissions", {"routing_form": "rf1", "count": 3}, ctx)
    params = ctx.fetch.call_args.kwargs.get("params", {})
    # the integration maps `routing_form` -> `form` for the Calendly API
    assert params["form"] == "rf1"
    assert "routing_form" not in params
    assert params["count"] == 3


@pytest.mark.asyncio
async def test_list_routing_form_submissions_missing_form_validation_error():
    ctx = make_ctx({})
    result = await calendly_integration.execute_action("list_routing_form_submissions", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_list_routing_form_submissions_error():
    ctx = make_ctx_error()
    result = await calendly_integration.execute_action("list_routing_form_submissions", {"routing_form": "rf1"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
