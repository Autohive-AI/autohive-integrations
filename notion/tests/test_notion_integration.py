"""Read-only live tests using NOTION_ACCESS_TOKEN supplied by TeamCity.

Share at least one page with the connected Notion integration. Page tests discover
a shared page automatically; NOTION_TEST_PAGE_ID can select a specific fixture.
Run: pytest notion/tests/test_notion_integration.py -m integration
"""

from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlsplit
from uuid import UUID

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from notion.notion import notion

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials):
    token = env_credentials("NOTION_ACCESS_TOKEN")
    if not token:
        pytest.skip("NOTION_ACCESS_TOKEN not set")

    async def real_fetch(url, *, method="GET", headers=None, params=None, json=None, **kwargs):
        target = urlsplit(url)
        assert target.scheme == "https" and target.netloc == "api.notion.com"
        # Notion search is read-only despite using POST.
        assert method == "GET" or (method == "POST" and target.path == "/v1/search")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.request(
                method,
                url,
                headers={**(headers or {}), "Authorization": f"Bearer {token}"},
                params=params,
                json=json,
            ) as response:
                data = await response.json()
                if response.status >= 400:
                    # Do not let handlers turn API errors into successful empty lists.
                    raise RuntimeError(f"Notion HTTP {response.status}: {data.get('code', 'unknown_error')}")
                return FetchResponse(status=response.status, headers=dict(response.headers), data=data)

    context = MagicMock()
    context.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": token}}
    context.fetch = AsyncMock(side_effect=real_fetch)
    return context


def action_data(result):
    assert result.type == ResultType.ACTION, result.result
    return result.result.data


@pytest.fixture
async def shared_page_id(live_context, env_credentials):
    configured_id = env_credentials("NOTION_TEST_PAGE_ID")
    if configured_id:
        return configured_id
    result = await notion.execute_action(
        "search_notion",
        {"query": "", "filter": {"value": "page", "property": "object"}, "page_size": 1},
        live_context,
    )
    pages = action_data(result)["results"]
    if not pages:
        pytest.skip("Share a page with the CI Notion integration or set NOTION_TEST_PAGE_ID")
    return pages[0]["id"]


async def test_search_returns_pages(live_context):
    result = await notion.execute_action(
        "search_notion",
        {"query": "", "filter": {"value": "page", "property": "object"}, "page_size": 5},
        live_context,
    )
    data = action_data(result)
    assert data["object"] == "list"
    assert isinstance(data["results"], list)
    assert len(data["results"]) <= 5
    assert isinstance(data["has_more"], bool)
    if data["has_more"]:
        assert data["next_cursor"]
    for page in data["results"]:
        assert page["object"] == "page"
        assert UUID(page["id"])


async def test_search_respects_page_size(live_context):
    result = await notion.execute_action("search_notion", {"query": "", "page_size": 1}, live_context)
    data = action_data(result)
    assert isinstance(data["results"], list)
    assert len(data["results"]) <= 1


async def test_get_shared_page(live_context, shared_page_id):
    result = await notion.execute_action("get_notion_page", {"page_id": shared_page_id}, live_context)
    page = action_data(result)["page"]
    assert page["object"] == "page"
    assert UUID(page["id"]) == UUID(shared_page_id)
    assert isinstance(page["properties"], dict)


async def test_get_shared_page_blocks(live_context, shared_page_id):
    result = await notion.execute_action(
        "get_notion_block_children", {"block_id": shared_page_id, "page_size": 5}, live_context
    )
    data = action_data(result)
    assert isinstance(data["blocks"], list)
    assert len(data["blocks"]) <= 5
    assert isinstance(data["has_more"], bool)
    for block in data["blocks"]:
        assert block["object"] == "block"
        assert UUID(block["id"])
        assert block["type"]


async def test_get_shared_page_comments(live_context, shared_page_id):
    result = await notion.execute_action(
        "get_notion_comments", {"block_id": shared_page_id, "page_size": 5}, live_context
    )
    data = action_data(result)
    assert isinstance(data["comments"], list)
    assert len(data["comments"]) <= 5
    assert isinstance(data["has_more"], bool)
    for comment in data["comments"]:
        assert comment["object"] == "comment"
        assert UUID(comment["id"])
        assert isinstance(comment["rich_text"], list)
