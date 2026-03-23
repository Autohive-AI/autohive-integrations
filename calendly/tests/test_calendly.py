# Test suite for Calendly integration
import asyncio
from context import calendly
from autohive_integrations_sdk import ExecutionContext


# ---- User Tests ----

async def test_get_current_user():
    """Test getting current user info."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("get_current_user", {}, context)
            print(f"Get Current User Result: {result}")
            assert result.data.get('result') == True
            assert 'user' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_current_user: {e}")
            return None


async def test_get_user():
    """Test getting user by UUID."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"user_uuid": "your_user_uuid_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("get_user", inputs, context)
            print(f"Get User Result: {result}")
            assert result.data.get('result') == True
            assert 'user' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_user: {e}")
            return None


# ---- Event Type Tests ----

async def test_list_event_types():
    """Test listing event types."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"count": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("list_event_types", inputs, context)
            print(f"List Event Types Result: {result}")
            assert result.data.get('result') == True
            assert 'event_types' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_event_types: {e}")
            return None


async def test_get_event_type():
    """Test getting event type details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"event_type_uuid": "your_event_type_uuid_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("get_event_type", inputs, context)
            print(f"Get Event Type Result: {result}")
            assert result.data.get('result') == True
            assert 'event_type' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_event_type: {e}")
            return None


# ---- Scheduled Event Tests ----

async def test_list_scheduled_events():
    """Test listing scheduled events."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"count": 10, "status": "active"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("list_scheduled_events", inputs, context)
            print(f"List Scheduled Events Result: {result}")
            assert result.data.get('result') == True
            assert 'events' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_scheduled_events: {e}")
            return None


async def test_get_scheduled_event():
    """Test getting scheduled event details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"event_uuid": "your_event_uuid_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("get_scheduled_event", inputs, context)
            print(f"Get Scheduled Event Result: {result}")
            assert result.data.get('result') == True
            assert 'event' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_scheduled_event: {e}")
            return None


async def test_cancel_scheduled_event():
    """Test canceling a scheduled event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"event_uuid": "your_event_uuid_to_cancel", "reason": "Test cancellation"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("cancel_scheduled_event", inputs, context)
            print(f"Cancel Scheduled Event Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing cancel_scheduled_event: {e}")
            return None


# ---- Invitee Tests ----

async def test_list_event_invitees():
    """Test listing event invitees."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"event_uuid": "your_event_uuid_here", "count": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("list_event_invitees", inputs, context)
            print(f"List Event Invitees Result: {result}")
            assert result.data.get('result') == True
            assert 'invitees' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_event_invitees: {e}")
            return None


async def test_get_invitee():
    """Test getting invitee details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"event_uuid": "your_event_uuid_here", "invitee_uuid": "your_invitee_uuid_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("get_invitee", inputs, context)
            print(f"Get Invitee Result: {result}")
            assert result.data.get('result') == True
            assert 'invitee' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_invitee: {e}")
            return None


# ---- Availability Tests ----

async def test_get_event_type_available_times():
    """Test getting available times for an event type."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "event_type": "https://api.calendly.com/event_types/your_event_type_uuid",
        "start_time": "2025-01-25T00:00:00Z",
        "end_time": "2025-01-31T23:59:59Z"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("get_event_type_available_times", inputs, context)
            print(f"Get Available Times Result: {result}")
            assert result.data.get('result') == True
            assert 'available_times' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_event_type_available_times: {e}")
            return None


async def test_get_user_busy_times():
    """Test getting user busy times."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "user": "https://api.calendly.com/users/your_user_uuid",
        "start_time": "2025-01-25T00:00:00Z",
        "end_time": "2025-01-31T23:59:59Z"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("get_user_busy_times", inputs, context)
            print(f"Get User Busy Times Result: {result}")
            assert result.data.get('result') == True
            assert 'busy_times' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_user_busy_times: {e}")
            return None


async def test_list_user_availability_schedules():
    """Test listing user availability schedules."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"user": "https://api.calendly.com/users/your_user_uuid"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("list_user_availability_schedules", inputs, context)
            print(f"List Availability Schedules Result: {result}")
            assert result.data.get('result') == True
            assert 'availability_schedules' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_user_availability_schedules: {e}")
            return None


# ---- Organization Tests ----

async def test_list_organization_memberships():
    """Test listing organization members."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"count": 10}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("list_organization_memberships", inputs, context)
            print(f"List Organization Memberships Result: {result}")
            assert result.data.get('result') == True
            assert 'memberships' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_organization_memberships: {e}")
            return None


# ---- Webhook Tests ----

async def test_list_webhooks():
    """Test listing webhooks."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"organization": "https://api.calendly.com/organizations/your_org_uuid"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("list_webhooks", inputs, context)
            print(f"List Webhooks Result: {result}")
            assert result.data.get('result') == True
            assert 'webhooks' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_webhooks: {e}")
            return None


async def test_get_webhook():
    """Test getting webhook details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"webhook_uuid": "your_webhook_uuid_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("get_webhook", inputs, context)
            print(f"Get Webhook Result: {result}")
            assert result.data.get('result') == True
            assert 'webhook' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_webhook: {e}")
            return None


async def test_create_webhook():
    """Test creating a webhook."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {
        "url": "https://example.com/webhook",
        "events": ["invitee.created", "invitee.canceled"],
        "organization": "https://api.calendly.com/organizations/your_org_uuid",
        "scope": "organization"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("create_webhook", inputs, context)
            print(f"Create Webhook Result: {result}")
            assert result.data.get('result') == True
            assert 'webhook' in result.data
            return result
        except Exception as e:
            print(f"Error testing create_webhook: {e}")
            return None


async def test_delete_webhook():
    """Test deleting a webhook."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"webhook_uuid": "your_webhook_uuid_to_delete"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("delete_webhook", inputs, context)
            print(f"Delete Webhook Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing delete_webhook: {e}")
            return None


# ---- Routing Form Tests ----

async def test_list_routing_forms():
    """Test listing routing forms."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"organization": "https://api.calendly.com/organizations/your_org_uuid"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("list_routing_forms", inputs, context)
            print(f"List Routing Forms Result: {result}")
            assert result.data.get('result') == True
            assert 'routing_forms' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_routing_forms: {e}")
            return None


async def test_get_routing_form():
    """Test getting routing form details."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"routing_form_uuid": "your_routing_form_uuid_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("get_routing_form", inputs, context)
            print(f"Get Routing Form Result: {result}")
            assert result.data.get('result') == True
            assert 'routing_form' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_routing_form: {e}")
            return None


async def test_list_routing_form_submissions():
    """Test listing routing form submissions."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "your_access_token_here"}
    }
    inputs = {"routing_form": "https://api.calendly.com/routing_forms/your_routing_form_uuid"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await calendly.execute_action("list_routing_form_submissions", inputs, context)
            print(f"List Routing Form Submissions Result: {result}")
            assert result.data.get('result') == True
            assert 'submissions' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_routing_form_submissions: {e}")
            return None


# Main test runner
async def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("Calendly Integration Test Suite")
    print("=" * 60)

    test_functions = [
        # User
        ("Get Current User", test_get_current_user),
        ("Get User", test_get_user),
        # Event Types
        ("List Event Types", test_list_event_types),
        ("Get Event Type", test_get_event_type),
        # Scheduled Events
        ("List Scheduled Events", test_list_scheduled_events),
        ("Get Scheduled Event", test_get_scheduled_event),
        ("Cancel Scheduled Event", test_cancel_scheduled_event),
        # Invitees
        ("List Event Invitees", test_list_event_invitees),
        ("Get Invitee", test_get_invitee),
        # Availability
        ("Get Available Times", test_get_event_type_available_times),
        ("Get User Busy Times", test_get_user_busy_times),
        ("List Availability Schedules", test_list_user_availability_schedules),
        # Organization
        ("List Organization Memberships", test_list_organization_memberships),
        # Webhooks
        ("List Webhooks", test_list_webhooks),
        ("Get Webhook", test_get_webhook),
        ("Create Webhook", test_create_webhook),
        ("Delete Webhook", test_delete_webhook),
        # Routing Forms
        ("List Routing Forms", test_list_routing_forms),
        ("Get Routing Form", test_get_routing_form),
        ("List Routing Form Submissions", test_list_routing_form_submissions),
    ]

    results = []
    for test_name, test_func in test_functions:
        print(f"\n{'-' * 60}")
        print(f"Running: {test_name}")
        print(f"{'-' * 60}")
        result = await test_func()
        results.append((test_name, result is not None))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {passed_count}/{len(results)} tests passed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
