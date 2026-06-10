import os
import pytest
from autohive_integrations_sdk import ExecutionContext
from ghost.ghost import ghost

pytestmark = pytest.mark.integration

GHOST_API_URL = os.getenv("GHOST_API_URL", "")
GHOST_CONTENT_API_KEY = os.getenv("GHOST_CONTENT_API_KEY", "")
GHOST_ADMIN_API_KEY = os.getenv("GHOST_ADMIN_API_KEY", "")
GHOST_TEST_POST_ID = os.getenv("GHOST_TEST_POST_ID", "")
GHOST_TEST_POST_UPDATED_AT = os.getenv("GHOST_TEST_POST_UPDATED_AT", "")
GHOST_TEST_NEWSLETTER_SLUG = os.getenv("GHOST_TEST_NEWSLETTER_SLUG", "")


@pytest.fixture
def live_context():
    if not GHOST_API_URL or not GHOST_CONTENT_API_KEY or not GHOST_ADMIN_API_KEY:
        pytest.skip("GHOST_API_URL, GHOST_CONTENT_API_KEY, and GHOST_ADMIN_API_KEY must be set")
    ctx = ExecutionContext.__new__(ExecutionContext)
    ctx.auth = {
        "api_url": GHOST_API_URL,
        "content_api_key": GHOST_CONTENT_API_KEY,
        "admin_api_key": GHOST_ADMIN_API_KEY,
    }
    return ctx


@pytest.mark.asyncio
async def test_get_posts_live(live_context):
    result = await ghost.execute_action("get_posts", {"limit": 5}, live_context)
    assert result.result.data.get("posts") is not None


@pytest.mark.asyncio
async def test_get_pages_live(live_context):
    result = await ghost.execute_action("get_pages", {"limit": 5}, live_context)
    assert result.result.data.get("pages") is not None


@pytest.mark.asyncio
async def test_get_tags_live(live_context):
    result = await ghost.execute_action("get_tags", {}, live_context)
    assert result.result.data.get("tags") is not None


@pytest.mark.asyncio
async def test_get_authors_live(live_context):
    result = await ghost.execute_action("get_authors", {}, live_context)
    assert result.result.data.get("authors") is not None


@pytest.mark.asyncio
async def test_get_settings_live(live_context):
    result = await ghost.execute_action("get_settings", {}, live_context)
    assert result.result.data.get("settings") is not None


@pytest.mark.asyncio
async def test_get_tiers_live(live_context):
    result = await ghost.execute_action("get_tiers", {}, live_context)
    assert result.result.data.get("tiers") is not None


@pytest.mark.asyncio
async def test_create_draft_post_live(live_context):
    result = await ghost.execute_action(
        "create_post",
        {"title": "[SDK 2.0 migration test] Draft post", "status": "draft"},
        live_context,
    )
    assert result.result.data.get("post") is not None
