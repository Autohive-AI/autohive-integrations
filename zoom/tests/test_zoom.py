# Test suite for the Zoom integration
import asyncio
from context import zoom
from autohive_integrations_sdk import ExecutionContext


async def test_connected_account():
    """Test the connected account handler."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            # Get the connected account handler
            handler = zoom.get_connected_account_handler()
            if handler:
                account_info = await handler.get_account_info(context)
                print("Connected Account Info:")
                print(f"  Email: {account_info.email}")
                print(f"  Username: {account_info.username}")
                print(f"  First Name: {account_info.first_name}")
                print(f"  Last Name: {account_info.last_name}")
                print(f"  Organization: {account_info.organization}")
                print(f"  User ID: {account_info.user_id}")
                print(f"  Avatar URL: {account_info.avatar_url}")
                return account_info
            else:
                print("No connected account handler found")
                return None
        except Exception as e:
            print(f"Error testing connected_account: {e}")
            return None


async def test_list_meetings():
    """Test listing meetings for a user."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "user_id": "me",
        "type": "scheduled",
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("list_meetings", inputs, context)
            # ActionResult contains data and cost_usd
            data = result.data
            cost = result.cost_usd
            print("List Meetings Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Total Records: {data.get('total_records')}")
            print(f"  Cost (USD): {cost}")
            if data.get('meetings'):
                for meeting in data['meetings'][:3]:
                    print(f"  - {meeting.get('topic')} (ID: {meeting.get('id')})")
            return result
        except Exception as e:
            print(f"Error testing list_meetings: {e}")
            return None


async def test_get_meeting():
    """Test getting meeting details."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "meeting_id": "your_meeting_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("get_meeting", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Get Meeting Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Topic: {data.get('topic')}")
            print(f"  Start Time: {data.get('start_time')}")
            print(f"  Join URL: {data.get('join_url')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing get_meeting: {e}")
            return None


async def test_create_meeting():
    """Test creating a new meeting."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "user_id": "me",
        "topic": "Test Meeting from Autohive",
        "type": 2,  # Scheduled meeting
        "start_time": "2025-01-20T10:00:00Z",
        "duration": 60,
        "timezone": "America/New_York",
        "agenda": "Test meeting created via Autohive integration",
        "waiting_room": True,
        "join_before_host": False,
        "mute_upon_entry": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("create_meeting", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Create Meeting Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Meeting ID: {data.get('id')}")
            print(f"  Topic: {data.get('topic')}")
            print(f"  Join URL: {data.get('join_url')}")
            print(f"  Start URL: {data.get('start_url')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing create_meeting: {e}")
            return None


async def test_update_meeting():
    """Test updating a meeting."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "meeting_id": "your_meeting_id_here",
        "topic": "Updated Meeting Topic",
        "duration": 90,
        "agenda": "Updated meeting agenda"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("update_meeting", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Update Meeting Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Meeting ID: {data.get('meeting_id')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing update_meeting: {e}")
            return None


async def test_delete_meeting():
    """Test deleting a meeting."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "meeting_id": "your_meeting_id_here",
        "schedule_for_reminder": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("delete_meeting", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Delete Meeting Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Meeting ID: {data.get('meeting_id')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing delete_meeting: {e}")
            return None


async def test_get_user():
    """Test getting user details."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "user_id": "me"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("get_user", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Get User Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Name: {data.get('first_name')} {data.get('last_name')}")
            print(f"  Email: {data.get('email')}")
            print(f"  Timezone: {data.get('timezone')}")
            print(f"  PMI: {data.get('pmi')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing get_user: {e}")
            return None


async def test_get_meeting_participants():
    """Test getting meeting participants."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "meeting_id": "your_meeting_id_here",
        "page_size": 30
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("get_meeting_participants", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Get Meeting Participants Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Total Records: {data.get('total_records')}")
            print(f"  Cost (USD): {cost}")
            if data.get('participants'):
                for participant in data['participants'][:5]:
                    print(f"  - {participant.get('name')} (Duration: {participant.get('duration')}s)")
            return result
        except Exception as e:
            print(f"Error testing get_meeting_participants: {e}")
            return None


async def test_add_meeting_registrant():
    """Test adding a meeting registrant."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "meeting_id": "your_meeting_id_here",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "auto_approve": True
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("add_meeting_registrant", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Add Meeting Registrant Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Registrant ID: {data.get('registrant_id')}")
            print(f"  Join URL: {data.get('join_url')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing add_meeting_registrant: {e}")
            return None


async def test_list_contacts():
    """Test listing contacts."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "page_size": 50
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("list_contacts", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("List Contacts Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Total Records: {data.get('total_records')}")
            print(f"  Cost (USD): {cost}")
            if data.get('contacts'):
                for contact in data['contacts'][:3]:
                    print(f"  - {contact.get('first_name')} {contact.get('last_name')} ({contact.get('email')})")
            return result
        except Exception as e:
            print(f"Error testing list_contacts: {e}")
            return None


async def test_create_calendar_event():
    """Test creating a calendar event."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "calendar_id": "primary",
        "summary": "Test Event from Autohive",
        "start": {
            "dateTime": "2025-01-20T10:00:00Z",
            "timeZone": "America/New_York"
        },
        "end": {
            "dateTime": "2025-01-20T11:00:00Z",
            "timeZone": "America/New_York"
        },
        "description": "Test event created via Autohive integration",
        "location": "Virtual"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("create_calendar_event", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Create Calendar Event Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Event ID: {data.get('id')}")
            print(f"  Summary: {data.get('summary')}")
            print(f"  HTML Link: {data.get('html_link')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing create_calendar_event: {e}")
            return None


async def test_list_calendar_events():
    """Test listing calendar events."""
    auth = {
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
            result = await zoom.execute_action("list_calendar_events", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("List Calendar Events Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Time Zone: {data.get('time_zone')}")
            print(f"  Cost (USD): {cost}")
            if data.get('events'):
                for event in data['events'][:3]:
                    print(f"  - {event.get('summary')} (ID: {event.get('id')})")
            return result
        except Exception as e:
            print(f"Error testing list_calendar_events: {e}")
            return None


async def test_get_calendar_event():
    """Test getting a calendar event."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "calendar_id": "primary",
        "event_id": "your_event_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("get_calendar_event", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Get Calendar Event Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Summary: {data.get('summary')}")
            print(f"  Location: {data.get('location')}")
            print(f"  Status: {data.get('status')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing get_calendar_event: {e}")
            return None


async def test_delete_calendar_event():
    """Test deleting a calendar event."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "calendar_id": "primary",
        "event_id": "your_event_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("delete_calendar_event", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Delete Calendar Event Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Event ID: {data.get('event_id')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing delete_calendar_event: {e}")
            return None


async def test_quick_create_calendar_event():
    """Test quick creating a calendar event."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "calendar_id": "primary",
        "text": "Team meeting tomorrow at 2pm"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("quick_create_calendar_event", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Quick Create Calendar Event Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Event ID: {data.get('id')}")
            print(f"  Summary: {data.get('summary')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing quick_create_calendar_event: {e}")
            return None


async def test_get_calendar_metadata():
    """Test getting calendar metadata."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "calendar_id": "primary"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("get_calendar_metadata", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Get Calendar Metadata Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  ID: {data.get('id')}")
            print(f"  Summary: {data.get('summary')}")
            print(f"  Timezone: {data.get('timezone')}")
            print(f"  Primary: {data.get('primary')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing get_calendar_metadata: {e}")
            return None


async def test_list_calendar_settings():
    """Test listing calendar settings."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("list_calendar_settings", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("List Calendar Settings Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Cost (USD): {cost}")
            if data.get('settings'):
                for setting in data['settings'][:5]:
                    print(f"  - {setting.get('id')}: {setting.get('value')}")
            return result
        except Exception as e:
            print(f"Error testing list_calendar_settings: {e}")
            return None


async def test_create_meeting_template():
    """Test creating a meeting template from an existing meeting."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "user_id": "me",
        "meeting_id": "your_meeting_id_here",
        "name": "Test Meeting Template"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("create_meeting_template", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Create Meeting Template Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Template ID: {data.get('id')}")
            print(f"  Name: {data.get('name')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing create_meeting_template: {e}")
            return None


async def test_get_meeting_template_detail():
    """Test getting meeting template detail."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "user_id": "me",
        "template_id": "your_template_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("get_meeting_template_detail", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Get Meeting Template Detail Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Template ID: {data.get('id')}")
            print(f"  Name: {data.get('name')}")
            print(f"  Topic: {data.get('topic')}")
            print(f"  Duration: {data.get('duration')} minutes")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing get_meeting_template_detail: {e}")
            return None


async def test_create_meeting_invite_links():
    """Test creating meeting invite links."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "meeting_id": "your_meeting_id_here",
        "attendees": [
            {"name": "John Doe"},
            {"name": "Jane Smith"}
        ],
        "ttl": 7200
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("create_meeting_invite_links", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Create Meeting Invite Links Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Cost (USD): {cost}")
            if data.get('attendees'):
                for attendee in data['attendees']:
                    print(f"  - {attendee.get('name')}: {attendee.get('join_url')}")
            return result
        except Exception as e:
            print(f"Error testing create_meeting_invite_links: {e}")
            return None


async def test_get_meeting_participant():
    """Test getting a meeting participant."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "meeting_id": "your_meeting_id_here",
        "participant_id": "your_participant_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("get_meeting_participant", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Get Meeting Participant Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Name: {data.get('name')}")
            print(f"  Email: {data.get('user_email')}")
            print(f"  Join Time: {data.get('join_time')}")
            print(f"  Duration: {data.get('duration')} seconds")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing get_meeting_participant: {e}")
            return None


async def test_get_past_meeting():
    """Test getting past meeting details."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "meeting_id": "your_meeting_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("get_past_meeting", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Get Past Meeting Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Topic: {data.get('topic')}")
            print(f"  Start Time: {data.get('start_time')}")
            print(f"  End Time: {data.get('end_time')}")
            print(f"  Total Minutes: {data.get('total_minutes')}")
            print(f"  Participants Count: {data.get('participants_count')}")
            print(f"  Cost (USD): {cost}")
            return result
        except Exception as e:
            print(f"Error testing get_past_meeting: {e}")
            return None


async def test_get_user_permissions():
    """Test getting user permissions."""
    auth = {
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "user_id": "me"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await zoom.execute_action("get_user_permissions", inputs, context)
            data = result.data
            cost = result.cost_usd
            print("Get User Permissions Result:")
            print(f"  Success: {data.get('result')}")
            print(f"  Cost (USD): {cost}")
            if data.get('permissions'):
                print(f"  Permissions: {', '.join(data['permissions'][:10])}")
                if len(data['permissions']) > 10:
                    print(f"    ... and {len(data['permissions']) - 10} more")
            return result
        except Exception as e:
            print(f"Error testing get_user_permissions: {e}")
            return None


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Zoom Integration (with ActionResult pattern)")
    print("=" * 60)
    print()
    print("Note: Replace 'your_access_token_here' and 'your_meeting_id_here'")
    print("with actual values to run these tests against the Zoom API.")
    print()

    # Uncomment the tests you want to run:
    # --- Original Meeting Tests ---
    # await test_connected_account()
    # await test_list_meetings()
    # await test_get_meeting()
    # await test_create_meeting()
    # await test_update_meeting()
    # await test_delete_meeting()
    # await test_get_user()
    # await test_get_meeting_participants()
    # await test_add_meeting_registrant()

    # --- Calendar Tests ---
    # await test_create_calendar_event()
    # await test_list_calendar_events()
    # await test_get_calendar_event()
    # await test_delete_calendar_event()
    # await test_quick_create_calendar_event()
    # await test_get_calendar_metadata()
    # await test_list_calendar_settings()

    # --- Contacts Tests ---
    # await test_list_contacts()

    # --- Meeting Template & Invite Tests ---
    # await test_create_meeting_template()
    # await test_get_meeting_template_detail()
    # await test_create_meeting_invite_links()
    # await test_get_meeting_participant()
    # await test_get_past_meeting()

    # --- User Tests ---
    # await test_get_user_permissions()

    print()
    print("=" * 60)
    print("Test suite completed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
