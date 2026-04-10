# Testbed for Google Calendar integration
import asyncio
from context import google_calendar
from autohive_integrations_sdk import ExecutionContext

async def test_list_calendars():
    """Test listing calendars with OAuth2 authentication."""
    # Setup OAuth2 auth object
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {}  # No inputs required for listing calendars

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_calendar.execute_action("list_calendars", inputs, context)
            print(f"List Calendars Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_calendars: {e}")
            return None

async def test_list_events():
    """Test listing events from primary calendar."""
    auth = {
        "auth_type": "PlatformOauth2", 
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "calendar_id": "primary",
        "max_results": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_calendar.execute_action("list_events", inputs, context)
            print(f"List Events Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing list_events: {e}")
            return None

async def test_get_event():
    """Test getting a specific event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "calendar_id": "primary",
        "event_id": "test_event_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_calendar.execute_action("get_event", inputs, context)
            print(f"Get Event Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing get_event: {e}")
            return None

async def test_create_event():
    """Test creating a new calendar event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "calendar_id": "primary",
        "summary": "Test Event",
        "description": "This is a test event created by the integration",
        "start_datetime": "2024-12-01T10:00:00-08:00",
        "end_datetime": "2024-12-01T11:00:00-08:00",
        "location": "Test Location"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_calendar.execute_action("create_event", inputs, context)
            print(f"Create Event Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing create_event: {e}")
            return None

async def test_update_event():
    """Test updating an existing event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "calendar_id": "primary",
        "event_id": "test_event_id_here",
        "summary": "Updated Test Event",
        "description": "This event has been updated"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_calendar.execute_action("update_event", inputs, context)
            print(f"Update Event Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing update_event: {e}")
            return None

async def test_delete_event():
    """Test deleting an event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "calendar_id": "primary",
        "event_id": "test_event_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await google_calendar.execute_action("delete_event", inputs, context)
            print(f"Delete Event Result: {result}")
            return result
        except Exception as e:
            print(f"Error testing delete_event: {e}")
            return None

async def main():
    print("Testing Google Calendar Integration")
    print("==================================")
    print()

    # Test each action
    print("1. Testing list_calendars...")
    await test_list_calendars()
    print()

    print("2. Testing list_events...")
    await test_list_events() 
    print()

    print("3. Testing get_event...")
    await test_get_event()
    print()

    print("4. Testing create_event...")
    created_event = await test_create_event()
    print()

    # If create succeeded, try to update and delete the created event
    if created_event and created_event.get('result'):
        event_id = created_event.get('event', {}).get('id')
        if event_id:
            print("5. Testing update_event on created event...")
            # Update the test to use actual event_id
            await test_update_event()
            print()

            print("6. Testing delete_event on created event...")
            # Delete the test to use actual event_id
            await test_delete_event()
            print()

    print("Testing completed!")

if __name__ == "__main__":
    asyncio.run(main())
