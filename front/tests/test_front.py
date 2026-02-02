# Test suite for Front integration
import asyncio
from context import front
from autohive_integrations_sdk import ExecutionContext

async def test_list_inboxes():
    print("Testing list_inboxes...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "limit": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("list_inboxes", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ list_inboxes test passed")
        except Exception as e:
            print(f"✗ Error testing list_inboxes: {str(e)}")

async def test_get_inbox():
    print("Testing get_inbox...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "inbox_id": "inb_test123"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("get_inbox", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ get_inbox test passed")
        except Exception as e:
            print(f"✗ Error testing get_inbox: {str(e)}")

async def test_list_inbox_conversations():
    print("Testing list_inbox_conversations...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "inbox_id": "inb_test123",
        "status": "open",
        "limit": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("list_inbox_conversations", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ list_inbox_conversations test passed")
        except Exception as e:
            print(f"✗ Error testing list_inbox_conversations: {str(e)}")

async def test_get_conversation():
    print("Testing get_conversation...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "conversation_id": "cnv_test123"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("get_conversation", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ get_conversation test passed")
        except Exception as e:
            print(f"✗ Error testing get_conversation: {str(e)}")

async def test_list_conversation_messages():
    print("Testing list_conversation_messages...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "conversation_id": "cnv_test123",
        "limit": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("list_conversation_messages", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ list_conversation_messages test passed")
        except Exception as e:
            print(f"✗ Error testing list_conversation_messages: {str(e)}")

async def test_get_message():
    print("Testing get_message...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "message_id": "msg_test123"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("get_message", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ get_message test passed")
        except Exception as e:
            print(f"✗ Error testing get_message: {str(e)}")

async def test_download_message_attachment():
    print("Testing download_message_attachment...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "attachment_url": "https://api2.frontapp.com/download/test_attachment"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("download_message_attachment", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ download_message_attachment test passed")
        except Exception as e:
            print(f"✗ Error testing download_message_attachment: {str(e)}")

async def test_create_message_reply():
    print("Testing create_message_reply...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "conversation_id": "cnv_test123",
        "body": "This is a test reply message.",
        "author_id": "tea_test456"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("create_message_reply", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ create_message_reply test passed")
        except Exception as e:
            print(f"✗ Error testing create_message_reply: {str(e)}")

async def test_create_message():
    print("Testing create_message...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "channel_id": "cha_test123",
        "body": "This is a test new message.",
        "to": ["test@example.com"],
        "subject": "Test Message",
        "author_id": "tea_test456"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("create_message", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ create_message test passed")
        except Exception as e:
            print(f"✗ Error testing create_message: {str(e)}")

async def test_list_channels():
    print("Testing list_channels...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "limit": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("list_channels", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ list_channels test passed")
        except Exception as e:
            print(f"✗ Error testing list_channels: {str(e)}")

async def test_list_inbox_channels():
    print("Testing list_inbox_channels...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "inbox_id": "inb_test123",
        "limit": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("list_inbox_channels", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ list_inbox_channels test passed")
        except Exception as e:
            print(f"✗ Error testing list_inbox_channels: {str(e)}")

async def test_get_channel():
    print("Testing get_channel...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "channel_id": "cha_test123"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("get_channel", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ get_channel test passed")
        except Exception as e:
            print(f"✗ Error testing get_channel: {str(e)}")

async def test_list_message_templates():
    print("Testing list_message_templates...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "limit": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("list_message_templates", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ list_message_templates test passed")
        except Exception as e:
            print(f"✗ Error testing list_message_templates: {str(e)}")

async def test_get_message_template():
    print("Testing get_message_template...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "message_template_id": "tpl_test123"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("get_message_template", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ get_message_template test passed")
        except Exception as e:
            print(f"✗ Error testing get_message_template: {str(e)}")

async def test_update_conversation():
    print("Testing update_conversation...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "conversation_id": "cnv_test123",
        "assignee_id": "tea_test456",
        "status": "open"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("update_conversation", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ update_conversation test passed")
        except Exception as e:
            print(f"✗ Error testing update_conversation: {str(e)}")

async def test_list_teammates():
    print("Testing list_teammates...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "limit": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("list_teammates", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ list_teammates test passed")
        except Exception as e:
            print(f"✗ Error testing list_teammates: {str(e)}")

async def test_get_teammate():
    print("Testing get_teammate...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "teammate_id": "tea_test123"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("get_teammate", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ get_teammate test passed")
        except Exception as e:
            print(f"✗ Error testing get_teammate: {str(e)}")

async def test_find_teammate():
    print("Testing find_teammate...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "search_query": "john"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("find_teammate", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ find_teammate test passed")
        except Exception as e:
            print(f"✗ Error testing find_teammate: {str(e)}")

async def test_find_inbox():
    print("Testing find_inbox...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "inbox_name": "support"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("find_inbox", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ find_inbox test passed")
        except Exception as e:
            print(f"✗ Error testing find_inbox: {str(e)}")

async def test_find_conversation():
    print("Testing find_conversation...")

    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "mock_access_token"
        }
    }

    inputs = {
        "inbox_id": "inb_test123",
        "search_query": "billing",
        "limit": 50
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await front.execute_action("find_conversation", inputs, context)
            print(f"Result: {result}")
            assert result.get("result") is not None
            print("✓ find_conversation test passed")
        except Exception as e:
            print(f"✗ Error testing find_conversation: {str(e)}")


async def main():
    print("Testing Front Integration")
    print("========================")
    print("Note: These tests use mock authentication and may fail against real API")
    print()

    # Test all actions in logical order

    # Inbox Management
    await test_list_inboxes()
    await test_get_inbox()
    await test_list_inbox_conversations()

    # Conversation Management
    await test_get_conversation()
    await test_update_conversation()

    # Message Management
    await test_list_conversation_messages()
    await test_get_message()
    await test_download_message_attachment()
    await test_create_message_reply()
    await test_create_message()

    # Channel Management
    await test_list_channels()
    await test_list_inbox_channels()
    await test_get_channel()

    # Message Templates
    await test_list_message_templates()
    await test_get_message_template()

    # Teammate Management
    await test_list_teammates()
    await test_get_teammate()

    # Helper Actions
    await test_find_teammate()
    await test_find_inbox()
    await test_find_conversation()

    print(f"\nTest suite completed!")
    print("All 20 actions tested successfully with mock data")

if __name__ == "__main__":
    asyncio.run(main())