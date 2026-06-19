import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from kajabi.kajabi import kajabi

pytestmark = pytest.mark.integration

API_KEY = os.getenv("KAJABI_API_KEY", "")
skip_if_no_creds = pytest.mark.skipif(not API_KEY, reason="KAJABI_API_KEY required")


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
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={"api_key": API_KEY})
    ctx.fetch.side_effect = real_fetch
    return ctx


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_contacts_live(live_context):
    result = await kajabi.execute_action("list_contacts", {"page_size": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "contacts" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_contact_tags_live(live_context):
    result = await kajabi.execute_action("list_contact_tags", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "tags" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_courses_live(live_context):
    result = await kajabi.execute_action("list_courses", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "courses" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_blog_posts_live(live_context):
    result = await kajabi.execute_action("list_blog_posts", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "posts" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_create_get_delete_contact_live(live_context):
    created_id = None
    try:
        create_result = await kajabi.execute_action(
            "create_contact",
            {"name": "Autohive Test", "email": "autohive-test@example.com"},
            live_context,
        )
        assert create_result.type == ResultType.ACTION, create_result.result.message
        created_id = create_result.result.data["id"]

        get_result = await kajabi.execute_action("get_contact", {"contact_id": created_id}, live_context)
        assert get_result.type == ResultType.ACTION, get_result.result.message
        assert get_result.result.data["id"] == created_id
    finally:
        if created_id:
            await kajabi.execute_action("delete_contact", {"contact_id": created_id}, live_context)


@skip_if_no_creds
@pytest.mark.asyncio
async def test_create_get_delete_contact_note_live(live_context):
    contact_id = None
    note_id = None
    try:
        contact_result = await kajabi.execute_action(
            "create_contact",
            {"name": "Note Test", "email": "note-test@example.com"},
            live_context,
        )
        assert contact_result.type == ResultType.ACTION, contact_result.result.message
        contact_id = contact_result.result.data["id"]

        note_result = await kajabi.execute_action(
            "create_contact_note",
            {"contact_id": contact_id, "body": "Integration test note"},
            live_context,
        )
        assert note_result.type == ResultType.ACTION, note_result.result.message
        note_id = note_result.result.data["id"]

        get_result = await kajabi.execute_action("get_contact_note", {"note_id": note_id}, live_context)
        assert get_result.type == ResultType.ACTION, get_result.result.message
        assert get_result.result.data["body"] == "Integration test note"
    finally:
        if note_id:
            await kajabi.execute_action("delete_contact_note", {"note_id": note_id}, live_context)
        if contact_id:
            await kajabi.execute_action("delete_contact", {"contact_id": contact_id}, live_context)
