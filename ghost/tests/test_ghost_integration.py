import os
import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType
from ghost.ghost import ghost, _make_admin_jwt

pytestmark = pytest.mark.integration

GHOST_API_URL = os.getenv("GHOST_API_URL", "")
GHOST_CONTENT_API_KEY = os.getenv("GHOST_CONTENT_API_KEY", "")
GHOST_ADMIN_API_KEY = os.getenv("GHOST_ADMIN_API_KEY", "")
GHOST_TEST_POST_ID = os.getenv("GHOST_TEST_POST_ID", "")
GHOST_TEST_POST_UPDATED_AT = os.getenv("GHOST_TEST_POST_UPDATED_AT", "")
GHOST_TEST_NEWSLETTER_SLUG = os.getenv("GHOST_TEST_NEWSLETTER_SLUG", "")
GHOST_TEST_MEMBER_ID = os.getenv("GHOST_TEST_MEMBER_ID", "")


@pytest.fixture
def live_context(make_context):
    if not GHOST_API_URL or not GHOST_CONTENT_API_KEY or not GHOST_ADMIN_API_KEY:
        pytest.skip("GHOST_API_URL, GHOST_CONTENT_API_KEY, and GHOST_ADMIN_API_KEY must be set")

    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, body=None, **kwargs):
        payload = kwargs.get("data", body)
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                data=payload,
                headers=dict(headers or {}),
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "api_url": GHOST_API_URL,
            "content_api_key": GHOST_CONTENT_API_KEY,
            "admin_api_key": GHOST_ADMIN_API_KEY,
        }
    )
    ctx.fetch.side_effect = real_fetch
    return ctx


# ---- Content API ----


@pytest.mark.asyncio
async def test_get_posts_live(live_context):
    result = await ghost.execute_action("get_posts", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("posts") is not None


@pytest.mark.asyncio
async def test_get_post_live(live_context):
    if not GHOST_TEST_POST_ID:
        pytest.skip("GHOST_TEST_POST_ID not set")
    result = await ghost.execute_action("get_post", {"id": GHOST_TEST_POST_ID}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("post") is not None


@pytest.mark.asyncio
async def test_get_pages_live(live_context):
    result = await ghost.execute_action("get_pages", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("pages") is not None


@pytest.mark.asyncio
async def test_get_tags_live(live_context):
    result = await ghost.execute_action("get_tags", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("tags") is not None


@pytest.mark.asyncio
async def test_get_authors_live(live_context):
    result = await ghost.execute_action("get_authors", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("authors") is not None


@pytest.mark.asyncio
async def test_get_settings_live(live_context):
    result = await ghost.execute_action("get_settings", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("settings") is not None


@pytest.mark.asyncio
async def test_get_tiers_live(live_context):
    result = await ghost.execute_action("get_tiers", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("tiers") is not None


# ---- Admin API (destructive) ----


@pytest.mark.destructive
@pytest.mark.asyncio
async def test_post_lifecycle_live(live_context):
    """create_post (draft) → update_post → DELETE via admin API for cleanup."""
    create_result = await ghost.execute_action(
        "create_post",
        {"title": "[Autohive SDK 2.0 test] Draft post", "status": "draft"},
        live_context,
    )
    assert create_result.type == ResultType.ACTION, create_result.result.message
    post = create_result.result.data["post"]
    assert post is not None
    post_id = post["id"]
    updated_at = post["updated_at"]

    update_result = await ghost.execute_action(
        "update_post",
        {"id": post_id, "updated_at": updated_at, "title": "[Autohive SDK 2.0 test] Updated post"},
        live_context,
    )
    assert update_result.type == ResultType.ACTION, update_result.result.message

    # Cleanup — Ghost Admin API DELETE (no registered action)
    base_url = GHOST_API_URL.rstrip("/")
    token = _make_admin_jwt(live_context)
    await live_context.fetch(
        f"{base_url}/ghost/api/admin/posts/{post_id}/",
        method="DELETE",
        headers={"Authorization": f"Ghost {token}"},
    )


@pytest.mark.destructive
@pytest.mark.asyncio
async def test_page_lifecycle_live(live_context):
    """create_page (draft) → DELETE via admin API for cleanup."""
    create_result = await ghost.execute_action(
        "create_page",
        {"title": "[Autohive SDK 2.0 test] Draft page", "status": "draft"},
        live_context,
    )
    assert create_result.type == ResultType.ACTION, create_result.result.message
    page = create_result.result.data["page"]
    assert page is not None
    page_id = page["id"]

    # Cleanup — Ghost Admin API DELETE (no registered action)
    base_url = GHOST_API_URL.rstrip("/")
    token = _make_admin_jwt(live_context)
    await live_context.fetch(
        f"{base_url}/ghost/api/admin/pages/{page_id}/",
        method="DELETE",
        headers={"Authorization": f"Ghost {token}"},
    )


@pytest.mark.destructive
@pytest.mark.asyncio
async def test_member_lifecycle_live(live_context):
    """create_member → update_member."""
    import time

    email = f"autohive-sdk-test-{int(time.time())}@example.com"
    create_result = await ghost.execute_action(
        "create_member",
        {"email": email, "name": "Autohive SDK Test"},
        live_context,
    )
    assert create_result.type == ResultType.ACTION, create_result.result.message
    member = create_result.result.data["member"]
    assert member is not None
    member_id = member["id"]

    update_result = await ghost.execute_action(
        "update_member",
        {"id": member_id, "name": "Autohive SDK Test (updated)"},
        live_context,
    )
    assert update_result.type == ResultType.ACTION, update_result.result.message


@pytest.mark.destructive
@pytest.mark.asyncio
async def test_send_newsletter_live(live_context):
    if not GHOST_TEST_POST_ID or not GHOST_TEST_POST_UPDATED_AT or not GHOST_TEST_NEWSLETTER_SLUG:
        pytest.skip("GHOST_TEST_POST_ID, GHOST_TEST_POST_UPDATED_AT, and GHOST_TEST_NEWSLETTER_SLUG required")
    result = await ghost.execute_action(
        "send_newsletter",
        {
            "post_id": GHOST_TEST_POST_ID,
            "updated_at": GHOST_TEST_POST_UPDATED_AT,
            "newsletter_slug": GHOST_TEST_NEWSLETTER_SLUG,
        },
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data.get("post") is not None
