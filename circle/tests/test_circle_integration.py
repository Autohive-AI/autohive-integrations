import os
import pytest
from autohive_integrations_sdk import ExecutionContext
from circle.circle import circle

pytestmark = pytest.mark.integration

CIRCLE_API_TOKEN = os.getenv("CIRCLE_API_TOKEN", "")
CIRCLE_TEST_POST_ID = os.getenv("CIRCLE_TEST_POST_ID", "")
CIRCLE_TEST_SPACE_ID = os.getenv("CIRCLE_TEST_SPACE_ID", "")
CIRCLE_TEST_MEMBER_ID = os.getenv("CIRCLE_TEST_MEMBER_ID", "")


@pytest.fixture
def live_context():
    if not CIRCLE_API_TOKEN:
        pytest.skip("CIRCLE_API_TOKEN not set")
    ctx = ExecutionContext.__new__(ExecutionContext)
    ctx.auth = {"api_token": CIRCLE_API_TOKEN}
    return ctx


@pytest.mark.asyncio
async def test_get_community_info_live(live_context):
    result = await circle.execute_action("get_community_info", {}, live_context)
    assert result.result.data.get("community") is not None


@pytest.mark.asyncio
async def test_list_members_live(live_context):
    result = await circle.execute_action("list_members", {"per_page": 5}, live_context)
    assert result.result.data.get("members") is not None


@pytest.mark.asyncio
async def test_search_spaces_live(live_context):
    result = await circle.execute_action("search_spaces", {"per_page": 5}, live_context)
    assert result.result.data.get("spaces") is not None


@pytest.mark.asyncio
async def test_list_tags_live(live_context):
    result = await circle.execute_action("list_tags", {}, live_context)
    assert result.result.data.get("tags") is not None


@pytest.mark.asyncio
async def test_list_space_groups_live(live_context):
    result = await circle.execute_action("list_space_groups", {}, live_context)
    assert result.result.data.get("space_groups") is not None


@pytest.mark.asyncio
async def test_get_post_live(live_context):
    if not CIRCLE_TEST_POST_ID:
        pytest.skip("CIRCLE_TEST_POST_ID not set")
    result = await circle.execute_action("get_post", {"post_id": CIRCLE_TEST_POST_ID}, live_context)
    assert result.result.data.get("post") is not None


@pytest.mark.asyncio
async def test_get_member_live(live_context):
    if not CIRCLE_TEST_MEMBER_ID:
        pytest.skip("CIRCLE_TEST_MEMBER_ID not set")
    result = await circle.execute_action("get_member", {"member_id": CIRCLE_TEST_MEMBER_ID}, live_context)
    assert result.result.data.get("member") is not None
