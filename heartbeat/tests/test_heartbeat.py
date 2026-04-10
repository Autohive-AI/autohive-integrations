# Testbed for the Heartbeat integration.
# The IUT (integration under test) is the heartbeat.py file
import asyncio

from autohive_integrations_sdk import ExecutionContext

import heartbeat

# Global credentials object
CREDENTIALS = {
    "credentials": {
        "api_key": "YOUR_HEARTBEAT_API_KEY_HERE"  # Replace with your actual API key
    }
}

async def test_get_channels():
    """Test getting all channels"""
    inputs = {}

    async with ExecutionContext(auth=CREDENTIALS) as context:
        try:
            result = await heartbeat.heartbeat.execute_action("get_heartbeat_channels", inputs, context)
            print(f"✅ Get Channels - Success: Found {len(result.get('channels', []))} channels")
            for channel in result.get('channels', [])[:3]:  # Show first 3 channels
                print(f"   - {channel.get('name', 'Unnamed')} (ID: {channel.get('id')})")
            return result
        except Exception as e:
            print(f"❌ Error testing get_heartbeat_channels: {str(e)}")
            return None

async def test_get_channel(channel_id: str = None):
    """Test getting a specific channel"""
    # Use a default channel ID if none provided
    inputs = {
        "channel_id": channel_id or "CHANNEL_ID_HERE"  # Replace with actual channel ID
    }

    async with ExecutionContext(auth=CREDENTIALS) as context:
        try:
            result = await heartbeat.heartbeat.execute_action("get_heartbeat_channel", inputs, context)
            print(f"✅ Get Channel - Success: {result.get('channel', {}).get('name', 'Unnamed')}")
            return result
        except Exception as e:
            print(f"❌ Error testing get_heartbeat_channel: {str(e)}")
            return None

async def test_get_channel_threads(channel_id: str = None):
    """Test getting threads from a specific channel"""
    inputs = {
        "channel_id": channel_id or "CHANNEL_ID_HERE"  # Replace with actual channel ID
    }

    async with ExecutionContext(auth=CREDENTIALS) as context:
        try:
            result = await heartbeat.heartbeat.execute_action("get_heartbeat_channel_threads", inputs, context)
            print(f"✅ Get Channel Threads - Success: Found {len(result.get('threads', []))} threads")
            for thread in result.get('threads', [])[:3]:  # Show first 3 threads
                print(f"   - {thread.get('title', 'Untitled')} (ID: {thread.get('id')})")
            return result
        except Exception as e:
            print(f"❌ Error testing get_heartbeat_channel_threads: {str(e)}")
            return None

async def test_get_thread(thread_id: str = None):
    """Test getting a specific thread"""
    inputs = {
        "thread_id": thread_id or "THREAD_ID_HERE"  # Replace with actual thread ID
    }

    async with ExecutionContext(auth=CREDENTIALS) as context:
        try:
            result = await heartbeat.heartbeat.execute_action("get_heartbeat_thread", inputs, context)
            print(f"✅ Get Thread - Success: {result.get('thread', {}).get('title', 'Untitled')}")
            return result
        except Exception as e:
            print(f"❌ Error testing get_heartbeat_thread: {str(e)}")
            return None

async def test_get_users():
    """Test getting all users"""
    inputs = {}

    async with ExecutionContext(auth=CREDENTIALS) as context:
        try:
            result = await heartbeat.heartbeat.execute_action("get_heartbeat_users", inputs, context)
            print(f"✅ Get Users - Success: Found {len(result.get('users', []))} users")
            for user in result.get('users', [])[:3]:  # Show first 3 users
                print(f"   - {user.get('name', 'Unnamed')} ({user.get('email', 'No email')})")
            return result
        except Exception as e:
            print(f"❌ Error testing get_heartbeat_users: {str(e)}")
            return None

async def test_get_user(user_id: str = None):
    """Test getting a specific user"""
    inputs = {
        "user_id": user_id or "USER_ID_HERE"  # Replace with actual user ID
    }

    async with ExecutionContext(auth=CREDENTIALS) as context:
        try:
            result = await heartbeat.heartbeat.execute_action("get_heartbeat_user", inputs, context)
            print(f"✅ Get User - Success: {result.get('user', {}).get('name', 'Unnamed')}")
            return result
        except Exception as e:
            print(f"❌ Error testing get_heartbeat_user: {str(e)}")
            return None

async def test_get_events():
    """Test getting all events"""
    inputs = {}

    async with ExecutionContext(auth=CREDENTIALS) as context:
        try:
            result = await heartbeat.heartbeat.execute_action("get_heartbeat_events", inputs, context)
            print(f"✅ Get Events - Success: Found {len(result.get('events', []))} events")
            for event in result.get('events', [])[:3]:  # Show first 3 events
                print(f"   - {event.get('title', 'Untitled')} (Start: {event.get('startTime', 'No time')})")
            return result
        except Exception as e:
            print(f"❌ Error testing get_heartbeat_events: {str(e)}")
            return None

async def test_get_event(event_id: str = None):
    """Test getting a specific event"""
    inputs = {
        "event_id": event_id or "EVENT_ID_HERE"  # Replace with actual event ID
    }

    async with ExecutionContext(auth=CREDENTIALS) as context:
        try:
            result = await heartbeat.heartbeat.execute_action("get_heartbeat_event", inputs, context)
            print(f"✅ Get Event - Success: {result.get('event', {}).get('title', 'Untitled')}")
            return result
        except Exception as e:
            print(f"❌ Error testing get_heartbeat_event: {str(e)}")
            return None

async def main():
    print("Testing Heartbeat Integration")
    print("============================")
    print("📝 Make sure to replace 'YOUR_HEARTBEAT_API_KEY_HERE' with your actual API key!")
    print("📝 Also replace the placeholder IDs with real IDs from your Heartbeat community.")
    print()

    # Test list endpoints first (these don't need specific IDs)
    print("🔍 Testing list endpoints...")
    channels_result = await test_get_channels()
    users_result = await test_get_users()
    events_result = await test_get_events()
    
    print("\n🎯 Testing specific item endpoints...")
    print("ℹ️  These will likely fail until you provide real IDs...")
    
    # Try to get a channel ID from the channels result for further testing
    channel_id = None
    if channels_result and channels_result.get('channels'):
        channel_id = channels_result['channels'][0].get('id')
        print(f"📌 Using channel ID from results: {channel_id}")
    
    # Test specific endpoints (may fail without real IDs)
    await test_get_channel(channel_id)
    if channel_id:
        await test_get_channel_threads(channel_id)
    
    await test_get_thread()
    await test_get_user()
    await test_get_event()
    
    print("\n🎉 Testing complete!")
    print("💡 To test specific items, update the placeholder IDs in the test functions.")

if __name__ == "__main__":
    asyncio.run(main())
