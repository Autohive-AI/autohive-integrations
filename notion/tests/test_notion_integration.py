import asyncio
import json
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock
from notion import notion
from notion.notion import NotionGetCommentsHandler

async def test_integration_config():
    """Test that the integration configuration is valid"""
    
    # Test that all actions defined in config.json have corresponding handlers
    with open("config.json", "r") as f:
        config = json.load(f)
    
    defined_actions = set(config.get("actions", {}).keys())
    
    # Get all registered action handlers from the integration
    registered_actions = set(notion._actions.keys()) if hasattr(notion, '_actions') else set()
    
    print(f"Actions defined in config.json: {defined_actions}")
    print(f"Actions registered in handlers: {registered_actions}")
    
    missing_handlers = defined_actions - registered_actions
    extra_handlers = registered_actions - defined_actions
    
    if missing_handlers:
        print(f"Missing handlers for actions: {missing_handlers}")
    
    if extra_handlers:
        print(f"Extra handlers without config: {extra_handlers}")
    
    if not missing_handlers and not extra_handlers:
        print("ll actions have matching handlers!")
        return True
    
    return False

async def test_get_comments():
    """Test that the get_notion_comments action is properly configured"""

    with open("config.json", "r") as f:
        config = json.load(f)

    actions = config.get("actions", {})

    if "get_notion_comments" in actions:
        print("✅ get_notion_comments is defined in config.json")
        action_config = actions["get_notion_comments"]

        # Check required fields
        assert action_config["display_name"] == "Get Comments"
        print(f"   - Has display_name: {action_config['display_name']}")

        assert "Retrieve comments" in action_config["description"]
        print(f"   - Has description: {action_config['description']}")

        # Check input schema
        input_schema = action_config["input_schema"]
        assert "block_id" in input_schema["properties"]
        assert "page_size" in input_schema["properties"]
        assert "start_cursor" in input_schema["properties"]
        assert input_schema["required"] == ["block_id"]
        print("   - Has correct input schema with block_id, page_size, start_cursor")

        # Check output schema
        output_schema = action_config["output_schema"]
        assert "comments" in output_schema["properties"]
        assert "next_cursor" in output_schema["properties"]
        assert "has_more" in output_schema["properties"]
        print("   - Has correct output schema with comments, next_cursor, has_more")

        return True
    else:
        print("❌ get_notion_comments is NOT defined in config.json")
        return False


async def test_get_comments_with_pagination():
    """Test that pagination parameters are correctly defined for get_notion_comments"""

    with open("config.json", "r") as f:
        config = json.load(f)

    actions = config.get("actions", {})
    action_config = actions.get("get_notion_comments", {})
    input_schema = action_config.get("input_schema", {})
    properties = input_schema.get("properties", {})

    # Check page_size constraints
    page_size = properties.get("page_size", {})
    assert page_size.get("type") == "integer"
    assert page_size.get("minimum") == 1
    assert page_size.get("maximum") == 100
    print("✅ page_size has correct type and constraints (1-100)")

    # Check start_cursor
    start_cursor = properties.get("start_cursor", {})
    assert start_cursor.get("type") == "string"
    print("✅ start_cursor is defined as string type")

    return True


async def test_create_and_get_comment():
    """Test that both create_notion_comment and get_notion_comments actions exist and complement each other"""

    with open("config.json", "r") as f:
        config = json.load(f)

    actions = config.get("actions", {})

    # Check both actions exist
    has_create = "create_notion_comment" in actions
    has_get = "get_notion_comments" in actions

    if has_create and has_get:
        print("✅ Both create_notion_comment and get_notion_comments actions exist")

        # Verify create_notion_comment returns an id that could be used to verify via get_notion_comments
        create_output = actions["create_notion_comment"]["output_schema"]["properties"]
        assert "id" in create_output
        print("   - create_notion_comment returns comment id")

        # Verify get_notion_comments returns array of comments with ids
        get_output = actions["get_notion_comments"]["output_schema"]["properties"]
        assert "comments" in get_output
        print("   - get_notion_comments returns comments array")

        return True
    else:
        if not has_create:
            print("❌ create_notion_comment is missing")
        if not has_get:
            print("❌ get_notion_comments is missing")
        return False


async def test_get_comments_handler_basic():
    """Test NotionGetCommentsHandler with basic block_id input"""
    handler = NotionGetCommentsHandler()

    mock_response = {
        "object": "list",
        "results": [
            {
                "id": "comment-123",
                "discussion_id": "disc-456",
                "created_time": "2024-01-15T10:00:00.000Z",
                "rich_text": [{"type": "text", "text": {"content": "Test comment"}}],
                "parent": {"type": "page_id", "page_id": "page-789"}
            }
        ],
        "next_cursor": None,
        "has_more": False
    }

    mock_context = MagicMock()
    mock_context.fetch = AsyncMock(return_value=mock_response)

    inputs = {"block_id": "page-789"}
    result = await handler.execute(inputs, mock_context)

    # Verify fetch was called correctly
    mock_context.fetch.assert_called_once_with(
        url="https://api.notion.com/v1/comments",
        method="GET",
        headers={"Notion-Version": "2025-09-03"},
        params={"block_id": "page-789"}
    )

    assert len(result.data["comments"]) == 1
    assert result.data["comments"][0]["id"] == "comment-123"
    assert result.data["has_more"] is False


async def test_get_comments_handler_with_pagination():
    """Test NotionGetCommentsHandler with pagination parameters"""
    handler = NotionGetCommentsHandler()

    mock_response = {
        "object": "list",
        "results": [{"id": "comment-1"}, {"id": "comment-2"}],
        "next_cursor": "cursor-abc",
        "has_more": True
    }

    mock_context = MagicMock()
    mock_context.fetch = AsyncMock(return_value=mock_response)

    inputs = {
        "block_id": "page-123",
        "page_size": 2,
        "start_cursor": "prev-cursor"
    }
    result = await handler.execute(inputs, mock_context)

    # Verify fetch was called with pagination params
    mock_context.fetch.assert_called_once_with(
        url="https://api.notion.com/v1/comments",
        method="GET",
        headers={"Notion-Version": "2025-09-03"},
        params={
            "block_id": "page-123",
            "page_size": 2,
            "start_cursor": "prev-cursor"
        }
    )

    assert result.data["has_more"] is True
    assert result.data["next_cursor"] == "cursor-abc"


async def test_get_comments_handler_error():
    """Test NotionGetCommentsHandler error handling"""
    handler = NotionGetCommentsHandler()

    mock_context = MagicMock()
    mock_context.fetch = AsyncMock(side_effect=Exception("API rate limit exceeded"))

    inputs = {"block_id": "page-789"}

    result = await handler.execute(inputs, mock_context)
    assert "error" in result.data
    assert "API rate limit exceeded" in result.data["error"]
    assert result.data["comments"] == []


async def test_get_comments_handler_empty_optional_params():
    """Test NotionGetCommentsHandler ignores empty optional params"""
    handler = NotionGetCommentsHandler()

    mock_response = {"object": "list", "results": [], "next_cursor": None, "has_more": False}

    mock_context = MagicMock()
    mock_context.fetch = AsyncMock(return_value=mock_response)

    # Pass empty/None values for optional params
    inputs = {
        "block_id": "page-123",
        "page_size": None,
        "start_cursor": ""
    }
    await handler.execute(inputs, mock_context)

    # Verify only block_id was passed (empty values should be ignored)
    mock_context.fetch.assert_called_once_with(
        url="https://api.notion.com/v1/comments",
        method="GET",
        headers={"Notion-Version": "2025-09-03"},
        params={"block_id": "page-123"}
    )


async def test_new_actions():
    """Test that the new update/delete actions are properly configured"""

    new_actions = ["update_notion_block", "delete_notion_block", "update_notion_page", "get_notion_comments"]
    
    with open("config.json", "r") as f:
        config = json.load(f)
    
    actions = config.get("actions", {})
    
    for action in new_actions:
        if action in actions:
            print(f"✅ {action} is defined in config.json")
            
            # Check required fields
            action_config = actions[action]
            if "display_name" in action_config and "description" in action_config:
                print(f"   - Has display_name: {action_config['display_name']}")
                print(f"   - Has description: {action_config['description']}")
            else:
                print(f"Missing display_name or description")
                
            if "input_schema" in action_config and "output_schema" in action_config:
                print(f"   - Has input and output schemas")
            else:
                print(f"Missing input or output schema")
        else:
            print(f"{action} is NOT defined in config.json")

async def main():
    """Run all tests"""
    print("=== Testing Notion Integration Enhancement ===\n")

    print("1. Testing integration configuration...")
    config_valid = await test_integration_config()
    print()

    print("2. Testing new action configurations...")
    await test_new_actions()
    print()

    print("3. Testing get_notion_comments action...")
    get_comments_valid = await test_get_comments()
    print()

    print("4. Testing get_notion_comments pagination...")
    pagination_valid = await test_get_comments_with_pagination()
    print()

    print("5. Testing create and get comment round-trip...")
    roundtrip_valid = await test_create_and_get_comment()
    print()

    print("6. Testing handler: basic get comments...")
    await test_get_comments_handler_basic()
    print("✅ Handler basic test passed")
    print()

    print("7. Testing handler: pagination params...")
    await test_get_comments_handler_with_pagination()
    print("✅ Handler pagination test passed")
    print()

    print("8. Testing handler: error handling...")
    await test_get_comments_handler_error()
    print("✅ Handler error test passed")
    print()

    print("9. Testing handler: empty optional params...")
    await test_get_comments_handler_empty_optional_params()
    print("✅ Handler empty params test passed")
    print()

    if config_valid and get_comments_valid and pagination_valid and roundtrip_valid:
        print("All tests passed!")
        print("\nNew capabilities added:")
        print("- get_notion_comments: Retrieve comments from pages/blocks")
    else:
        print("Integration has configuration issues that need to be fixed.")

if __name__ == "__main__":
    asyncio.run(main())