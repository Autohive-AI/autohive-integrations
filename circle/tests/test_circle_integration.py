"""
End-to-end integration tests for the Circle integration (read-only actions).

Requires credentials set in environment variables or a .env file at the repo root:
    CIRCLE_API_TOKEN — your API token from Circle Settings > API

Optional — target specific resources for faster / more thorough tests:
    CIRCLE_TEST_POST_ID    — a known post ID
    CIRCLE_TEST_SPACE_ID   — a known space ID
    CIRCLE_TEST_MEMBER_ID  — a known member ID (numeric)
    CIRCLE_TEST_MEMBER_EMAIL — a known member email for search_member_by_email

Run with:
    pytest circle/tests/test_circle_integration.py -m integration
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType
from circle.circle import circle  # noqa: E402

pytestmark = pytest.mark.integration

CIRCLE_API_TOKEN = os.getenv("CIRCLE_API_TOKEN", "")
CIRCLE_TEST_POST_ID = os.getenv("CIRCLE_TEST_POST_ID", "")
CIRCLE_TEST_SPACE_ID = os.getenv("CIRCLE_TEST_SPACE_ID", "")
CIRCLE_TEST_MEMBER_ID = os.getenv("CIRCLE_TEST_MEMBER_ID", "")
CIRCLE_TEST_MEMBER_EMAIL = os.getenv("CIRCLE_TEST_MEMBER_EMAIL", "")

skip_if_no_token = pytest.mark.skipif(
    not CIRCLE_API_TOKEN,
    reason="CIRCLE_API_TOKEN required",
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
                    raise RateLimitError(retry_after, resp.status, str(data), data)
                if resp.status < 200 or resp.status >= 300:
                    raise HTTPError(resp.status, str(data), data)

                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={"api_token": CIRCLE_API_TOKEN})
    ctx.fetch.side_effect = real_fetch
    return ctx


# ---- Community ----


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_community_info(live_context):
    result = await circle.execute_action("get_community_info", {}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("community") is not None


# ---- Members ----


@skip_if_no_token
@pytest.mark.asyncio
async def test_list_members(live_context):
    result = await circle.execute_action("list_members", {"per_page": 5}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert isinstance(result.result.data.get("members"), list)


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_member(live_context):
    member_id = CIRCLE_TEST_MEMBER_ID
    if not member_id:
        list_result = await circle.execute_action("list_members", {"per_page": 1}, live_context)
        members = list_result.result.data.get("members", [])
        if not members:
            pytest.skip("No members found")
        member_id = str(members[0].get("id") or members[0].get("member_id", ""))
    result = await circle.execute_action("get_member", {"member_id": member_id}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("member") is not None


@skip_if_no_token
@pytest.mark.asyncio
async def test_search_member_by_email(live_context):
    email = CIRCLE_TEST_MEMBER_EMAIL
    if not email:
        pytest.skip("CIRCLE_TEST_MEMBER_EMAIL not set")
    result = await circle.execute_action("search_member_by_email", {"email": email}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("member") is not None


# ---- Spaces ----


@skip_if_no_token
@pytest.mark.asyncio
async def test_search_spaces(live_context):
    result = await circle.execute_action("search_spaces", {"per_page": 5}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert isinstance(result.result.data.get("spaces"), list)


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_space(live_context):
    space_id = CIRCLE_TEST_SPACE_ID
    if not space_id:
        list_result = await circle.execute_action("search_spaces", {"per_page": 1}, live_context)
        spaces = list_result.result.data.get("spaces", [])
        if not spaces:
            pytest.skip("No spaces found")
        space_id = str(spaces[0].get("id", ""))
    result = await circle.execute_action("get_space", {"space_id": space_id}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("space") is not None


# ---- Posts ----


@skip_if_no_token
@pytest.mark.asyncio
async def test_search_posts(live_context):
    result = await circle.execute_action("search_posts", {"per_page": 5}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert isinstance(result.result.data.get("posts"), list)


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_post(live_context):
    post_id = CIRCLE_TEST_POST_ID
    if not post_id:
        list_result = await circle.execute_action("search_posts", {"per_page": 1}, live_context)
        posts = list_result.result.data.get("posts", [])
        if not posts:
            pytest.skip("No posts found")
        post_id = str(posts[0].get("id", ""))
    result = await circle.execute_action("get_post", {"post_id": post_id}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("post") is not None


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_post_comments(live_context):
    post_id = CIRCLE_TEST_POST_ID
    if not post_id:
        list_result = await circle.execute_action("search_posts", {"per_page": 1}, live_context)
        posts = list_result.result.data.get("posts", [])
        if not posts:
            pytest.skip("No posts found")
        post_id = str(posts[0].get("id", ""))
    result = await circle.execute_action("get_post_comments", {"post_id": post_id}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "comments" in result.result.data


# ---- Events ----


@skip_if_no_token
@pytest.mark.asyncio
async def test_search_events(live_context):
    result = await circle.execute_action("search_events", {"per_page": 5}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert isinstance(result.result.data.get("events"), list)


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_event(live_context):
    list_result = await circle.execute_action("search_events", {"per_page": 1}, live_context)
    events = list_result.result.data.get("events", [])
    if not events:
        pytest.skip("No events found")
    event_id = str(events[0].get("id", ""))
    result = await circle.execute_action("get_event", {"event_id": event_id}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("event") is not None


# ---- Tags & Groups ----


@skip_if_no_token
@pytest.mark.asyncio
async def test_list_tags(live_context):
    result = await circle.execute_action("list_tags", {}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert isinstance(result.result.data.get("tags"), list)


@skip_if_no_token
@pytest.mark.asyncio
async def test_list_space_groups(live_context):
    result = await circle.execute_action("list_space_groups", {}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert isinstance(result.result.data.get("space_groups"), list)


@skip_if_no_token
@pytest.mark.asyncio
async def test_list_access_groups(live_context):
    result = await circle.execute_action("list_access_groups", {}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert isinstance(result.result.data.get("access_groups"), list)
