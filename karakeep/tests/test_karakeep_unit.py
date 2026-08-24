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
        {
            "url": "https://example.com/a",
            "title": "A",
            "note": "A note",
            "summary": "A summary",
            "archived": False,
            "favourited": True,
        },
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
    assert body == {
        "type": "link",
        "url": "https://example.com/a",
        "title": "A",
        "note": "A note",
        "summary": "A summary",
        "archived": False,
        "favourited": True,
    }


@pytest.mark.asyncio
async def test_create_bookmark_omits_empty_optional_fields(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_1"}))
    await karakeep.execute_action("create_bookmark", {"url": "https://example.com/a", "title": ""}, mock_context)
    body = mock_context.fetch.call_args[1]["json"]
    assert body == {"type": "link", "url": "https://example.com/a"}


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


@pytest.mark.asyncio
async def test_create_bookmark_link_missing_url(mock_context):
    result = await karakeep.execute_action("create_bookmark", {"type": "link"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_create_bookmark_text_type(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_t1"}, status=201))
    result = await karakeep.execute_action(
        "create_bookmark",
        {"type": "text", "text": "A note snippet", "source_url": "https://ex.com"},
        mock_context,
    )
    assert result.result.data["bookmark_id"] == "bk_t1"
    assert result.result.data["already_existed"] is False
    body = mock_context.fetch.call_args[1]["json"]
    assert body == {"type": "text", "text": "A note snippet", "sourceUrl": "https://ex.com"}


@pytest.mark.asyncio
async def test_create_bookmark_text_200_not_already_existed(mock_context):
    """200 dedup semantics apply to link bookmarks only."""
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_t1"}, status=200))
    result = await karakeep.execute_action("create_bookmark", {"type": "text", "text": "note"}, mock_context)
    assert result.result.data["already_existed"] is False


@pytest.mark.asyncio
async def test_create_bookmark_asset_type(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_a1"}, status=201))
    await karakeep.execute_action(
        "create_bookmark",
        {"type": "asset", "asset_type": "pdf", "asset_id": "asset_123", "file_name": "doc.pdf"},
        mock_context,
    )
    body = mock_context.fetch.call_args[1]["json"]
    assert body == {"type": "asset", "assetType": "pdf", "assetId": "asset_123", "fileName": "doc.pdf"}


@pytest.mark.asyncio
async def test_create_bookmark_asset_source_url(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_a2"}, status=201))
    await karakeep.execute_action(
        "create_bookmark",
        {
            "type": "asset",
            "asset_type": "image",
            "asset_id": "asset_img",
            "source_url": "https://ex.com/pic.png",
        },
        mock_context,
    )
    body = mock_context.fetch.call_args[1]["json"]
    assert body == {
        "type": "asset",
        "assetType": "image",
        "assetId": "asset_img",
        "sourceUrl": "https://ex.com/pic.png",
    }


@pytest.mark.asyncio
async def test_create_bookmark_text_missing_text_field(mock_context):
    result = await karakeep.execute_action("create_bookmark", {"type": "text"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_create_bookmark_asset_missing_asset_type(mock_context):
    result = await karakeep.execute_action(
        "create_bookmark",
        {"type": "asset", "asset_id": "asset_1"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_create_bookmark_asset_missing_asset_id(mock_context):
    result = await karakeep.execute_action(
        "create_bookmark",
        {"type": "asset", "asset_type": "pdf"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_create_bookmark_invalid_type(mock_context):
    result = await karakeep.execute_action("create_bookmark", {"type": "video", "url": "x"}, mock_context)
    assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)
    mock_context.fetch.assert_not_called()


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
async def test_attach_tags_by_id_only(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"attached": ["t1"]}))
    await karakeep.execute_action("attach_tags", {"bookmark_id": "bk_1", "tag_ids": ["existing_1"]}, mock_context)
    body = mock_context.fetch.call_args[1]["json"]
    assert body == {"tags": [{"tagId": "existing_1"}]}


@pytest.mark.asyncio
async def test_attach_tags_by_id_and_name(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"attached": ["t1", "t2"]}))
    await karakeep.execute_action(
        "attach_tags",
        {"bookmark_id": "bk_1", "tags": ["new-tag"], "tag_ids": ["existing_1"], "attached_by": "ai"},
        mock_context,
    )
    body = mock_context.fetch.call_args[1]["json"]
    assert body == {
        "tags": [
            {"tagName": "new-tag", "attachedBy": "ai"},
            {"tagId": "existing_1", "attachedBy": "ai"},
        ]
    }


@pytest.mark.asyncio
async def test_attach_tags_empty_list_noop(mock_context):
    result = await karakeep.execute_action("attach_tags", {"bookmark_id": "bk_1", "tags": []}, mock_context)
    assert result.result.data == {"attached": [], "count": 0}
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_attach_tags_no_tags_or_ids_noop(mock_context):
    result = await karakeep.execute_action("attach_tags", {"bookmark_id": "bk_1"}, mock_context)
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


@pytest.mark.asyncio
async def test_search_bookmarks_passes_cursor(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": [], "nextCursor": None}))
    await karakeep.execute_action("search_bookmarks", {"query": "x", "cursor": "abc"}, mock_context)
    assert mock_context.fetch.call_args[1]["params"]["cursor"] == "abc"


@pytest.mark.asyncio
async def test_search_bookmarks_semantic_mode(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": []}))
    await karakeep.execute_action(
        "search_bookmarks",
        {"query": "AI agents", "search_mode": "semantic", "sort_order": "relevance", "include_content": True},
        mock_context,
    )
    params = mock_context.fetch.call_args[1]["params"]
    assert params["searchMode"] == "semantic"
    assert params["sortOrder"] == "relevance"
    assert params["includeContent"] == "true"


@pytest.mark.asyncio
async def test_search_bookmarks_include_content_false(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": []}))
    await karakeep.execute_action("search_bookmarks", {"query": "x", "include_content": False}, mock_context)
    assert mock_context.fetch.call_args[1]["params"]["includeContent"] == "false"


# ---- get_bookmark ----


@pytest.mark.asyncio
async def test_get_bookmark(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_9", "url": "https://example.com/x"}))
    result = await karakeep.execute_action(
        "get_bookmark", {"bookmark_id": "bk_9", "include_content": True}, mock_context
    )
    assert result.result.data["bookmark"]["url"] == "https://example.com/x"
    assert mock_context.fetch.call_args[0][0].endswith("/api/v1/bookmarks/bk_9")
    assert mock_context.fetch.call_args[1]["params"]["includeContent"] == "true"


@pytest.mark.asyncio
async def test_get_bookmark_omits_include_content_when_unset(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_9"}))
    await karakeep.execute_action("get_bookmark", {"bookmark_id": "bk_9"}, mock_context)
    assert mock_context.fetch.call_args[1]["params"] == {}


@pytest.mark.asyncio
async def test_path_ids_are_url_encoded(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": "bk_1"}))
    await karakeep.execute_action("get_bookmark", {"bookmark_id": "a/b"}, mock_context)
    assert mock_context.fetch.call_args[0][0].endswith("/api/v1/bookmarks/a%2Fb")


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
async def test_create_tag_no_id_in_response(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"name": "AI"}))
    result = await karakeep.execute_action("create_tag", {"name": "AI"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_list_tags(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"tags": [{"id": "t1", "name": "AI"}]}))
    result = await karakeep.execute_action(
        "list_tags", {"name_contains": "AI", "limit": 10, "sort": "name", "attached_by": "human"}, mock_context
    )
    assert result.result.data["count"] == 1
    assert result.result.data["tags"][0]["name"] == "AI"
    url = mock_context.fetch.call_args[0][0]
    assert url == "https://karakeep.test/api/v1/tags"
    assert mock_context.fetch.call_args[1]["params"] == {
        "limit": 10,
        "nameContains": "AI",
        "sort": "name",
        "attachedBy": "human",
    }


@pytest.mark.asyncio
async def test_list_tags_passes_cursor(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"tags": []}))
    await karakeep.execute_action("list_tags", {"cursor": "tag-page-2"}, mock_context)
    assert mock_context.fetch.call_args[1]["params"]["cursor"] == "tag-page-2"


@pytest.mark.asyncio
async def test_list_tags_without_name_filter(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"tags": []}))
    await karakeep.execute_action("list_tags", {}, mock_context)
    params = mock_context.fetch.call_args[1]["params"]
    assert params == {"limit": 20}
    assert "nameContains" not in params


@pytest.mark.asyncio
async def test_list_tags_clamps_limit(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"tags": []}))
    await karakeep.execute_action("list_tags", {"limit": 5000}, mock_context)
    assert mock_context.fetch.call_args[1]["params"]["limit"] == 1000


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filter_key", "filter_value", "expected_param"),
    [
        ("favourited", True, {"favourited": "true"}),
        ("archived", False, {"archived": "false"}),
    ],
)
async def test_list_bookmarks_filters(mock_context, filter_key, filter_value, expected_param):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": [{"id": "bk_1"}]}))
    result = await karakeep.execute_action(
        "list_bookmarks", {filter_key: filter_value, "limit": 5, "sort_order": "asc"}, mock_context
    )
    assert result.result.data["count"] == 1
    assert mock_context.fetch.call_args[0][0] == "https://karakeep.test/api/v1/bookmarks"
    assert mock_context.fetch.call_args[1]["params"] == {"limit": 5, "sortOrder": "asc", **expected_param}


@pytest.mark.asyncio
async def test_list_bookmarks_clamps_limit(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": []}))
    await karakeep.execute_action("list_bookmarks", {"limit": 500}, mock_context)
    assert mock_context.fetch.call_args[1]["params"]["limit"] == 100


@pytest.mark.asyncio
async def test_list_bookmarks_include_content_and_cursor(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": []}))
    await karakeep.execute_action(
        "list_bookmarks",
        {"cursor": "page-2", "include_content": False},
        mock_context,
    )
    params = mock_context.fetch.call_args[1]["params"]
    assert params["cursor"] == "page-2"
    assert params["includeContent"] == "false"


@pytest.mark.asyncio
async def test_paged_response_maps_next_cursor(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": [{"id": "bk_1"}], "nextCursor": "page-2"}))
    result = await karakeep.execute_action("list_bookmarks", {"limit": 1}, mock_context)
    assert result.result.data["next_cursor"] == "page-2"


@pytest.mark.asyncio
async def test_get_tag_bookmarks(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": [{"id": "bk_1"}, {"id": "bk_2"}]}))
    result = await karakeep.execute_action(
        "get_tag_bookmarks",
        {"tag_id": "tag_1", "limit": 5, "include_content": True, "sort_order": "asc"},
        mock_context,
    )
    assert result.result.data["count"] == 2
    url = mock_context.fetch.call_args[0][0]
    assert url == "https://karakeep.test/api/v1/tags/tag_1/bookmarks"
    params = mock_context.fetch.call_args[1]["params"]
    assert params == {"limit": 5, "includeContent": "true", "sortOrder": "asc"}


@pytest.mark.asyncio
async def test_get_tag_bookmarks_passes_cursor(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"bookmarks": []}))
    await karakeep.execute_action("get_tag_bookmarks", {"tag_id": "tag_1", "cursor": "next-page"}, mock_context)
    assert mock_context.fetch.call_args[1]["params"]["cursor"] == "next-page"


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
async def test_rejects_http_base_url(mock_context):
    """http is refused: the API key must not travel over cleartext."""
    mock_context.auth = {
        "auth_type": "Custom",
        "credentials": {"base_url": "http://127.0.0.1:3000", "api_key": "test_api_key"},  # nosec B105
    }
    result = await karakeep.execute_action("list_tags", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_accepts_https_base_url(mock_context):
    mock_context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "base_url": "https://cloud.karakeep.app",
            "api_key": "test_api_key",  # nosec B105
        },
    }
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"tags": []}))
    await karakeep.execute_action("list_tags", {}, mock_context)
    assert mock_context.fetch.call_args[0][0] == "https://cloud.karakeep.app/api/v1/tags"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "inputs"),
    [
        ("create_bookmark", {"url": "https://example.com/a"}),
        ("attach_tags", {"bookmark_id": "bk_1", "tags": ["a"]}),
        ("search_bookmarks", {"query": "x"}),
        ("get_bookmark", {"bookmark_id": "bk_1"}),
        ("create_tag", {"name": "AI"}),
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
