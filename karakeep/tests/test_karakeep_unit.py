from unittest.mock import AsyncMock
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType
from karakeep.karakeep import karakeep

pytestmark = pytest.mark.unit


def _fetch_result(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


# ---- create_bookmark ----


@pytest.mark.asyncio
async def test_create_bookmark(mock_context):
    mock_context.fetch = AsyncMock(
        return_value=_fetch_result({"id": "bk_123", "url": "https://example.com/a", "title": "A"}, status=201)
    )
    result = await karakeep.execute_action(
        "create_bookmark",
        {"url": "https://example.com/a", "title": "A", "note": "A note"},
        mock_context,
    )
    assert result.result.data["bookmark_id"] == "bk_123"
    assert result.result.data["bookmark"]["url"] == "https://example.com/a"
    assert result.result.data["already_existed"] is False
    url = mock_context.fetch.call_args[0][0]
    assert url == "https://karakeep.test/api/v1/bookmarks"
    kwargs = mock_context.fetch.call_args[1]
    assert kwargs["method"] == "POST"
    assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
    body = kwargs["json"]
    assert body["type"] == "link"
    assert body["url"] == "https://example.com/a"
    assert body["title"] == "A"
    assert body["note"] == "A note"


@pytest.mark.asyncio
async def test_create_bookmark_omits_empty_optional_fields(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_1"}))
    await karakeep.execute_action("create_bookmark", {"url": "https://example.com/a", "title": ""}, mock_context)
    body = mock_context.fetch.call_args[1]["json"]
    assert "title" not in body
    assert "note" not in body
    assert "summary" not in body


@pytest.mark.asyncio
async def test_create_bookmark_no_id_in_response(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"something": "else"}))
    result = await karakeep.execute_action("create_bookmark", {"url": "https://example.com/a"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_create_bookmark_already_existed(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_existing"}, status=200))
    result = await karakeep.execute_action("create_bookmark", {"url": "https://example.com/a"}, mock_context)
    assert result.result.data["bookmark_id"] == "bk_existing"
    assert result.result.data["already_existed"] is True


# ---- attach_tags ----


@pytest.mark.asyncio
async def test_attach_tags(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"attached": ["tag_a", "tag_b"]}))
    result = await karakeep.execute_action(
        "attach_tags",
        {"bookmark_id": "bk_1", "tags": ["topic:x", "sentiment:y"]},
        mock_context,
    )
    assert result.result.data["attached"] == ["tag_a", "tag_b"]
    assert result.result.data["count"] == 2
    url = mock_context.fetch.call_args[0][0]
    assert url == "https://karakeep.test/api/v1/bookmarks/bk_1/tags"
    body = mock_context.fetch.call_args[1]["json"]
    assert body == {"tags": [{"tagName": "topic:x"}, {"tagName": "sentiment:y"}]}


@pytest.mark.asyncio
async def test_attach_tags_empty_list_noop(mock_context):
    result = await karakeep.execute_action("attach_tags", {"bookmark_id": "bk_1", "tags": []}, mock_context)
    assert result.result.data == {"attached": [], "count": 0}
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_attach_tags_strips_whitespace(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"attached": []}))
    await karakeep.execute_action(
        "attach_tags",
        {"bookmark_id": "bk_1", "tags": ["  topic:x  ", "", "  ", "sentiment:y"]},
        mock_context,
    )
    body = mock_context.fetch.call_args[1]["json"]
    assert body == {"tags": [{"tagName": "topic:x"}, {"tagName": "sentiment:y"}]}


# ---- search_bookmarks ----


@pytest.mark.asyncio
async def test_search_bookmarks(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": [{"id": "bk_1"}, {"id": "bk_2"}]}))
    result = await karakeep.execute_action(
        "search_bookmarks", {"query": "https://example.com/a", "limit": 5}, mock_context
    )
    assert result.result.data["count"] == 2
    assert result.result.data["next_cursor"] is None
    url = mock_context.fetch.call_args[0][0]
    assert url == "https://karakeep.test/api/v1/bookmarks/search"
    kwargs = mock_context.fetch.call_args[1]
    assert kwargs["method"] == "GET"
    assert kwargs["params"] == {"q": "https://example.com/a", "limit": 5}


@pytest.mark.asyncio
async def test_search_bookmarks_default_limit(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": []}))
    await karakeep.execute_action("search_bookmarks", {"query": "x"}, mock_context)
    assert mock_context.fetch.call_args[1]["params"]["limit"] == 20


# ---- get_bookmark ----


@pytest.mark.asyncio
async def test_get_bookmark(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_9", "url": "https://example.com/x"}))
    result = await karakeep.execute_action("get_bookmark", {"bookmark_id": "bk_9"}, mock_context)
    assert result.result.data["bookmark"]["url"] == "https://example.com/x"
    assert "bk_9" in mock_context.fetch.call_args[0][0]


# ---- create_tag / list_tags / list_bookmarks / get_tag_bookmarks ----


@pytest.mark.asyncio
async def test_create_tag(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "tag_1", "name": "AI"}))
    result = await karakeep.execute_action("create_tag", {"name": "  AI  "}, mock_context)
    assert result.result.data["tag_id"] == "tag_1"
    assert result.result.data["name"] == "AI"
    url = mock_context.fetch.call_args[0][0]
    assert url == "https://karakeep.test/api/v1/tags"
    kwargs = mock_context.fetch.call_args[1]
    assert kwargs["method"] == "POST"
    assert kwargs["json"] == {"name": "AI"}


@pytest.mark.asyncio
async def test_create_tag_empty_name(mock_context):
    result = await karakeep.execute_action("create_tag", {"name": "   "}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_list_tags(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"tags": [{"id": "t1", "name": "AI"}]}))
    result = await karakeep.execute_action("list_tags", {"name_contains": "AI", "limit": 10}, mock_context)
    assert result.result.data["count"] == 1
    assert result.result.data["tags"][0]["name"] == "AI"
    url = mock_context.fetch.call_args[0][0]
    assert url == "https://karakeep.test/api/v1/tags"
    assert mock_context.fetch.call_args[1]["params"] == {"limit": 10, "nameContains": "AI"}


@pytest.mark.asyncio
async def test_list_bookmarks(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": [{"id": "bk_1"}]}))
    result = await karakeep.execute_action("list_bookmarks", {"favourited": True, "limit": 5}, mock_context)
    assert result.result.data["count"] == 1
    url = mock_context.fetch.call_args[0][0]
    assert url == "https://karakeep.test/api/v1/bookmarks"
    assert mock_context.fetch.call_args[1]["params"] == {"limit": 5, "favourited": "true"}


@pytest.mark.asyncio
async def test_list_bookmarks_clamps_limit(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": []}))
    await karakeep.execute_action("list_bookmarks", {"limit": 500}, mock_context)
    assert mock_context.fetch.call_args[1]["params"]["limit"] == 100


@pytest.mark.asyncio
async def test_list_tags_without_name_filter(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"tags": []}))
    await karakeep.execute_action("list_tags", {}, mock_context)
    params = mock_context.fetch.call_args[1]["params"]
    assert params == {"limit": 20}
    assert "nameContains" not in params


@pytest.mark.asyncio
async def test_search_bookmarks_passes_cursor(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": [], "nextCursor": None}))
    await karakeep.execute_action("search_bookmarks", {"query": "x", "cursor": "abc"}, mock_context)
    assert mock_context.fetch.call_args[1]["params"]["cursor"] == "abc"


@pytest.mark.asyncio
async def test_create_bookmark_flags(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_1"}, status=201))
    await karakeep.execute_action(
        "create_bookmark",
        {"url": "https://example.com/a", "archived": False, "favourited": True},
        mock_context,
    )
    body = mock_context.fetch.call_args[1]["json"]
    assert body["archived"] is False
    assert body["favourited"] is True


@pytest.mark.asyncio
async def test_get_tag_bookmarks(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": [{"id": "bk_1"}, {"id": "bk_2"}]}))
    result = await karakeep.execute_action("get_tag_bookmarks", {"tag_id": "tag_1", "limit": 5}, mock_context)
    assert result.result.data["count"] == 2
    url = mock_context.fetch.call_args[0][0]
    assert url == "https://karakeep.test/api/v1/tags/tag_1/bookmarks"
    assert mock_context.fetch.call_args[1]["params"]["limit"] == 5


# ---- auth validation ----


@pytest.mark.asyncio
async def test_missing_base_url(mock_context):
    mock_context.auth = {"auth_type": "Custom", "credentials": {"api_key": "k"}}
    result = await karakeep.execute_action("create_bookmark", {"url": "https://example.com/a"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_missing_api_key(mock_context):
    mock_context.auth = {
        "auth_type": "Custom",
        "credentials": {"base_url": "https://karakeep.test"},
    }
    result = await karakeep.execute_action("create_bookmark", {"url": "https://example.com/a"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_create_bookmark_summary(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_1"}, status=201))
    await karakeep.execute_action(
        "create_bookmark",
        {"url": "https://example.com/a", "summary": "A summary"},
        mock_context,
    )
    assert mock_context.fetch.call_args[1]["json"]["summary"] == "A summary"


@pytest.mark.asyncio
async def test_create_tag_no_id_in_response(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"name": "AI"}))
    result = await karakeep.execute_action("create_tag", {"name": "AI"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_list_bookmarks_archived_false(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": []}))
    await karakeep.execute_action("list_bookmarks", {"archived": False, "limit": 5}, mock_context)
    assert mock_context.fetch.call_args[1]["params"] == {"limit": 5, "archived": "false"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "inputs"),
    [
        ("attach_tags", {"bookmark_id": "bk_1", "tags": ["a"]}),
        ("search_bookmarks", {"query": "x"}),
        ("get_bookmark", {"bookmark_id": "bk_1"}),
        ("list_tags", {}),
        ("list_bookmarks", {}),
        ("get_tag_bookmarks", {"tag_id": "tag_1"}),
    ],
)
async def test_fetch_errors_return_action_error(mock_context, action, inputs):
    mock_context.fetch = AsyncMock(side_effect=RuntimeError("upstream failed"))
    result = await karakeep.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "upstream failed" in result.result.message
    assert "test_api_key" not in result.result.message


@pytest.mark.asyncio
async def test_rejects_non_http_base_url(mock_context):
    mock_context.auth = {
        "auth_type": "Custom",
        "credentials": {"base_url": "file:///tmp", "api_key": "test_api_key"},  # nosec B105
    }
    result = await karakeep.execute_action("list_tags", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_accepts_http_host_port_base_url(mock_context):
    mock_context.auth = {
        "auth_type": "Custom",
        "credentials": {"base_url": "http://127.0.0.1:3000", "api_key": "test_api_key"},  # nosec B105
    }
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"tags": []}))
    await karakeep.execute_action("list_tags", {}, mock_context)
    assert mock_context.fetch.call_args[0][0] == "http://127.0.0.1:3000/api/v1/tags"


@pytest.mark.asyncio
async def test_path_ids_are_url_encoded(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_1"}))
    await karakeep.execute_action("get_bookmark", {"bookmark_id": "a/b"}, mock_context)
    assert mock_context.fetch.call_args[0][0].endswith("/api/v1/bookmarks/a%2Fb")
