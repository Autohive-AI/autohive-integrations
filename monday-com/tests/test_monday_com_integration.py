"""
End-to-end integration tests for the Monday.com integration.

These tests call the real Monday.com GraphQL API and require a valid access
token set in the MONDAY_ACCESS_TOKEN environment variable (via .env or export).

Run read-only tests (safe):
    pytest monday-com/tests/test_monday_com_integration.py -m "integration and not destructive"

Run destructive tests (create/update real items on a test board):
    pytest monday-com/tests/test_monday_com_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os

import aiohttp
import pytest
from unittest.mock import AsyncMock, MagicMock
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import HTTPError, RateLimitError

from monday_com import monday_com as integration

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("MONDAY_ACCESS_TOKEN", "")

# Optional: provide a known board/item so tests don't need to chain list→get.
TEST_BOARD_ID = os.environ.get("MONDAY_TEST_BOARD_ID", "")
TEST_ITEM_ID = os.environ.get("MONDAY_TEST_ITEM_ID", "")

skip_if_no_token = pytest.mark.skipif(
    not ACCESS_TOKEN,
    reason="MONDAY_ACCESS_TOKEN required",
)


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("MONDAY_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=dict(headers or {}), params=params) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()

                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, "Rate limit exceeded", str(data))
                if not resp.ok:
                    raise HTTPError(resp.status, str(data), data)

                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"access_token": ACCESS_TOKEN}}  # nosec B105
    return ctx


async def _first_board_id(live_context):
    """Return a board id from the account, or skip if none exist."""
    if TEST_BOARD_ID:
        return TEST_BOARD_ID
    from autohive_integrations_sdk import ResultType

    result = await integration.execute_action("get_boards", {"limit": 1}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"get_boards failed: {result.result.message}")
    boards = result.result.data.get("boards", [])
    if not boards:
        pytest.skip("No boards on this account to test with")
    return boards[0]["id"]


async def _first_item_id(live_context, board_id):
    """Return an item id from a board, or skip if none exist."""
    if TEST_ITEM_ID:
        return TEST_ITEM_ID
    from autohive_integrations_sdk import ResultType

    result = await integration.execute_action("get_items", {"board_id": board_id, "limit": 1}, live_context)
    if result.type != ResultType.ACTION:
        pytest.skip(f"get_items failed: {result.result.message}")
    items = result.result.data.get("items", [])
    if not items:
        pytest.skip("No items on this board to test with")
    return items[0]["id"]


# =============================================================================
# GET BOARDS
# =============================================================================


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_boards_returns_list(live_context):
    from autohive_integrations_sdk import ResultType

    result = await integration.execute_action("get_boards", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    data = result.result.data
    assert "boards" in data
    assert isinstance(data["boards"], list)
    assert isinstance(data["board_count"], int)


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_boards_limit_respected(live_context):
    from autohive_integrations_sdk import ResultType

    result = await integration.execute_action("get_boards", {"limit": 2}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert len(result.result.data["boards"]) <= 2


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_boards_item_has_expected_fields(live_context):
    from autohive_integrations_sdk import ResultType

    result = await integration.execute_action("get_boards", {"limit": 1}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    boards = result.result.data["boards"]
    if not boards:
        pytest.skip("No boards on this account")
    board = boards[0]
    assert "id" in board
    assert "name" in board


# =============================================================================
# GET ITEMS
# =============================================================================


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_items_returns_list(live_context):
    from autohive_integrations_sdk import ResultType

    board_id = await _first_board_id(live_context)
    result = await integration.execute_action("get_items", {"board_id": board_id}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    data = result.result.data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["item_count"], int)


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_items_limit_respected(live_context):
    from autohive_integrations_sdk import ResultType

    board_id = await _first_board_id(live_context)
    result = await integration.execute_action("get_items", {"board_id": board_id, "limit": 2}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert len(result.result.data["items"]) <= 2


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_items_item_has_expected_fields(live_context):
    from autohive_integrations_sdk import ResultType

    board_id = await _first_board_id(live_context)
    result = await integration.execute_action("get_items", {"board_id": board_id, "limit": 1}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    items = result.result.data["items"]
    if not items:
        pytest.skip("No items on this board")
    item = items[0]
    assert "id" in item
    assert "name" in item


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_items_pagination_cursor(live_context):
    from autohive_integrations_sdk import ResultType

    board_id = await _first_board_id(live_context)

    # Check if the board has enough items to paginate
    count_result = await integration.execute_action("get_items", {"board_id": board_id, "limit": 50}, live_context)
    if count_result.result.data["item_count"] < 2:
        pytest.skip("Board has fewer than 2 items — can't test pagination")

    result = await integration.execute_action("get_items", {"board_id": board_id, "limit": 1}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data["cursor"] is not None


# =============================================================================
# GET USERS
# =============================================================================


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_users_returns_list(live_context):
    from autohive_integrations_sdk import ResultType

    result = await integration.execute_action("get_users", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    data = result.result.data
    assert "users" in data
    assert isinstance(data["users"], list)
    assert isinstance(data["user_count"], int)


@skip_if_no_token
@pytest.mark.asyncio
async def test_get_users_item_has_expected_fields(live_context):
    from autohive_integrations_sdk import ResultType

    result = await integration.execute_action("get_users", {"limit": 1}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    users = result.result.data["users"]
    if not users:
        pytest.skip("No users on this account")
    user = users[0]
    assert "id" in user
    assert "name" in user
    assert "email" in user


# =============================================================================
# DESTRUCTIVE — create_item, update_item, create_update
# Only run with: pytest -m "integration and destructive"
# Requires MONDAY_TEST_BOARD_ID pointing to a dedicated test board.
# =============================================================================


@pytest.mark.destructive
@skip_if_no_token
@pytest.mark.asyncio
async def test_create_item_lifecycle(live_context):
    """create_item → update_item → create_update lifecycle on a test board."""
    from autohive_integrations_sdk import ResultType

    board_id = TEST_BOARD_ID
    if not board_id:
        pytest.skip("MONDAY_TEST_BOARD_ID not set — required for destructive create_item test")

    # Create
    create_result = await integration.execute_action(
        "create_item",
        {"board_id": board_id, "item_name": "Autohive integration test item"},
        live_context,
    )
    assert create_result.type == ResultType.ACTION, create_result.result.message
    item = create_result.result.data.get("item")
    assert item is not None
    item_id = item["id"]
    assert item_id

    # Update
    update_result = await integration.execute_action(
        "update_item",
        {"board_id": board_id, "item_id": item_id, "column_values": "{}"},
        live_context,
    )
    assert update_result.type == ResultType.ACTION, update_result.result.message
    assert update_result.result.data.get("item") is not None

    # Comment
    comment_result = await integration.execute_action(
        "create_update",
        {"item_id": item_id, "body": "Autohive integration test comment — automated"},
        live_context,
    )
    assert comment_result.type == ResultType.ACTION, comment_result.result.message
    assert comment_result.result.data.get("update") is not None
