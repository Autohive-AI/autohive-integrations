import asyncio
import sys
from pathlib import Path

# Ensure the teams package resolves config.json from its own directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from autohive_integrations_sdk import ExecutionContext
from teams import teams

# Common test credentials
# Replace these with real values from your Teams connection before running.
TEST_AUTH = {
    "auth_type": "PlatformTeams",
    "credentials": {
        "TeamId": "YOUR_TEAM_ID",
        "GroupId": "YOUR_GROUP_ID",
        "TenantId": "YOUR_TENANT_ID",
        "ServiceUrl": "https://smba.trafficmanager.net/YOUR_REGION/YOUR_TENANT_ID/",
    },
}


async def test_list_channels():
    print("\nTesting list_channels action")
    print("=============================")

    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {}

    try:
        result = await teams.execute_action("list_channels", inputs, context)
        print("Success! Retrieved channels:")
        for channel in result.result.data.get("channels", []):
            print(f"- {channel['name']} (ID: {channel['id']})")
    except Exception as e:
        print(f"Error testing list_channels: {str(e)}")


async def test_search_channels():
    print("\nTesting search_channels action")
    print("=============================")

    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        "query": "general"  # This should find the general channel
    }

    try:
        result = await teams.execute_action("search_channels", inputs, context)
        print("Success! Found channels:")
        for channel in result.result.data.get("channels", []):
            print(f"- {channel['name']} (ID: {channel['id']})")
    except Exception as e:
        print(f"Error testing search_channels: {str(e)}")


async def test_get_channel_by_name():
    print("\nTesting get_channel_by_name action")
    print("=============================")

    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        "channel_name": "general"  # Testing with general channel
    }

    try:
        result = await teams.execute_action("get_channel_by_name", inputs, context)
        data = result.result.data
        if data["found"]:
            channel = data["channel"]
            print(f"Success! Found channel: {channel['name']} (ID: {channel['id']})")
        else:
            print("Channel not found")
    except Exception as e:
        print(f"Error testing get_channel_by_name: {str(e)}")


async def test_send_message():
    print("\nTesting send_message action")
    print("=============================")

    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {
        "channel_id": "YOUR_CHANNEL_ID",
        "message": "Hello, this is a test message from the Teams integration!",
    }

    try:
        result = await teams.execute_action("send_message", inputs, context)
        print(f"Success! {result.result.data['message']}")
    except Exception as e:
        print(f"Error testing send_message: {str(e)}")


TEST_CHANNEL_ID = "YOUR_CHANNEL_ID"


async def test_get_channel_messages():
    print("\nTesting get_channel_messages action")
    print("=============================")

    context = ExecutionContext(auth=TEST_AUTH)
    inputs = {"channel_id": TEST_CHANNEL_ID, "limit": 5}

    try:
        result = await teams.execute_action("get_channel_messages", inputs, context)
        messages = result.result.data.get("messages", [])
        print(f"Success! Retrieved {len(messages)} messages:")
        for msg in messages:
            print(f"- [{msg['created_at']}] {msg['from']}: {msg['text'][:80]}")
    except Exception as e:
        print(f"Error testing get_channel_messages: {str(e)}")


async def test_get_message_replies():
    print("\nTesting get_message_replies action")
    print("=============================")

    # First get a message ID to reply to
    context = ExecutionContext(auth=TEST_AUTH)
    messages_result = await teams.execute_action(
        "get_channel_messages", {"channel_id": TEST_CHANNEL_ID, "limit": 1}, context
    )
    messages = messages_result.result.data.get("messages", [])
    if not messages:
        print("No messages found — skipping get_message_replies test")
        return

    message_id = messages[0]["id"]
    inputs = {"channel_id": TEST_CHANNEL_ID, "message_id": message_id}

    try:
        result = await teams.execute_action("get_message_replies", inputs, context)
        data = result.result.data
        print(f"Success! {data['count']} replies for message {message_id}")
    except Exception as e:
        print(f"Error testing get_message_replies: {str(e)}")


async def test_reply_to_message():
    print("\nTesting reply_to_message action")
    print("=============================")

    # Get a message ID to reply to
    context = ExecutionContext(auth=TEST_AUTH)
    messages_result = await teams.execute_action(
        "get_channel_messages", {"channel_id": TEST_CHANNEL_ID, "limit": 1}, context
    )
    messages = messages_result.result.data.get("messages", [])
    if not messages:
        print("No messages found — skipping reply_to_message test")
        return

    message_id = messages[0]["id"]
    inputs = {
        "channel_id": TEST_CHANNEL_ID,
        "message_id": message_id,
        "reply": "This is a test reply from the Teams integration.",
    }

    try:
        result = await teams.execute_action("reply_to_message", inputs, context)
        print(f"Success! {result.result.data}")
    except Exception as e:
        print(f"Error testing reply_to_message: {str(e)}")


async def main():
    print("Testing Teams Integration")
    print("=============================")

    await test_list_channels()
    await test_search_channels()
    await test_get_channel_by_name()
    await test_send_message()
    await test_get_channel_messages()
    await test_get_message_replies()
    await test_reply_to_message()


if __name__ == "__main__":
    asyncio.run(main())
