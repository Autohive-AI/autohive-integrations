"""
End-to-end integration tests for the ActiveCampaign integration.

Requires credentials set in environment variables or a .env file at the repo root:
    ACTIVECAMPAIGN_API_KEY  — your API key (Settings > Developer)
    ACTIVECAMPAIGN_API_URL  — your API URL (e.g. https://mycompany.api-us1.com)

Optional — targets specific resources for faster tests:
    ACTIVECAMPAIGN_TEST_CAMPAIGN_ID  — a known campaign ID
    ACTIVECAMPAIGN_TEST_CONTACT_ID   — a known contact ID

Run with:
    pytest active-campaign/tests/test_active_campaign_integration.py -m integration
"""

import os
import sys

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from active_campaign import active_campaign  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    api_key = env_credentials("ACTIVECAMPAIGN_API_KEY")
    api_url = env_credentials("ACTIVECAMPAIGN_API_URL")

    if not api_key:
        pytest.skip("ACTIVECAMPAIGN_API_KEY not set — skipping integration tests")
    if not api_url:
        pytest.skip("ACTIVECAMPAIGN_API_URL not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, **kwargs):
        merged = dict(headers or {})
        merged["Api-Token"] = api_key
        merged["Accept"] = "application/json"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, params=params, json=json, headers=merged) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={"auth_type": "Custom", "credentials": {"api_key": api_key, "api_url": api_url}})
    ctx.fetch.side_effect = real_fetch
    return ctx


def _campaign_id(env_credentials):
    val = env_credentials("ACTIVECAMPAIGN_TEST_CAMPAIGN_ID")
    return int(val) if val else 0


def _contact_id(env_credentials):
    val = env_credentials("ACTIVECAMPAIGN_TEST_CONTACT_ID")
    return int(val) if val else 0


# ---- list_campaigns ----


class TestListCampaigns:
    async def test_returns_list(self, live_context):
        result = await active_campaign.execute_action("list_campaigns", {}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["campaigns"], list)
        assert isinstance(data["total"], int)

    async def test_campaign_has_rate_fields(self, live_context):
        result = await active_campaign.execute_action("list_campaigns", {"limit": 5}, live_context)
        campaigns = result.result.data["campaigns"]
        if not campaigns:
            pytest.skip("No campaigns in account")
        c = campaigns[0]
        assert "sends" in c
        assert "open_rate" in c
        assert "click_rate" in c
        assert "bounce_rate" in c

    async def test_limit_respected(self, live_context):
        result = await active_campaign.execute_action("list_campaigns", {"limit": 2}, live_context)
        assert len(result.result.data["campaigns"]) <= 2


# ---- get_campaign ----


class TestGetCampaign:
    async def test_returns_campaign_with_rates(self, live_context, env_credentials):
        cid = _campaign_id(env_credentials)
        if not cid:
            list_result = await active_campaign.execute_action("list_campaigns", {"limit": 1}, live_context)
            campaigns = list_result.result.data["campaigns"]
            if not campaigns:
                pytest.skip("No campaigns in account")
            cid = int(campaigns[0]["id"])

        result = await active_campaign.execute_action("get_campaign", {"campaign_id": cid}, live_context)
        assert result.type == ResultType.ACTION
        c = result.result.data["campaign"]
        assert "name" in c
        assert "open_rate" in c
        assert "click_rate" in c
        assert "bounce_rate" in c


# ---- get_campaign_links ----


class TestGetCampaignLinks:
    async def test_returns_links(self, live_context, env_credentials):
        cid = _campaign_id(env_credentials)
        if not cid:
            list_result = await active_campaign.execute_action("list_campaigns", {"limit": 1}, live_context)
            campaigns = list_result.result.data["campaigns"]
            if not campaigns:
                pytest.skip("No campaigns in account")
            cid = int(campaigns[0]["id"])

        result = await active_campaign.execute_action("get_campaign_links", {"campaign_id": cid}, live_context)
        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data["links"], list)


# ---- list_contacts ----


class TestListContacts:
    async def test_returns_contacts(self, live_context):
        result = await active_campaign.execute_action("list_contacts", {"limit": 5}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["contacts"], list)
        assert isinstance(data["total"], int)

    async def test_contact_has_expected_fields(self, live_context):
        result = await active_campaign.execute_action("list_contacts", {"limit": 1}, live_context)
        contacts = result.result.data["contacts"]
        if not contacts:
            pytest.skip("No contacts in account")
        assert "id" in contacts[0]
        assert "email" in contacts[0]


# ---- get_contact ----


class TestGetContact:
    async def test_returns_contact(self, live_context, env_credentials):
        cid = _contact_id(env_credentials)
        if not cid:
            list_result = await active_campaign.execute_action("list_contacts", {"limit": 1}, live_context)
            contacts = list_result.result.data["contacts"]
            if not contacts:
                pytest.skip("No contacts in account")
            cid = int(contacts[0]["id"])

        result = await active_campaign.execute_action("get_contact", {"contact_id": cid}, live_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["contact"] is not None


# ---- list_contact_activities ----


class TestListContactActivities:
    async def test_returns_activities(self, live_context, env_credentials):
        cid = _contact_id(env_credentials)
        if not cid:
            list_result = await active_campaign.execute_action("list_contacts", {"limit": 1}, live_context)
            contacts = list_result.result.data["contacts"]
            if not contacts:
                pytest.skip("No contacts in account")
            cid = int(contacts[0]["id"])

        result = await active_campaign.execute_action("list_contact_activities", {"contact_id": cid}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["activities"], list)
        assert isinstance(data["total"], int)


# ---- list_lists ----


class TestListLists:
    async def test_returns_lists(self, live_context):
        result = await active_campaign.execute_action("list_lists", {}, live_context)
        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["result"] is True
        assert isinstance(data["lists"], list)
        assert isinstance(data["total"], int)

    async def test_list_has_expected_fields(self, live_context):
        result = await active_campaign.execute_action("list_lists", {"limit": 1}, live_context)
        lists = result.result.data["lists"]
        if not lists:
            pytest.skip("No lists in account")
        assert "id" in lists[0]
        assert "name" in lists[0]
