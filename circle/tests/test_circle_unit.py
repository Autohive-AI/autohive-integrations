from unittest.mock import AsyncMock, MagicMock
import pytest
from autohive_integrations_sdk import ResultType
from circle.circle import circle

pytestmark = pytest.mark.unit


def _fetch_result(data):
    r = MagicMock()
    r.data = data
    return r


# ---- Post Actions ----


@pytest.mark.asyncio
async def test_search_posts(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"records": [{"id": 1}], "count": 1}))
    result = await circle.execute_action("search_posts", {}, mock_context)
    assert result.result.data["count"] == 1
    assert len(result.result.data["posts"]) == 1


@pytest.mark.asyncio
async def test_search_posts_with_filters(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"records": [], "count": 0}))
    await circle.execute_action("search_posts", {"query": "hello", "space_id": "5", "per_page": 5}, mock_context)
    params = mock_context.fetch.call_args[1]["params"]
    assert params["query"] == "hello"
    assert params["per_page"] == 5


@pytest.mark.asyncio
async def test_get_post(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 42, "name": "Test Post"}))
    result = await circle.execute_action("get_post", {"post_id": "42"}, mock_context)
    assert result.result.data["post"]["id"] == 42
    assert "posts/42" in mock_context.fetch.call_args[0][0]


@pytest.mark.asyncio
async def test_create_post(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 10, "name": "New Post"}))
    result = await circle.execute_action(
        "create_post",
        {"space_id": 1, "name": "New Post", "body": "Hello **world**"},
        mock_context,
    )
    assert result.result.data["post"]["id"] == 10
    body = mock_context.fetch.call_args[1]["json"]
    assert "tiptap_body" in body
    assert body["status"] == "published"


@pytest.mark.asyncio
async def test_create_post_with_user_email(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 11}))
    await circle.execute_action(
        "create_post",
        {"space_id": 1, "name": "Post", "body": "Content", "user_email": "user@example.com"},
        mock_context,
    )
    body = mock_context.fetch.call_args[1]["json"]
    assert body["user_email"] == "user@example.com"


@pytest.mark.asyncio
async def test_update_post(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 5, "name": "Updated"}))
    result = await circle.execute_action("update_post", {"post_id": "5", "name": "Updated"}, mock_context)
    assert result.result.data["post"]["name"] == "Updated"
    assert "posts/5" in mock_context.fetch.call_args[0][0]


# ---- Member Actions ----


@pytest.mark.asyncio
async def test_search_member_by_email(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 99, "email": "user@example.com"}))
    result = await circle.execute_action("search_member_by_email", {"email": "user@example.com"}, mock_context)
    assert result.result.data["member"]["id"] == 99
    params = mock_context.fetch.call_args[1]["params"]
    assert params["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_list_members(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"records": [{"id": 1}, {"id": 2}], "count": 2}))
    result = await circle.execute_action("list_members", {}, mock_context)
    assert result.result.data["count"] == 2
    assert len(result.result.data["members"]) == 2


@pytest.mark.asyncio
async def test_get_member(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 77, "name": "Alice"}))
    result = await circle.execute_action("get_member", {"member_id": "77"}, mock_context)
    assert result.result.data["member"]["id"] == 77
    assert "community_members/77" in mock_context.fetch.call_args[0][0]


# ---- Space Actions ----


@pytest.mark.asyncio
async def test_search_spaces(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"records": [{"id": 3}], "count": 1}))
    result = await circle.execute_action("search_spaces", {"query": "general"}, mock_context)
    assert result.result.data["spaces"][0]["id"] == 3


@pytest.mark.asyncio
async def test_get_space(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 3, "name": "General"}))
    result = await circle.execute_action("get_space", {"space_id": "3"}, mock_context)
    assert result.result.data["space"]["name"] == "General"
    assert "spaces/3" in mock_context.fetch.call_args[0][0]


# ---- Event Actions ----


@pytest.mark.asyncio
async def test_search_events(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"records": [{"id": 7}], "count": 1}))
    result = await circle.execute_action("search_events", {"time_filter": "upcoming"}, mock_context)
    assert result.result.data["events"][0]["id"] == 7


@pytest.mark.asyncio
async def test_get_event(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 7, "name": "Webinar"}))
    result = await circle.execute_action("get_event", {"event_id": "7"}, mock_context)
    assert result.result.data["event"]["name"] == "Webinar"
    assert "events/7" in mock_context.fetch.call_args[0][0]


# ---- Comment Actions ----


@pytest.mark.asyncio
async def test_create_comment(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 20, "body": "Great post!"}))
    result = await circle.execute_action("create_comment", {"post_id": "42", "body": "Great post!"}, mock_context)
    assert result.result.data["comment"]["id"] == 20
    body = mock_context.fetch.call_args[1]["json"]
    assert body["post_id"] == "42"


@pytest.mark.asyncio
async def test_get_post_comments(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"records": [{"id": 1}], "count": 1}))
    result = await circle.execute_action("get_post_comments", {"post_id": "42"}, mock_context)
    assert result.result.data["count"] == 1
    params = mock_context.fetch.call_args[1]["params"]
    assert params["post_id"] == "42"


# ---- Community Actions ----


@pytest.mark.asyncio
async def test_get_community_info(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 1, "name": "My Community"}))
    result = await circle.execute_action("get_community_info", {}, mock_context)
    assert result.result.data["community"]["name"] == "My Community"
    assert mock_context.fetch.call_args[0][0].endswith("/community")


# ---- Member Tag Actions ----


@pytest.mark.asyncio
async def test_add_member_tags(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 1}))
    result = await circle.execute_action(
        "add_member_tags",
        {"user_email": "user@example.com", "member_tag_ids": [10, 20]},
        mock_context,
    )
    assert result.result.data["tags_added"] == 2
    assert mock_context.fetch.call_count == 2


@pytest.mark.asyncio
async def test_remove_member_tags(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({}))
    result = await circle.execute_action(
        "remove_member_tags",
        {"user_email": "user@example.com", "member_tag_ids": [10, 20]},
        mock_context,
    )
    assert result.result.data["tags_removed"] == 2
    assert mock_context.fetch.call_count == 2


# ---- Space Group Actions ----


@pytest.mark.asyncio
async def test_add_member_to_space_groups(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 1}))
    result = await circle.execute_action(
        "add_member_to_space_groups",
        {"email": "user@example.com", "space_group_ids": [5]},
        mock_context,
    )
    assert result.result.data["groups_added"] == 1


@pytest.mark.asyncio
async def test_remove_member_from_space_groups(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({}))
    result = await circle.execute_action(
        "remove_member_from_space_groups",
        {"email": "user@example.com", "space_group_ids": [5, 6]},
        mock_context,
    )
    assert result.result.data["groups_removed"] == 2


# ---- List + Access Group Actions ----


@pytest.mark.asyncio
async def test_list_tags(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"records": [{"id": 1, "name": "vip"}], "count": 1}))
    result = await circle.execute_action("list_tags", {}, mock_context)
    assert result.result.data["tags"][0]["name"] == "vip"
    params = mock_context.fetch.call_args[1]["params"]
    assert params["per_page"] == 100


@pytest.mark.asyncio
async def test_list_space_groups(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"records": [{"id": 3}], "count": 1}))
    result = await circle.execute_action("list_space_groups", {}, mock_context)
    assert result.result.data["space_groups"][0]["id"] == 3


@pytest.mark.asyncio
async def test_list_access_groups(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"records": [{"id": 2}], "count": 1}))
    result = await circle.execute_action("list_access_groups", {}, mock_context)
    assert result.result.data["access_groups"][0]["id"] == 2


@pytest.mark.asyncio
async def test_add_member_to_access_groups(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 1}))
    result = await circle.execute_action(
        "add_member_to_access_groups",
        {"email": "user@example.com", "access_group_ids": [2, 3]},
        mock_context,
    )
    assert result.result.data["groups_added"] == 2
    assert mock_context.fetch.call_count == 2


@pytest.mark.asyncio
async def test_remove_member_from_access_groups(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({}))
    result = await circle.execute_action(
        "remove_member_from_access_groups",
        {"email": "user@example.com", "access_group_ids": [2]},
        mock_context,
    )
    assert result.result.data["groups_removed"] == 1


@pytest.mark.asyncio
async def test_api_error_in_response(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"error": "Not found"}))
    result = await circle.execute_action("get_community_info", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "API request failed" in result.result.message


@pytest.mark.asyncio
async def test_missing_api_token(mock_context):
    mock_context.auth = {"auth_type": "Custom", "credentials": {}}
    result = await circle.execute_action("list_tags", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Circle API token is required" in result.result.message
