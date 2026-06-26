"""
Unit tests for the Monday.com integration using mocked fetch (SDK 2.0.0).

Covers all six actions (get_boards, get_items, create_item, update_item,
create_update, get_users) plus build_headers and execute_graphql_query.
Each action is tested for: happy path, request shape, GraphQL error path
(ActionError), exception path (ActionError), and missing required inputs
(VALIDATION_ERROR).
"""

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType
from unittest.mock import AsyncMock

from monday_com import monday_com as integration, build_headers, execute_graphql_query

pytestmark = pytest.mark.unit

MONDAY_API_URL = "https://api.monday.com/v2"


def gql_ok(data):
    """Wrap a GraphQL response body in a FetchResponse."""
    return FetchResponse(status=200, headers={}, data=data)


def gql_error(message="API Error"):
    return gql_ok({"errors": [{"message": message}]})


# =============================================================================
# BUILD HEADERS
# =============================================================================


def test_build_headers_sets_auth(mock_context):
    headers = build_headers(mock_context)
    assert headers["Authorization"] == "test_token"
    assert headers["Content-Type"] == "application/json"
    assert headers["API-Version"] == "2024-10"


# =============================================================================
# EXECUTE GRAPHQL QUERY
# =============================================================================


@pytest.mark.asyncio
async def test_execute_graphql_query_posts_to_api(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {}}))
    await execute_graphql_query("query {}", {}, mock_context)
    call = mock_context.fetch.call_args
    assert call.args[0] == MONDAY_API_URL
    assert call.kwargs["method"] == "POST"
    assert call.kwargs["json"]["query"] == "query {}"


@pytest.mark.asyncio
async def test_execute_graphql_query_returns_body(mock_context):
    body = {"data": {"boards": []}}
    mock_context.fetch = AsyncMock(return_value=gql_ok(body))
    result = await execute_graphql_query("query {}", {}, mock_context)
    assert result == body


# =============================================================================
# GET BOARDS
# =============================================================================


@pytest.mark.asyncio
async def test_get_boards_success(mock_context):
    boards = [{"id": "1", "name": "Board 1"}, {"id": "2", "name": "Board 2"}]
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"boards": boards}}))
    result = await integration.execute_action("get_boards", {}, mock_context)
    assert result.result.data["boards"] == boards
    assert result.result.data["board_count"] == 2


@pytest.mark.asyncio
async def test_get_boards_empty(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"boards": []}}))
    result = await integration.execute_action("get_boards", {}, mock_context)
    assert result.result.data["boards"] == []
    assert result.result.data["board_count"] == 0


@pytest.mark.asyncio
async def test_get_boards_forwards_pagination(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"boards": []}}))
    await integration.execute_action("get_boards", {"limit": 10, "page": 3, "board_kind": "public"}, mock_context)
    variables = mock_context.fetch.call_args.kwargs["json"]["variables"]
    assert variables["limit"] == 10
    assert variables["page"] == 3
    assert variables["board_kind"] == "public"


@pytest.mark.asyncio
async def test_get_boards_graphql_error_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_error("Unauthorized"))
    result = await integration.execute_action("get_boards", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Unauthorized" in result.result.message


@pytest.mark.asyncio
async def test_get_boards_exception_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("Network error"))
    result = await integration.execute_action("get_boards", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Network error" in result.result.message


# =============================================================================
# GET ITEMS
# =============================================================================


@pytest.mark.asyncio
async def test_get_items_success(mock_context):
    items = [{"id": "10", "name": "Item 1"}, {"id": "11", "name": "Item 2"}]
    mock_context.fetch = AsyncMock(
        return_value=gql_ok({"data": {"boards": [{"items_page": {"items": items, "cursor": "cur_abc"}}]}})
    )
    result = await integration.execute_action("get_items", {"board_id": "123"}, mock_context)
    assert result.result.data["items"] == items
    assert result.result.data["item_count"] == 2
    assert result.result.data["cursor"] == "cur_abc"


@pytest.mark.asyncio
async def test_get_items_no_cursor_on_last_page(mock_context):
    mock_context.fetch = AsyncMock(
        return_value=gql_ok({"data": {"boards": [{"items_page": {"items": [], "cursor": None}}]}})
    )
    result = await integration.execute_action("get_items", {"board_id": "123"}, mock_context)
    assert result.result.data["cursor"] is None


@pytest.mark.asyncio
async def test_get_items_empty_boards(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"boards": []}}))
    result = await integration.execute_action("get_items", {"board_id": "123"}, mock_context)
    assert result.result.data["items"] == []
    assert result.result.data["item_count"] == 0
    assert result.result.data["cursor"] is None


@pytest.mark.asyncio
async def test_get_items_forwards_cursor(mock_context):
    mock_context.fetch = AsyncMock(
        return_value=gql_ok({"data": {"boards": [{"items_page": {"items": [], "cursor": None}}]}})
    )
    await integration.execute_action("get_items", {"board_id": "5", "cursor": "prev_cursor", "limit": 50}, mock_context)
    variables = mock_context.fetch.call_args.kwargs["json"]["variables"]
    assert variables["cursor"] == "prev_cursor"
    assert variables["limit"] == 50


@pytest.mark.asyncio
async def test_get_items_missing_board_id_returns_validation_error(mock_context):
    result = await integration.execute_action("get_items", {}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_items_graphql_error_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_error("Board not found"))
    result = await integration.execute_action("get_items", {"board_id": "999"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Board not found" in result.result.message


@pytest.mark.asyncio
async def test_get_items_exception_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("Timeout"))
    result = await integration.execute_action("get_items", {"board_id": "123"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Timeout" in result.result.message


# =============================================================================
# CREATE ITEM
# =============================================================================


@pytest.mark.asyncio
async def test_create_item_success(mock_context):
    item = {"id": "456", "name": "New Item", "state": "active"}
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"create_item": item}}))
    result = await integration.execute_action("create_item", {"board_id": "123", "item_name": "New Item"}, mock_context)
    assert result.result.data["item"] == item


@pytest.mark.asyncio
async def test_create_item_with_group_and_column_values(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"create_item": {"id": "789"}}}))
    result = await integration.execute_action(
        "create_item",
        {"board_id": "1", "item_name": "Task", "group_id": "grp1", "column_values": '{"status": "Done"}'},
        mock_context,
    )
    assert result.result.data["item"]["id"] == "789"
    variables = mock_context.fetch.call_args.kwargs["json"]["variables"]
    assert variables["group_id"] == "grp1"
    assert variables["column_values"] == '{"status": "Done"}'


@pytest.mark.asyncio
async def test_create_item_missing_required_returns_validation_error(mock_context):
    result = await integration.execute_action("create_item", {"board_id": "1"}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_item_graphql_error_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_error("Invalid board_id"))
    result = await integration.execute_action("create_item", {"board_id": "bad", "item_name": "Test"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Invalid board_id" in result.result.message


@pytest.mark.asyncio
async def test_create_item_exception_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("Connection refused"))
    result = await integration.execute_action("create_item", {"board_id": "1", "item_name": "Test"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Connection refused" in result.result.message


# =============================================================================
# UPDATE ITEM
# =============================================================================


@pytest.mark.asyncio
async def test_update_item_success(mock_context):
    updated = {"id": "456", "name": "Updated", "updated_at": "2024-01-01T00:00:00Z"}
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"change_multiple_column_values": updated}}))
    result = await integration.execute_action(
        "update_item",
        {"board_id": "1", "item_id": "456", "column_values": '{"status": "Done"}'},
        mock_context,
    )
    assert result.result.data["item"] == updated


@pytest.mark.asyncio
async def test_update_item_sends_correct_variables(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"change_multiple_column_values": {"id": "1"}}}))
    await integration.execute_action(
        "update_item",
        {"board_id": "10", "item_id": "20", "column_values": '{"text": "hi"}'},
        mock_context,
    )
    variables = mock_context.fetch.call_args.kwargs["json"]["variables"]
    assert variables["board_id"] == "10"
    assert variables["item_id"] == "20"
    assert variables["column_values"] == '{"text": "hi"}'


@pytest.mark.asyncio
async def test_update_item_missing_required_returns_validation_error(mock_context):
    result = await integration.execute_action("update_item", {"board_id": "1", "item_id": "2"}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_update_item_graphql_error_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_error("Item not found"))
    result = await integration.execute_action(
        "update_item", {"board_id": "1", "item_id": "999", "column_values": "{}"}, mock_context
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Item not found" in result.result.message


@pytest.mark.asyncio
async def test_update_item_exception_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("Connection timeout"))
    result = await integration.execute_action(
        "update_item", {"board_id": "1", "item_id": "2", "column_values": "{}"}, mock_context
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Connection timeout" in result.result.message


# =============================================================================
# CREATE UPDATE (COMMENT)
# =============================================================================


@pytest.mark.asyncio
async def test_create_update_success(mock_context):
    comment = {"id": "789", "body": "Great progress!", "created_at": "2024-01-01T00:00:00Z"}
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"create_update": comment}}))
    result = await integration.execute_action(
        "create_update", {"item_id": "456", "body": "Great progress!"}, mock_context
    )
    assert result.result.data["update"] == comment


@pytest.mark.asyncio
async def test_create_update_sends_correct_variables(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"create_update": {"id": "1"}}}))
    await integration.execute_action("create_update", {"item_id": "42", "body": "Hello!"}, mock_context)
    variables = mock_context.fetch.call_args.kwargs["json"]["variables"]
    assert variables["item_id"] == "42"
    assert variables["body"] == "Hello!"


@pytest.mark.asyncio
async def test_create_update_missing_required_returns_validation_error(mock_context):
    result = await integration.execute_action("create_update", {"item_id": "1"}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_update_graphql_error_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_error("Item not found"))
    result = await integration.execute_action("create_update", {"item_id": "999", "body": "Comment"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Item not found" in result.result.message


@pytest.mark.asyncio
async def test_create_update_exception_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("API unavailable"))
    result = await integration.execute_action("create_update", {"item_id": "1", "body": "Hello"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "API unavailable" in result.result.message


# =============================================================================
# GET USERS
# =============================================================================


@pytest.mark.asyncio
async def test_get_users_success(mock_context):
    users = [{"id": "1", "name": "Alice", "email": "alice@example.com"}, {"id": "2", "name": "Bob"}]
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"users": users}}))
    result = await integration.execute_action("get_users", {}, mock_context)
    assert result.result.data["users"] == users
    assert result.result.data["user_count"] == 2


@pytest.mark.asyncio
async def test_get_users_empty(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"users": []}}))
    result = await integration.execute_action("get_users", {}, mock_context)
    assert result.result.data["users"] == []
    assert result.result.data["user_count"] == 0


@pytest.mark.asyncio
async def test_get_users_forwards_pagination(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_ok({"data": {"users": []}}))
    await integration.execute_action("get_users", {"limit": 50, "page": 2}, mock_context)
    variables = mock_context.fetch.call_args.kwargs["json"]["variables"]
    assert variables["limit"] == 50
    assert variables["page"] == 2


@pytest.mark.asyncio
async def test_get_users_graphql_error_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(return_value=gql_error("Unauthorized"))
    result = await integration.execute_action("get_users", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Unauthorized" in result.result.message


@pytest.mark.asyncio
async def test_get_users_exception_returns_action_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("API unavailable"))
    result = await integration.execute_action("get_users", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "API unavailable" in result.result.message
