# Live API tests for Meetup integration
# Run: python tests/test_meetup.py
# Requires a valid Meetup OAuth access token and at least one group you organize.
import asyncio
from context import meetup
from autohive_integrations_sdk import ExecutionContext

AUTH = {
    "auth_type": "PlatformOauth2",
    "credentials": {
        "access_token": "your_access_token_here"
    }
}

# Fill these in before running create/update/delete/publish tests
TEST_GROUP_URLNAME = "your-group-urlname-here"
TEST_EVENT_ID = "your_event_id_here"


async def test_get_self():
    """Test getting the authenticated user's profile."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await meetup.execute_action("get_self", {}, context)
            print(f"Get Self Result: {result}")
            assert result.get("result") is True, f"Action failed: {result.get('error')}"
            assert "user" in result, "Response missing 'user' field"
            if result.get("user"):
                print(f"  -> {result['user'].get('name')} ({result['user'].get('email')})")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_list_groups():
    """Test listing organized groups."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await meetup.execute_action("list_groups", {"first": 10}, context)
            print(f"List Groups Result: {result}")
            assert result.get("result") is True, f"Action failed: {result.get('error')}"
            assert "groups" in result, "Response missing 'groups' field"
            if result.get("groups"):
                print(f"  -> Found {len(result['groups'])} group(s)")
                for g in result["groups"]:
                    print(f"     - {g.get('name')} ({g.get('urlname')})")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_group():
    """Test getting a specific group."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await meetup.execute_action("get_group", {"urlname": TEST_GROUP_URLNAME}, context)
            print(f"Get Group Result: {result}")
            assert result.get("result") is True, f"Action failed: {result.get('error')}"
            assert "group" in result, "Response missing 'group' field"
            if result.get("group"):
                print(f"  -> {result['group'].get('name')} ({result['group'].get('membersCount')} members)")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_list_events():
    """Test listing upcoming events for a group."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await meetup.execute_action(
                "list_events",
                {"urlname": TEST_GROUP_URLNAME, "first": 5},
                context
            )
            print(f"List Events Result: {result}")
            assert result.get("result") is True, f"Action failed: {result.get('error')}"
            assert "events" in result, "Response missing 'events' field"
            if result.get("events"):
                print(f"  -> Found {len(result['events'])} event(s)")
                for e in result["events"]:
                    print(f"     - {e.get('title')} (ID: {e.get('id')})")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_event():
    """Test getting a specific event."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await meetup.execute_action("get_event", {"event_id": TEST_EVENT_ID}, context)
            print(f"Get Event Result: {result}")
            assert result.get("result") is True, f"Action failed: {result.get('error')}"
            assert "event" in result, "Response missing 'event' field"
            if result.get("event"):
                print(f"  -> {result['event'].get('title')} (status: {result['event'].get('status')})")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_create_event():
    """Test creating a draft event. Returns the new event ID for use in other tests."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await meetup.execute_action(
                "create_event",
                {
                    "group_urlname": TEST_GROUP_URLNAME,
                    "title": "Test Event (Autohive Integration Test)",
                    "description": "This is a test event created by the Autohive Meetup integration.",
                    "start_date_time": "2026-06-01T18:00:00",
                    "duration": 90,
                    "is_online": True,
                },
                context
            )
            print(f"Create Event Result: {result}")
            assert result.get("result") is True, f"Action failed: {result.get('error')}"
            assert "event" in result, "Response missing 'event' field"
            if result.get("event"):
                print(f"  -> Created: {result['event'].get('title')} (ID: {result['event'].get('id')})")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_update_event(event_id: str):
    """Test updating an event."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await meetup.execute_action(
                "update_event",
                {
                    "event_id": event_id,
                    "title": "Test Event (Updated by Autohive)",
                    "description": "Updated description via Autohive integration test.",
                },
                context
            )
            print(f"Update Event Result: {result}")
            assert result.get("result") is True, f"Action failed: {result.get('error')}"
            if result.get("event"):
                print(f"  -> Updated: {result['event'].get('title')}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_publish_event(event_id: str):
    """Test publishing a draft event."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await meetup.execute_action("publish_event", {"event_id": event_id}, context)
            print(f"Publish Event Result: {result}")
            assert result.get("result") is True, f"Action failed: {result.get('error')}"
            if result.get("event"):
                print(f"  -> Published: {result['event'].get('title')} (status: {result['event'].get('status')})")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_delete_event(event_id: str):
    """Test deleting an event."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await meetup.execute_action("delete_event", {"event_id": event_id}, context)
            print(f"Delete Event Result: {result}")
            assert result.get("result") is True, f"Action failed: {result.get('error')}"
            print("  -> Deleted successfully")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return None


async def main():
    print("=" * 60)
    print("MEETUP INTEGRATION TESTS")
    print("=" * 60)

    print("\n1. Testing get_self...")
    await test_get_self()

    print("\n2. Testing list_groups...")
    await test_list_groups()

    print("\n3. Testing get_group...")
    await test_get_group()

    print("\n4. Testing list_events...")
    await test_list_events()

    print("\n5. Testing get_event (uses TEST_EVENT_ID)...")
    await test_get_event()

    print("\n6. Testing create_event...")
    create_result = await test_create_event()
    new_event_id = None
    if create_result and create_result.get("event"):
        new_event_id = create_result["event"].get("id")

    if new_event_id:
        print(f"\n7. Testing update_event (event: {new_event_id})...")
        await test_update_event(new_event_id)

        print(f"\n8. Testing publish_event (event: {new_event_id})...")
        await test_publish_event(new_event_id)

        print(f"\n9. Testing delete_event (event: {new_event_id})...")
        await test_delete_event(new_event_id)
    else:
        print("\n7-9. Skipping update/publish/delete (no event ID from create step)")

    print("\n" + "=" * 60)
    print("Testing complete — 9 actions total")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
