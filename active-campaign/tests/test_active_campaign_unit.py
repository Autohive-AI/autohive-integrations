"""
Unit tests for the ActiveCampaign integration using mocked fetch.

Run with:
    pytest active-campaign/tests/test_active_campaign_unit.py -m unit
"""

import os
import sys

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from active_campaign import active_campaign  # noqa: E402

pytestmark = pytest.mark.unit

CAMPAIGN = {
    "id": "1",
    "type": "email",
    "name": "Test EDM",
    "send_amt": "100",
    "uniqueopens": "40",
    "uniquelinkclicks": "10",
    "hardbounces": "3",
    "softbounces": "2",
    "unsubscribes": "1",
    "status": "5",
    "sdate": "2025-01-01T10:00:00",
}


def ok(data):
    return FetchResponse(status=200, headers={}, data=data)


def err(status, data=None):
    return FetchResponse(status=status, headers={}, data=data or {})


# ---- list_campaigns ----


async def test_list_campaigns_returns_list(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"campaigns": [CAMPAIGN], "meta": {"total": "1"}})
    result = await active_campaign.execute_action("list_campaigns", {}, ctx)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert data["result"] is True
    assert len(data["campaigns"]) == 1
    assert data["total"] == 1


async def test_list_campaigns_derives_rates(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"campaigns": [CAMPAIGN], "meta": {"total": "1"}})
    result = await active_campaign.execute_action("list_campaigns", {}, ctx)
    c = result.result.data["campaigns"][0]
    assert c["sends"] == 100
    assert c["open_rate"] == 40.0
    assert c["click_rate"] == 10.0
    assert c["bounce_rate"] == 5.0


async def test_list_campaigns_zero_sends_no_division_error(make_context):
    campaign = {**CAMPAIGN, "send_amt": "0", "uniqueopens": "0", "uniquelinkclicks": "0"}
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"campaigns": [campaign], "meta": {"total": "1"}})
    result = await active_campaign.execute_action("list_campaigns", {}, ctx)
    c = result.result.data["campaigns"][0]
    assert c["open_rate"] == 0.0
    assert c["click_rate"] == 0.0
    assert c["bounce_rate"] == 0.0


async def test_list_campaigns_uses_correct_url(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"campaigns": [], "meta": {"total": "0"}})
    await active_campaign.execute_action("list_campaigns", {}, ctx)
    url = ctx.fetch.call_args.args[0]
    assert url.endswith("/campaigns")


async def test_list_campaigns_params_baked_into_url_not_passed_as_kwarg(make_context):
    """Params must be baked into the URL so the SDK retry loop cannot duplicate them."""
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"campaigns": [], "meta": {"total": "0"}})
    await active_campaign.execute_action("list_campaigns", {"limit": 2, "offset": 10}, ctx)
    call = ctx.fetch.call_args
    url = call.args[0]
    assert "limit=2" in url
    assert "offset=10" in url
    assert call.kwargs.get("params") is None


async def test_list_contacts_params_baked_into_url_not_passed_as_kwarg(make_context):
    """Params must be baked into the URL so the SDK retry loop cannot duplicate them."""
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"contacts": [], "meta": {"total": "0"}})
    await active_campaign.execute_action("list_contacts", {"email": "test@example.com", "limit": 5}, ctx)
    call = ctx.fetch.call_args
    url = call.args[0]
    assert "email=test%40example.com" in url or "email=test@example.com" in url
    assert "limit=5" in url
    assert call.kwargs.get("params") is None


async def test_list_contact_activities_params_baked_into_url_not_passed_as_kwarg(make_context):
    """Params must be baked into the URL so the SDK retry loop cannot duplicate them."""
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"activities": [], "meta": {"total": "0"}})
    await active_campaign.execute_action("list_contact_activities", {"contact_id": 42}, ctx)
    call = ctx.fetch.call_args
    url = call.args[0]
    assert "contact=42" in url
    assert call.kwargs.get("params") is None


async def test_list_lists_params_baked_into_url_not_passed_as_kwarg(make_context):
    """Params must be baked into the URL so the SDK retry loop cannot duplicate them."""
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"lists": [], "meta": {"total": "0"}})
    await active_campaign.execute_action("list_lists", {"limit": 5, "offset": 10}, ctx)
    call = ctx.fetch.call_args
    url = call.args[0]
    assert "limit=5" in url
    assert "offset=10" in url
    assert call.kwargs.get("params") is None


# ---- get_campaign ----


async def test_get_campaign_returns_campaign(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"campaign": CAMPAIGN})
    result = await active_campaign.execute_action("get_campaign", {"campaign_id": 1}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert data["campaign"]["name"] == "Test EDM"


async def test_get_campaign_derives_rates(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"campaign": CAMPAIGN})
    result = await active_campaign.execute_action("get_campaign", {"campaign_id": 1}, ctx)
    c = result.result.data["campaign"]
    assert c["open_rate"] == 40.0
    assert c["bounce_rate"] == 5.0


async def test_get_campaign_uses_correct_url(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"campaign": CAMPAIGN})
    await active_campaign.execute_action("get_campaign", {"campaign_id": 99}, ctx)
    url = ctx.fetch.call_args.args[0]
    assert "/campaigns/99" in url


# ---- get_campaign_links ----


async def test_get_campaign_links_returns_links(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"links": [{"id": "1", "link": "https://example.com", "uniqueclicks": "5"}]})
    result = await active_campaign.execute_action("get_campaign_links", {"campaign_id": 1}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert len(data["links"]) == 1


async def test_get_campaign_links_uses_correct_url(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"links": []})
    await active_campaign.execute_action("get_campaign_links", {"campaign_id": 5}, ctx)
    url = ctx.fetch.call_args.args[0]
    assert "/campaigns/5/links" in url


# ---- list_contacts ----


async def test_list_contacts_returns_list(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok(
        {"contacts": [{"id": "1", "email": "test@example.com", "firstName": "Jane"}], "meta": {"total": "1"}}
    )
    result = await active_campaign.execute_action("list_contacts", {}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert len(data["contacts"]) == 1
    assert data["total"] == 1


async def test_list_contacts_passes_email_filter(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"contacts": [], "meta": {"total": "0"}})
    await active_campaign.execute_action("list_contacts", {"email": "jane@example.com"}, ctx)
    url = ctx.fetch.call_args.args[0]
    assert "email=jane%40example.com" in url or "email=jane@example.com" in url


# ---- get_contact ----


async def test_get_contact_returns_contact(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"contact": {"id": "5", "email": "bob@example.com"}})
    result = await active_campaign.execute_action("get_contact", {"contact_id": 5}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert data["contact"]["email"] == "bob@example.com"
    assert data["contact"]["id"] == "5"


async def test_get_contact_uses_correct_url(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"contact": {"id": "5"}})
    await active_campaign.execute_action("get_contact", {"contact_id": 5}, ctx)
    url = ctx.fetch.call_args.args[0]
    assert "/contacts/5" in url


# ---- list_contact_activities ----


async def test_list_contact_activities_returns_activities(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok(
        {"activities": [{"tstamp": "2025-01-01", "reference_action": "open"}], "meta": {"total": "1"}}
    )
    result = await active_campaign.execute_action("list_contact_activities", {"contact_id": 10}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert len(data["activities"]) == 1
    assert data["total"] == 1


async def test_list_contact_activities_passes_contact_id(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"activities": [], "meta": {"total": "0"}})
    await active_campaign.execute_action("list_contact_activities", {"contact_id": 42}, ctx)
    url = ctx.fetch.call_args.args[0]
    assert "contact=42" in url


# ---- list_lists ----


async def test_list_lists_returns_lists(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"lists": [{"id": "1", "name": "Newsletter"}], "meta": {"total": "1"}})
    result = await active_campaign.execute_action("list_lists", {}, ctx)
    data = result.result.data
    assert data["result"] is True
    assert len(data["lists"]) == 1
    assert data["total"] == 1


# ---- error handling ----


async def test_error_response_returns_action_error(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "testkey", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = err(401, {"message": "Unauthorized"})
    result = await active_campaign.execute_action("list_campaigns", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert result.result.message == "Unauthorized"


async def test_auth_header_is_set(make_context):
    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"api_key": "my-secret-key", "api_url": "https://testaccount.api-us1.com"},
        }
    )
    ctx.fetch.return_value = ok({"campaigns": [], "meta": {"total": "0"}})
    await active_campaign.execute_action("list_campaigns", {}, ctx)
    headers = ctx.fetch.call_args.kwargs["headers"]
    assert headers["Api-Token"] == "my-secret-key"
