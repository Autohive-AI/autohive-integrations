# Testbed for Google Chat integration
import asyncio
from context import google_chat
from autohive_integrations_sdk import ExecutionContext


async def test_list_spaces():
    """Test listing all spaces the user is a member of."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {"page_size": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("list_spaces", inputs, context)
            print(f"List Spaces Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_spaces: {e}")
            return None


async def test_get_space():
    """Test getting details of a specific space."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {"space_name": "spaces/AAAAMpdlehY"}  # Replace with actual space name

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("get_space", inputs, context)
            print(f"Get Space Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_space: {e}")
            return None


async def test_create_space():
    """Test creating a new Google Chat space."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {
        "display_name": "Test Space via Integration",
        "space_details": {
            "description": "A test space created via API integration",
            "guidelines": "Please be respectful and on-topic"
        }
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("create_space", inputs, context)
            print(f"Create Space Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_space: {e}")
            return None


async def test_send_message():
    """Test sending a message to a space."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {
        "space_name": "spaces/AAAAMpdlehY",  # Replace with actual space name
        "text": "Hello from Autohive integration! This is a test message."
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("send_message", inputs, context)
            print(f"Send Message Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing send_message: {e}")
            return None


async def test_list_messages():
    """Test listing messages from a space."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {
        "space_name": "spaces/AAAAMpdlehY",  # Replace with actual space name
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("list_messages", inputs, context)
            print(f"List Messages Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_messages: {e}")
            return None


async def test_get_message():
    """Test getting details of a specific message."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {"message_name": "spaces/AAAAMpdlehY/messages/xyz"}  # Replace with actual message name

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("get_message", inputs, context)
            print(f"Get Message Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_message: {e}")
            return None


async def test_update_message():
    """Test updating a previously sent message."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {
        "message_name": "spaces/AAAAMpdlehY/messages/xyz",  # Replace with actual message name
        "text": "Updated message content from Autohive integration"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("update_message", inputs, context)
            print(f"Update Message Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing update_message: {e}")
            return None


async def test_delete_message():
    """Test deleting a message."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {
        "message_name": "spaces/AAAAMpdlehY/messages/xyz",  # Replace with actual message name
        "force": False
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("delete_message", inputs, context)
            print(f"Delete Message Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing delete_message: {e}")
            return None


async def test_list_members():
    """Test listing members of a space."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {
        "space_name": "spaces/AAAAMpdlehY",  # Replace with actual space name
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("list_members", inputs, context)
            print(f"List Members Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_members: {e}")
            return None


async def test_add_reaction():
    """Test adding an emoji reaction to a message."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {
        "message_name": "spaces/AAAAMpdlehY/messages/xyz",  # Replace with actual message name
        "emoji": {
            "unicode": "👍"
        }
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("add_reaction", inputs, context)
            print(f"Add Reaction Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing add_reaction: {e}")
            return None


async def test_list_reactions():
    """Test listing reactions on a message."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {
        "message_name": "spaces/AAAAMpdlehY/messages/xyz",  # Replace with actual message name
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("list_reactions", inputs, context)
            print(f"List Reactions Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_reactions: {e}")
            return None


async def test_remove_reaction():
    """Test removing a reaction from a message."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {
        "reaction_name": "spaces/AAAAMpdlehY/messages/xyz/reactions/123"  # Replace with actual reaction name
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("remove_reaction", inputs, context)
            print(f"Remove Reaction Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing remove_reaction: {e}")
            return None


async def test_find_direct_message():
    """Test finding a direct message conversation with a user."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here",
            "refresh_token": "your_refresh_token_here"
        }
    }

    inputs = {
        "user_name": "users/example@gmail.com"  # Replace with actual user name
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_chat.execute_action("find_direct_message", inputs, context)
            print(f"Find Direct Message Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing find_direct_message: {e}")
            return None


async def main():
    print("Testing Google Chat Integration")
    print("=" * 60)
    print()
    print("NOTE: Replace 'your_access_token_here' and 'your_refresh_token_here'")
    print("      with actual OAuth tokens before running tests.")
    print("      Also replace resource names (spaces/AAAAMpdlehY) with actual values.")
    print()
    print("=" * 60)
    print()

    # Test space actions
    print("1. Testing list_spaces...")
    await test_list_spaces()
    print()

    print("2. Testing get_space...")
    await test_get_space()
    print()

    print("3. Testing create_space...")
    created_space = await test_create_space()
    print()

    # Test message actions
    print("4. Testing send_message...")
    sent_message = await test_send_message()
    print()

    print("5. Testing list_messages...")
    await test_list_messages()
    print()

    print("6. Testing get_message...")
    await test_get_message()
    print()

    print("7. Testing update_message...")
    await test_update_message()
    print()

    print("8. Testing delete_message...")
    await test_delete_message()
    print()

    # Test member actions
    print("9. Testing list_members...")
    await test_list_members()
    print()

    # Test reaction actions
    print("10. Testing add_reaction...")
    await test_add_reaction()
    print()

    print("11. Testing list_reactions...")
    await test_list_reactions()
    print()

    print("12. Testing remove_reaction...")
    await test_remove_reaction()
    print()

    # Test utility actions
    print("13. Testing find_direct_message...")
    await test_find_direct_message()
    print()

    print("=" * 60)
    print("Testing completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
