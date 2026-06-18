"""
End-to-end integration tests for the iMIS RiSE integration.

Requires credentials set in environment variables or a .env file at the repo root:
    IMIS_SITE_URL  — your iMIS site URL (e.g. https://yourorg.imis.com)
    IMIS_USERNAME  — iMIS username
    IMIS_PASSWORD  — iMIS password
    IMIS_CLIENT_ID — OAuth client ID (default: iMIS)

Optional:
    IMIS_TEST_PARTY_ID  — a known contact Party ID for get/update tests
    IMIS_TEST_EVENT_ID  — a known event ID for get/update tests

Run with:
    pytest imis/tests/test_imis_integration.py -m integration
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType
from imis.imis import imis  # noqa: E402

pytestmark = pytest.mark.integration

IMIS_SITE_URL = os.getenv("IMIS_SITE_URL", "")
IMIS_USERNAME = os.getenv("IMIS_USERNAME", "")
IMIS_PASSWORD = os.getenv("IMIS_PASSWORD", "")
IMIS_CLIENT_ID = os.getenv("IMIS_CLIENT_ID", "iMIS")
IMIS_TEST_PARTY_ID = os.getenv("IMIS_TEST_PARTY_ID", "")
IMIS_TEST_EVENT_ID = os.getenv("IMIS_TEST_EVENT_ID", "")

skip_if_no_creds = pytest.mark.skipif(
    not IMIS_SITE_URL or not IMIS_USERNAME or not IMIS_PASSWORD,
    reason="IMIS_SITE_URL, IMIS_USERNAME, and IMIS_PASSWORD required",
)


@pytest.fixture
def live_context(make_context):
    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, body=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                data=body,
                headers=dict(headers or {}),
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after)
                if resp.status >= 400:
                    raise HTTPError(resp.status, str(data))
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "site_url": IMIS_SITE_URL,
            "username": IMIS_USERNAME,
            "password": IMIS_PASSWORD,
            "client_id": IMIS_CLIENT_ID,
        }
    )
    ctx.fetch.side_effect = real_fetch
    return ctx


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_events_live(live_context):
    result = await imis.execute_action("list_events", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert isinstance(result.result.data["events"], list)


@skip_if_no_creds
@pytest.mark.asyncio
async def test_get_event_live(live_context):
    event_id = IMIS_TEST_EVENT_ID
    if not event_id:
        list_result = await imis.execute_action("list_events", {"limit": 1}, live_context)
        events = list_result.result.data.get("events", [])
        if not events:
            pytest.skip("No events found in iMIS instance")
        event_id = str(events[0].get("Id", ""))
    result = await imis.execute_action("get_event", {"event_id": event_id}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data["event"] is not None


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_registrations_live(live_context):
    result = await imis.execute_action("list_registrations", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert isinstance(result.result.data["registrations"], list)


@skip_if_no_creds
@pytest.mark.asyncio
async def test_get_contact_live(live_context):
    if not IMIS_TEST_PARTY_ID:
        pytest.skip("IMIS_TEST_PARTY_ID not set")
    result = await imis.execute_action("get_contact", {"party_id": IMIS_TEST_PARTY_ID}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data["contact"] is not None


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_media_assets_live(live_context):
    result = await imis.execute_action("list_media_assets", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert isinstance(result.result.data["assets"], list)
