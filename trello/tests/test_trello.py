# Testbed for Trello integration
import asyncio
from context import trello
from autohive_integrations_sdk import ExecutionContext


async def test_get_current_member():
    """Test getting current member information."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("get_current_member", inputs, context)
            print(f"Get Current Member Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'member' in result, "Response missing 'member' field"
            return result
        except Exception as e:
            print(f"Error testing get_current_member: {e}")
            return None


async def test_list_boards():
    """Test listing all boards for authenticated member."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "filter": "open"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("list_boards", inputs, context)
            print(f"List Boards Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'boards' in result, "Response missing 'boards' field"
            return result
        except Exception as e:
            print(f"Error testing list_boards: {e}")
            return None


async def test_create_board():
    """Test creating a new board."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "name": "Test Board via Integration",
        "desc": "This is a test board created via Trello API integration",
        "defaultLists": True,
        "prefs_permissionLevel": "private"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("create_board", inputs, context)
            print(f"Create Board Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'board' in result, "Response missing 'board' field"
            return result
        except Exception as e:
            print(f"Error testing create_board: {e}")
            return None


async def test_get_board():
    """Test getting a specific board."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "board_id": "board_id_here",
        "fields": "name,desc,url"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("get_board", inputs, context)
            print(f"Get Board Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'board' in result, "Response missing 'board' field"
            return result
        except Exception as e:
            print(f"Error testing get_board: {e}")
            return None


async def test_update_board():
    """Test updating a board."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "board_id": "board_id_here",
        "name": "Updated Board Name",
        "desc": "Updated board description"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("update_board", inputs, context)
            print(f"Update Board Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'board' in result, "Response missing 'board' field"
            return result
        except Exception as e:
            print(f"Error testing update_board: {e}")
            return None


async def test_create_list():
    """Test creating a new list on a board."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "board_id": "board_id_here",
        "name": "To Do",
        "pos": "top"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("create_list", inputs, context)
            print(f"Create List Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'list' in result, "Response missing 'list' field"
            return result
        except Exception as e:
            print(f"Error testing create_list: {e}")
            return None


async def test_get_list():
    """Test getting a specific list."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "list_id": "list_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("get_list", inputs, context)
            print(f"Get List Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'list' in result, "Response missing 'list' field"
            return result
        except Exception as e:
            print(f"Error testing get_list: {e}")
            return None


async def test_update_list():
    """Test updating a list."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "list_id": "list_id_here",
        "name": "In Progress"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("update_list", inputs, context)
            print(f"Update List Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'list' in result, "Response missing 'list' field"
            return result
        except Exception as e:
            print(f"Error testing update_list: {e}")
            return None


async def test_list_lists():
    """Test listing all lists on a board."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "board_id": "board_id_here",
        "filter": "open"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("list_lists", inputs, context)
            print(f"List Lists Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'lists' in result, "Response missing 'lists' field"
            return result
        except Exception as e:
            print(f"Error testing list_lists: {e}")
            return None


async def test_create_card():
    """Test creating a new card."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "list_id": "list_id_here",
        "name": "Test Card via Integration",
        "desc": "This is a test card created via Trello API integration",
        "pos": "top"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("create_card", inputs, context)
            print(f"Create Card Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'card' in result, "Response missing 'card' field"
            return result
        except Exception as e:
            print(f"Error testing create_card: {e}")
            return None


async def test_get_card():
    """Test getting a specific card."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "card_id": "card_id_here",
        "fields": "name,desc,due,members"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("get_card", inputs, context)
            print(f"Get Card Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'card' in result, "Response missing 'card' field"
            return result
        except Exception as e:
            print(f"Error testing get_card: {e}")
            return None


async def test_update_card():
    """Test updating a card."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "card_id": "card_id_here",
        "name": "Updated Card Name",
        "desc": "Updated card description"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("update_card", inputs, context)
            print(f"Update Card Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'card' in result, "Response missing 'card' field"
            return result
        except Exception as e:
            print(f"Error testing update_card: {e}")
            return None


async def test_delete_card():
    """Test deleting a card."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "card_id": "card_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("delete_card", inputs, context)
            print(f"Delete Card Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing delete_card: {e}")
            return None


async def test_list_cards():
    """Test listing cards on a list."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "list_id": "list_id_here",
        "filter": "open"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("list_cards", inputs, context)
            print(f"List Cards Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'cards' in result, "Response missing 'cards' field"
            return result
        except Exception as e:
            print(f"Error testing list_cards: {e}")
            return None


async def test_create_checklist():
    """Test creating a checklist on a card."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "card_id": "card_id_here",
        "name": "Checklist Items"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("create_checklist", inputs, context)
            print(f"Create Checklist Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'checklist' in result, "Response missing 'checklist' field"
            return result
        except Exception as e:
            print(f"Error testing create_checklist: {e}")
            return None


async def test_add_checklist_item():
    """Test adding an item to a checklist."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "checklist_id": "checklist_id_here",
        "name": "Task item 1",
        "checked": False
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("add_checklist_item", inputs, context)
            print(f"Add Checklist Item Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'checkItem' in result, "Response missing 'checkItem' field"
            return result
        except Exception as e:
            print(f"Error testing add_checklist_item: {e}")
            return None


async def test_add_comment():
    """Test adding a comment to a card."""
    auth = {
        "auth_type": "custom",
        "credentials": {
            "api_key": "your_api_key_here",
            "token": "your_token_here"
        }
    }

    inputs = {
        "card_id": "card_id_here",
        "text": "This is a test comment"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await trello.execute_action("add_comment", inputs, context)
            print(f"Add Comment Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'comment' in result, "Response missing 'comment' field"
            return result
        except Exception as e:
            print(f"Error testing add_comment: {e}")
            return None


async def main():
    print("Testing Trello Integration - 17 Actions")
    print("=" * 60)
    print()
    print("NOTE: Replace placeholders with actual values:")
    print("  - your_api_key_here: Your Trello API Key")
    print("  - your_token_here: Your Trello API Token")
    print("  - board_id_here, list_id_here, card_id_here, checklist_id_here")
    print()
    print("TIP: Run get_current_member and list_boards tests first!")
    print()
    print("=" * 60)
    print()

    # Test member action (1) - RUN THIS FIRST!
    print("MEMBER DISCOVERY ACTION")
    print("-" * 60)
    print("1. Testing get_current_member (helps you discover member info)...")
    await test_get_current_member()
    print()

    print("=" * 60)
    print()
    print("BOARD ACTIONS")
    print("-" * 60)

    # Test board actions (4)
    print("2. Testing list_boards...")
    await test_list_boards()
    print()

    print("3. Testing create_board...")
    await test_create_board()
    print()

    print("4. Testing get_board...")
    await test_get_board()
    print()

    print("5. Testing update_board...")
    await test_update_board()
    print()

    print("=" * 60)
    print()
    print("LIST ACTIONS")
    print("-" * 60)

    # Test list actions (4)
    print("6. Testing create_list...")
    await test_create_list()
    print()

    print("7. Testing get_list...")
    await test_get_list()
    print()

    print("8. Testing update_list...")
    await test_update_list()
    print()

    print("9. Testing list_lists...")
    await test_list_lists()
    print()

    print("=" * 60)
    print()
    print("CARD ACTIONS")
    print("-" * 60)

    # Test card actions (6)
    print("10. Testing create_card...")
    await test_create_card()
    print()

    print("11. Testing get_card...")
    await test_get_card()
    print()

    print("12. Testing update_card...")
    await test_update_card()
    print()

    print("13. Testing delete_card...")
    await test_delete_card()
    print()

    print("14. Testing list_cards...")
    await test_list_cards()
    print()

    print("=" * 60)
    print()
    print("CHECKLIST ACTIONS")
    print("-" * 60)

    # Test checklist actions (2)
    print("15. Testing create_checklist...")
    await test_create_checklist()
    print()

    print("16. Testing add_checklist_item...")
    await test_add_checklist_item()
    print()

    print("=" * 60)
    print()
    print("COMMENT ACTIONS")
    print("-" * 60)

    # Test comment action (1)
    print("17. Testing add_comment...")
    await test_add_comment()
    print()

    print("=" * 60)
    print("Testing completed - 17 actions total!")
    print("  - 1 member action")
    print("  - 4 board actions")
    print("  - 4 list actions")
    print("  - 6 card actions")
    print("  - 2 checklist actions")
    print("  - 1 comment action")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
