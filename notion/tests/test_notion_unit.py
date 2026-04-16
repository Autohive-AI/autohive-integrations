"""
Unit tests for Notion integration.

Migrated from test_notion_integration.py (asyncio.run style) to proper pytest.
Covers all handlers with mocked context.fetch calls.
"""

import json
import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock

# Add parent and tests directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from notion.notion import (
    NOTION_API_VERSION,
    NotionGetCommentsHandler,
    NotionSearchHandler,
    NotionGetPageHandler,
    NotionCreatePageHandler,
    NotionCreateCommentHandler,
    NotionGetBlockChildrenHandler,
    NotionUpdateBlockHandler,
    NotionDeleteBlockHandler,
    NotionUpdatePageHandler,
    notion as notion_integration,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},
    }  # nosec B105
    return ctx


NOTION_HEADERS = {"Notion-Version": NOTION_API_VERSION}
NOTION_HEADERS_JSON = {
    "Notion-Version": NOTION_API_VERSION,
    "Content-Type": "application/json",
}

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")


# ---------------------------------------------------------------------------
# Config validation (migrated from old tests)
# ---------------------------------------------------------------------------


class TestConfigValidation:
    """Verify config.json actions match registered handlers."""

    def test_actions_match_handlers(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        defined_actions = set(config.get("actions", {}).keys())
        registered_actions = set(notion_integration._action_handlers.keys())

        missing_handlers = defined_actions - registered_actions
        extra_handlers = registered_actions - defined_actions

        assert not missing_handlers, f"Missing handlers for actions: {missing_handlers}"
        assert not extra_handlers, f"Extra handlers without config: {extra_handlers}"

    def test_get_comments_action_config(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        action_config = config["actions"]["get_notion_comments"]

        assert action_config["display_name"] == "Get Comments"
        assert "Retrieve comments" in action_config["description"]

        input_schema = action_config["input_schema"]
        assert "block_id" in input_schema["properties"]
        assert "page_size" in input_schema["properties"]
        assert "start_cursor" in input_schema["properties"]
        assert input_schema["required"] == ["block_id"]

        output_schema = action_config["output_schema"]
        assert "comments" in output_schema["properties"]
        assert "next_cursor" in output_schema["properties"]
        assert "has_more" in output_schema["properties"]

    def test_get_comments_pagination_schema(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        props = config["actions"]["get_notion_comments"]["input_schema"]["properties"]

        page_size = props["page_size"]
        assert page_size["type"] == "integer"
        assert page_size["minimum"] == 1
        assert page_size["maximum"] == 100

        start_cursor = props["start_cursor"]
        assert start_cursor["type"] == "string"

    def test_create_and_get_comment_actions_complement(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        actions = config["actions"]
        assert "create_notion_comment" in actions
        assert "get_notion_comments" in actions

        create_output = actions["create_notion_comment"]["output_schema"]["properties"]
        assert "id" in create_output

        get_output = actions["get_notion_comments"]["output_schema"]["properties"]
        assert "comments" in get_output

    def test_new_actions_defined(self):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        actions = config["actions"]
        for action_name in [
            "update_notion_block",
            "delete_notion_block",
            "update_notion_page",
            "get_notion_comments",
        ]:
            assert action_name in actions, f"{action_name} not in config.json"
            action_config = actions[action_name]
            assert "display_name" in action_config
            assert "description" in action_config
            assert "input_schema" in action_config
            assert "output_schema" in action_config


# ---------------------------------------------------------------------------
# GetComments handler (migrated from old tests)
# ---------------------------------------------------------------------------


class TestGetComments:
    """Tests for NotionGetCommentsHandler — migrated from old test suite."""

    @pytest.mark.asyncio
    async def test_basic(self, mock_context):
        handler = NotionGetCommentsHandler()

        mock_context.fetch.return_value = {
            "object": "list",
            "results": [
                {
                    "id": "comment-123",
                    "discussion_id": "disc-456",
                    "created_time": "2024-01-15T10:00:00.000Z",
                    "rich_text": [{"type": "text", "text": {"content": "Test comment"}}],
                    "parent": {"type": "page_id", "page_id": "page-789"},
                }
            ],
            "next_cursor": None,
            "has_more": False,
        }

        result = await handler.execute({"block_id": "page-789"}, mock_context)

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/comments",
            method="GET",
            headers=NOTION_HEADERS,
            params={"block_id": "page-789"},
        )

        assert len(result.data["comments"]) == 1
        assert result.data["comments"][0]["id"] == "comment-123"
        assert result.data["has_more"] is False

    @pytest.mark.asyncio
    async def test_with_pagination(self, mock_context):
        handler = NotionGetCommentsHandler()

        mock_context.fetch.return_value = {
            "object": "list",
            "results": [{"id": "comment-1"}, {"id": "comment-2"}],
            "next_cursor": "cursor-abc",
            "has_more": True,
        }

        result = await handler.execute(
            {"block_id": "page-123", "page_size": 2, "start_cursor": "prev-cursor"},
            mock_context,
        )

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/comments",
            method="GET",
            headers=NOTION_HEADERS,
            params={
                "block_id": "page-123",
                "page_size": 2,
                "start_cursor": "prev-cursor",
            },
        )

        assert result.data["has_more"] is True
        assert result.data["next_cursor"] == "cursor-abc"

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_context):
        handler = NotionGetCommentsHandler()
        mock_context.fetch.side_effect = Exception("API rate limit exceeded")

        result = await handler.execute({"block_id": "page-789"}, mock_context)

        assert "error" in result.data
        assert "API rate limit exceeded" in result.data["error"]
        assert result.data["comments"] == []

    @pytest.mark.asyncio
    async def test_empty_optional_params(self, mock_context):
        handler = NotionGetCommentsHandler()

        mock_context.fetch.return_value = {
            "object": "list",
            "results": [],
            "next_cursor": None,
            "has_more": False,
        }

        await handler.execute(
            {"block_id": "page-123", "page_size": None, "start_cursor": ""},
            mock_context,
        )

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/comments",
            method="GET",
            headers=NOTION_HEADERS,
            params={"block_id": "page-123"},
        )


# ---------------------------------------------------------------------------
# Search handler
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.mark.asyncio
    async def test_basic_search(self, mock_context):
        handler = NotionSearchHandler()

        mock_context.fetch.return_value = {
            "object": "list",
            "results": [{"id": "page-1", "object": "page"}],
            "has_more": False,
            "next_cursor": None,
            "type": "page_or_database",
        }

        result = await handler.execute({"query": "meeting notes"}, mock_context)

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/search",
            method="POST",
            headers=NOTION_HEADERS_JSON,
            json={"query": "meeting notes"},
        )

        assert result.data["results"] == [{"id": "page-1", "object": "page"}]
        assert result.data["has_more"] is False

    @pytest.mark.asyncio
    async def test_search_with_filter_and_sort(self, mock_context):
        handler = NotionSearchHandler()

        mock_context.fetch.return_value = {
            "object": "list",
            "results": [],
            "has_more": False,
            "next_cursor": None,
        }

        inputs = {
            "query": "test",
            "filter": {"value": "page", "property": "object"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            "page_size": 10,
            "start_cursor": "abc",
        }

        await handler.execute(inputs, mock_context)

        call_json = mock_context.fetch.call_args.kwargs["json"]
        assert call_json["query"] == "test"
        assert call_json["filter"] == {"value": "page", "property": "object"}
        assert call_json["sort"] == {
            "direction": "descending",
            "timestamp": "last_edited_time",
        }
        assert call_json["page_size"] == 10
        assert call_json["start_cursor"] == "abc"

    @pytest.mark.asyncio
    async def test_search_error(self, mock_context):
        handler = NotionSearchHandler()
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await handler.execute({"query": "test"}, mock_context)

        assert "error" in result.data
        assert "Unauthorized" in result.data["error"]
        assert result.data["results"] == []


# ---------------------------------------------------------------------------
# GetPage handler
# ---------------------------------------------------------------------------


class TestGetPage:
    @pytest.mark.asyncio
    async def test_get_page(self, mock_context):
        handler = NotionGetPageHandler()

        page_data = {
            "id": "page-abc",
            "object": "page",
            "properties": {"Name": {"title": []}},
        }
        mock_context.fetch.return_value = page_data

        result = await handler.execute({"page_id": "page-abc"}, mock_context)

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/pages/page-abc",
            method="GET",
            headers=NOTION_HEADERS,
        )

        assert result.data["page"] == page_data

    @pytest.mark.asyncio
    async def test_get_page_error(self, mock_context):
        handler = NotionGetPageHandler()
        mock_context.fetch.side_effect = Exception("Not found")

        result = await handler.execute({"page_id": "bad-id"}, mock_context)

        assert "error" in result.data
        assert "Not found" in result.data["error"]
        assert result.data["page"] is None


# ---------------------------------------------------------------------------
# CreatePage handler
# ---------------------------------------------------------------------------


class TestCreatePage:
    @pytest.mark.asyncio
    async def test_create_page(self, mock_context):
        handler = NotionCreatePageHandler()

        parent = {"database_id": "db-123"}
        properties = {"Name": {"title": [{"text": {"content": "New Page"}}]}}
        created_page = {"id": "new-page-1", "object": "page"}
        mock_context.fetch.return_value = created_page

        result = await handler.execute({"parent": parent, "properties": properties}, mock_context)

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/pages",
            method="POST",
            headers=NOTION_HEADERS_JSON,
            json={"parent": parent, "properties": properties},
        )

        assert result.data["page"] == created_page

    @pytest.mark.asyncio
    async def test_create_page_error(self, mock_context):
        handler = NotionCreatePageHandler()
        mock_context.fetch.side_effect = Exception("Validation error")

        result = await handler.execute(
            {"parent": {"database_id": "db-1"}, "properties": {}},
            mock_context,
        )

        assert "error" in result.data
        assert result.data["page"] is None


# ---------------------------------------------------------------------------
# CreateComment handler
# ---------------------------------------------------------------------------


class TestCreateComment:
    @pytest.mark.asyncio
    async def test_create_comment(self, mock_context):
        handler = NotionCreateCommentHandler()

        parent = {"page_id": "page-123"}
        rich_text = [{"type": "text", "text": {"content": "A comment"}}]
        created_comment = {"id": "comment-new", "object": "comment"}
        mock_context.fetch.return_value = created_comment

        result = await handler.execute({"parent": parent, "rich_text": rich_text}, mock_context)

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/comments",
            method="POST",
            headers=NOTION_HEADERS_JSON,
            json={"parent": parent, "rich_text": rich_text},
        )

        assert result.data["comment"] == created_comment

    @pytest.mark.asyncio
    async def test_create_comment_error(self, mock_context):
        handler = NotionCreateCommentHandler()
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await handler.execute(
            {"parent": {"page_id": "p-1"}, "rich_text": []},
            mock_context,
        )

        assert "error" in result.data
        assert result.data["comment"] is None


# ---------------------------------------------------------------------------
# GetBlockChildren handler
# ---------------------------------------------------------------------------


class TestGetBlockChildren:
    @pytest.mark.asyncio
    async def test_get_block_children(self, mock_context):
        handler = NotionGetBlockChildrenHandler()

        mock_context.fetch.return_value = {
            "results": [
                {"id": "block-1", "type": "paragraph"},
                {"id": "block-2", "type": "heading_1"},
            ],
            "has_more": False,
            "next_cursor": None,
            "type": "block",
        }

        result = await handler.execute({"block_id": "parent-block"}, mock_context)

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/blocks/parent-block/children",
            method="GET",
            headers=NOTION_HEADERS,
            params={},
        )

        assert len(result.data["blocks"]) == 2
        assert result.data["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_block_children_with_pagination(self, mock_context):
        handler = NotionGetBlockChildrenHandler()

        mock_context.fetch.return_value = {
            "results": [{"id": "block-3"}],
            "has_more": True,
            "next_cursor": "next-abc",
        }

        result = await handler.execute(
            {"block_id": "parent-block", "page_size": 1, "start_cursor": "cur-1"},
            mock_context,
        )

        call_params = mock_context.fetch.call_args.kwargs["params"]
        assert call_params["page_size"] == 1
        assert call_params["start_cursor"] == "cur-1"
        assert result.data["has_more"] is True
        assert result.data["next_cursor"] == "next-abc"

    @pytest.mark.asyncio
    async def test_get_block_children_error(self, mock_context):
        handler = NotionGetBlockChildrenHandler()
        mock_context.fetch.side_effect = Exception("Server error")

        result = await handler.execute({"block_id": "block-x"}, mock_context)

        assert "error" in result.data
        assert result.data["blocks"] == []


# ---------------------------------------------------------------------------
# UpdateBlock handler
# ---------------------------------------------------------------------------


class TestUpdateBlock:
    @pytest.mark.asyncio
    async def test_update_block(self, mock_context):
        handler = NotionUpdateBlockHandler()

        updated_block = {
            "id": "block-1",
            "type": "paragraph",
            "paragraph": {"rich_text": []},
        }
        mock_context.fetch.return_value = updated_block

        inputs = {
            "block_id": "block-1",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Updated text"}}]},
        }

        result = await handler.execute(inputs, mock_context)

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/blocks/block-1",
            method="PATCH",
            headers=NOTION_HEADERS_JSON,
            json={"paragraph": inputs["paragraph"]},
        )

        assert result.data["block"] == updated_block

    @pytest.mark.asyncio
    async def test_update_block_filters_invalid_keys(self, mock_context):
        handler = NotionUpdateBlockHandler()
        mock_context.fetch.return_value = {"id": "block-1"}

        await handler.execute(
            {
                "block_id": "block-1",
                "paragraph": {"rich_text": []},
                "invalid_key": "ignored",
            },
            mock_context,
        )

        call_json = mock_context.fetch.call_args.kwargs["json"]
        assert "paragraph" in call_json
        assert "invalid_key" not in call_json
        assert "block_id" not in call_json

    @pytest.mark.asyncio
    async def test_update_block_error(self, mock_context):
        handler = NotionUpdateBlockHandler()
        mock_context.fetch.side_effect = Exception("Conflict")

        result = await handler.execute({"block_id": "block-1", "paragraph": {}}, mock_context)

        assert "error" in result.data
        assert result.data["block"] is None


# ---------------------------------------------------------------------------
# DeleteBlock handler
# ---------------------------------------------------------------------------


class TestDeleteBlock:
    @pytest.mark.asyncio
    async def test_delete_block(self, mock_context):
        handler = NotionDeleteBlockHandler()

        deleted_block = {"id": "block-del", "archived": True}
        mock_context.fetch.return_value = deleted_block

        result = await handler.execute({"block_id": "block-del"}, mock_context)

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/blocks/block-del",
            method="DELETE",
            headers=NOTION_HEADERS,
        )

        assert result.data["block"] == deleted_block

    @pytest.mark.asyncio
    async def test_delete_block_error(self, mock_context):
        handler = NotionDeleteBlockHandler()
        mock_context.fetch.side_effect = Exception("Not found")

        result = await handler.execute({"block_id": "gone"}, mock_context)

        assert "error" in result.data
        assert result.data["block"] is None


# ---------------------------------------------------------------------------
# UpdatePage handler
# ---------------------------------------------------------------------------


class TestUpdatePage:
    @pytest.mark.asyncio
    async def test_update_page_properties(self, mock_context):
        handler = NotionUpdatePageHandler()

        updated_page = {"id": "page-1", "object": "page"}
        mock_context.fetch.return_value = updated_page

        properties = {"Status": {"select": {"name": "Done"}}}
        result = await handler.execute({"page_id": "page-1", "properties": properties}, mock_context)

        mock_context.fetch.assert_called_once_with(
            url="https://api.notion.com/v1/pages/page-1",
            method="PATCH",
            headers=NOTION_HEADERS_JSON,
            json={"properties": properties},
        )

        assert result.data["page"] == updated_page

    @pytest.mark.asyncio
    async def test_update_page_archive(self, mock_context):
        handler = NotionUpdatePageHandler()
        mock_context.fetch.return_value = {"id": "page-1", "archived": True}

        result = await handler.execute({"page_id": "page-1", "archived": True}, mock_context)

        call_json = mock_context.fetch.call_args.kwargs["json"]
        assert call_json["archived"] is True
        assert result.data["page"]["archived"] is True

    @pytest.mark.asyncio
    async def test_update_page_filters_invalid_keys(self, mock_context):
        handler = NotionUpdatePageHandler()
        mock_context.fetch.return_value = {"id": "page-1"}

        await handler.execute(
            {"page_id": "page-1", "properties": {}, "bad_field": "ignored"},
            mock_context,
        )

        call_json = mock_context.fetch.call_args.kwargs["json"]
        assert "properties" in call_json
        assert "bad_field" not in call_json
        assert "page_id" not in call_json

    @pytest.mark.asyncio
    async def test_update_page_error(self, mock_context):
        handler = NotionUpdatePageHandler()
        mock_context.fetch.side_effect = Exception("Bad request")

        result = await handler.execute({"page_id": "page-1", "properties": {}}, mock_context)

        assert "error" in result.data
        assert result.data["page"] is None


# ---------------------------------------------------------------------------
# Cross-handler error consistency
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Verify all handlers return structured error data when fetch raises."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "handler_cls, inputs, error_key",
        [
            (NotionSearchHandler, {"query": "x"}, "results"),
            (NotionGetPageHandler, {"page_id": "x"}, "page"),
            (NotionCreatePageHandler, {"parent": {}, "properties": {}}, "page"),
            (NotionCreateCommentHandler, {"parent": {}, "rich_text": []}, "comment"),
            (NotionGetCommentsHandler, {"block_id": "x"}, "comments"),
            (NotionGetBlockChildrenHandler, {"block_id": "x"}, "blocks"),
            (NotionUpdateBlockHandler, {"block_id": "x"}, "block"),
            (NotionDeleteBlockHandler, {"block_id": "x"}, "block"),
            (NotionUpdatePageHandler, {"page_id": "x", "properties": {}}, "page"),
        ],
    )
    async def test_handler_returns_error_on_exception(self, mock_context, handler_cls, inputs, error_key):
        mock_context.fetch.side_effect = Exception("boom")

        handler = handler_cls()
        result = await handler.execute(inputs, mock_context)

        assert "error" in result.data
        assert "boom" in result.data["error"]
        assert error_key in result.data
