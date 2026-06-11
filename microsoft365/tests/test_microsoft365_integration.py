import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType
from microsoft365.microsoft365 import microsoft365

pytestmark = pytest.mark.integration

CRED = os.getenv("MICROSOFT365_ACCESS_TOKEN", "")
skip_if_no_creds = pytest.mark.skipif(not CRED, reason="MICROSOFT365_ACCESS_TOKEN required")


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
                headers={"Authorization": f"Bearer {CRED}", **(dict(headers or {}))},
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.read()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={})
    ctx.fetch.side_effect = real_fetch
    return ctx


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_emails_live(live_context):
    result = await microsoft365.execute_action("list_emails", {"limit": 5}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "emails" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_emails_with_fields_live(live_context):
    result = await microsoft365.execute_action(
        "list_emails",
        {"limit": 5, "fields": ["id", "subject", "sender", "receivedDateTime", "hasAttachments", "bodyPreview"]},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "emails" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_calendar_events_live(live_context):
    result = await microsoft365.execute_action("list_calendar_events", {"limit": 5}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "events" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_files_live(live_context):
    result = await microsoft365.execute_action("list_files", {"folder_path": "/"}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "files" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_mail_folders_live(live_context):
    result = await microsoft365.execute_action(
        "list_mail_folders", {"include_hidden": False, "include_children": False}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "folders" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_read_contacts_live(live_context):
    result = await microsoft365.execute_action("read_contacts", {"limit": 5}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "contacts" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_search_onedrive_files_live(live_context):
    result = await microsoft365.execute_action(
        "search_onedrive_files", {"query": "test", "limit": 5}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "files" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_search_emails_live(live_context):
    result = await microsoft365.execute_action(
        "search_emails", {"query": "test", "limit": 5}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "messages" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_01_create_draft_email_live(live_context):
    result = await microsoft365.execute_action(
        "create_draft_email",
        {
            "subject": "Integration Test Draft",
            "body": "This is a test draft created by integration tests.",
            "body_type": "Text",
            "to_recipients": ["test@example.com"],
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "draft_id" in result.result.data
    os.environ["_TEST_DRAFT_ID"] = result.result.data["draft_id"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_02_send_draft_email_live(live_context):
    draft_id = os.environ.get("_TEST_DRAFT_ID")
    if not draft_id:
        pytest.skip("No draft_id from test_01_create_draft_email_live")
    result = await microsoft365.execute_action(
        "send_draft_email", {"draft_id": draft_id}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("sent") is True
