# Testbed for Eventbrite integration
import asyncio
from context import eventbrite
from autohive_integrations_sdk import ExecutionContext


async def test_get_current_user():
    """Test getting current user information."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("get_current_user", inputs, context)
            print(f"Get Current User Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'user' in result, "Response missing 'user' field"
            if result.get('user'):
                print(f"  -> User: {result['user'].get('name')} ({result['user'].get('email')})")
            return result
        except Exception as e:
            print(f"Error testing get_current_user: {e}")
            return None


async def test_list_organizations():
    """Test listing organizations."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("list_organizations", inputs, context)
            print(f"List Organizations Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'organizations' in result, "Response missing 'organizations' field"
            if result.get('organizations'):
                print(f"  -> Found {len(result['organizations'])} organization(s)")
                for org in result['organizations']:
                    print(f"     - {org.get('name')} (ID: {org.get('id')})")
            return result
        except Exception as e:
            print(f"Error testing list_organizations: {e}")
            return None


async def test_list_events():
    """Test listing events for an organization."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "organization_id": "your_organization_id_here",
        "status": "live",
        "page_size": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("list_events", inputs, context)
            print(f"List Events Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'events' in result, "Response missing 'events' field"
            if result.get('events'):
                print(f"  -> Found {len(result['events'])} event(s)")
                for event in result['events'][:5]:
                    print(f"     - {event.get('name', {}).get('text')} (ID: {event.get('id')})")
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
        "event_id": "your_event_id_here",
        "expand": ["venue", "organizer"]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("get_event", inputs, context)
            print(f"Get Event Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'event' in result, "Response missing 'event' field"
            return result
        except Exception as e:
            print(f"Error testing get_event: {e}")
            return None


async def test_create_event():
    """Test creating a new event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "organization_id": "your_organization_id_here",
        "name": "Test Event via Integration",
        "summary": "This is a test event created via Eventbrite API integration",
        "start_utc": "2024-12-25T18:00:00Z",
        "end_utc": "2024-12-25T21:00:00Z",
        "timezone": "America/Los_Angeles",
        "currency": "USD",
        "online_event": True,
        "listed": False
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("create_event", inputs, context)
            print(f"Create Event Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'event' in result, "Response missing 'event' field"
            if result.get('event'):
                print(f"  -> Created event ID: {result['event'].get('id')}")
            return result
        except Exception as e:
            print(f"Error testing create_event: {e}")
            return None


async def test_update_event():
    """Test updating an event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "event_id": "your_event_id_here",
        "name": "Updated Event Name",
        "summary": "Updated event summary"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("update_event", inputs, context)
            print(f"Update Event Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'event' in result, "Response missing 'event' field"
            return result
        except Exception as e:
            print(f"Error testing update_event: {e}")
            return None


async def test_publish_event():
    """Test publishing an event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"event_id": "your_event_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("publish_event", inputs, context)
            print(f"Publish Event Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing publish_event: {e}")
            return None


async def test_unpublish_event():
    """Test unpublishing an event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"event_id": "your_event_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("unpublish_event", inputs, context)
            print(f"Unpublish Event Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing unpublish_event: {e}")
            return None


async def test_copy_event():
    """Test copying an event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "event_id": "your_event_id_here",
        "name": "Copied Event"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("copy_event", inputs, context)
            print(f"Copy Event Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'event' in result, "Response missing 'event' field"
            return result
        except Exception as e:
            print(f"Error testing copy_event: {e}")
            return None


async def test_delete_event():
    """Test deleting an event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"event_id": "your_event_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("delete_event", inputs, context)
            print(f"Delete Event Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing delete_event: {e}")
            return None


async def test_list_venues():
    """Test listing venues."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"organization_id": "your_organization_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("list_venues", inputs, context)
            print(f"List Venues Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'venues' in result, "Response missing 'venues' field"
            if result.get('venues'):
                print(f"  -> Found {len(result['venues'])} venue(s)")
                for venue in result['venues'][:5]:
                    print(f"     - {venue.get('name')} (ID: {venue.get('id')})")
            return result
        except Exception as e:
            print(f"Error testing list_venues: {e}")
            return None


async def test_get_venue():
    """Test getting a specific venue."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"venue_id": "your_venue_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("get_venue", inputs, context)
            print(f"Get Venue Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'venue' in result, "Response missing 'venue' field"
            return result
        except Exception as e:
            print(f"Error testing get_venue: {e}")
            return None


async def test_create_venue():
    """Test creating a venue."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "organization_id": "your_organization_id_here",
        "name": "Test Venue via Integration",
        "address_1": "123 Test Street",
        "city": "San Francisco",
        "region": "CA",
        "postal_code": "94102",
        "country": "US"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("create_venue", inputs, context)
            print(f"Create Venue Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'venue' in result, "Response missing 'venue' field"
            return result
        except Exception as e:
            print(f"Error testing create_venue: {e}")
            return None


async def test_list_orders_by_event():
    """Test listing orders for an event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "event_id": "your_event_id_here",
        "status": "active"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("list_orders_by_event", inputs, context)
            print(f"List Orders by Event Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'orders' in result, "Response missing 'orders' field"
            if result.get('orders'):
                print(f"  -> Found {len(result['orders'])} order(s)")
            return result
        except Exception as e:
            print(f"Error testing list_orders_by_event: {e}")
            return None


async def test_list_orders_by_organization():
    """Test listing orders for an organization."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "organization_id": "your_organization_id_here",
        "status": "active"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("list_orders_by_organization", inputs, context)
            print(f"List Orders by Organization Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'orders' in result, "Response missing 'orders' field"
            if result.get('orders'):
                print(f"  -> Found {len(result['orders'])} order(s)")
            return result
        except Exception as e:
            print(f"Error testing list_orders_by_organization: {e}")
            return None


async def test_get_order():
    """Test getting a specific order."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "order_id": "your_order_id_here",
        "expand": ["event", "attendees"]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("get_order", inputs, context)
            print(f"Get Order Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'order' in result, "Response missing 'order' field"
            return result
        except Exception as e:
            print(f"Error testing get_order: {e}")
            return None


async def test_list_attendees():
    """Test listing attendees for an event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "event_id": "your_event_id_here",
        "status": "attending"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("list_attendees", inputs, context)
            print(f"List Attendees Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'attendees' in result, "Response missing 'attendees' field"
            if result.get('attendees'):
                print(f"  -> Found {len(result['attendees'])} attendee(s)")
            return result
        except Exception as e:
            print(f"Error testing list_attendees: {e}")
            return None


async def test_get_attendee():
    """Test getting a specific attendee."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "event_id": "your_event_id_here",
        "attendee_id": "your_attendee_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("get_attendee", inputs, context)
            print(f"Get Attendee Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'attendee' in result, "Response missing 'attendee' field"
            return result
        except Exception as e:
            print(f"Error testing get_attendee: {e}")
            return None


async def test_list_ticket_classes():
    """Test listing ticket classes for an event."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"event_id": "your_event_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("list_ticket_classes", inputs, context)
            print(f"List Ticket Classes Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'ticket_classes' in result, "Response missing 'ticket_classes' field"
            if result.get('ticket_classes'):
                print(f"  -> Found {len(result['ticket_classes'])} ticket class(es)")
                for tc in result['ticket_classes']:
                    print(f"     - {tc.get('name')} (ID: {tc.get('id')})")
            return result
        except Exception as e:
            print(f"Error testing list_ticket_classes: {e}")
            return None


async def test_get_ticket_class():
    """Test getting a specific ticket class."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "event_id": "your_event_id_here",
        "ticket_class_id": "your_ticket_class_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("get_ticket_class", inputs, context)
            print(f"Get Ticket Class Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'ticket_class' in result, "Response missing 'ticket_class' field"
            return result
        except Exception as e:
            print(f"Error testing get_ticket_class: {e}")
            return None


async def test_create_ticket_class():
    """Test creating a ticket class."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "event_id": "your_event_id_here",
        "name": "General Admission",
        "quantity_total": 100,
        "free": True,
        "minimum_quantity": 1,
        "maximum_quantity": 10
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("create_ticket_class", inputs, context)
            print(f"Create Ticket Class Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'ticket_class' in result, "Response missing 'ticket_class' field"
            if result.get('ticket_class'):
                print(f"  -> Created ticket class ID: {result['ticket_class'].get('id')}")
            return result
        except Exception as e:
            print(f"Error testing create_ticket_class: {e}")
            return None


async def test_create_paid_ticket_class():
    """Test creating a paid ticket class."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "event_id": "your_event_id_here",
        "name": "VIP Ticket",
        "quantity_total": 50,
        "cost": "USD,5000",  # $50.00
        "minimum_quantity": 1,
        "maximum_quantity": 5
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("create_ticket_class", inputs, context)
            print(f"Create Paid Ticket Class Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'ticket_class' in result, "Response missing 'ticket_class' field"
            return result
        except Exception as e:
            print(f"Error testing create_paid_ticket_class: {e}")
            return None


async def test_update_ticket_class():
    """Test updating a ticket class."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "event_id": "your_event_id_here",
        "ticket_class_id": "your_ticket_class_id_here",
        "name": "Updated Ticket Name",
        "quantity_total": 150
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("update_ticket_class", inputs, context)
            print(f"Update Ticket Class Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'ticket_class' in result, "Response missing 'ticket_class' field"
            return result
        except Exception as e:
            print(f"Error testing update_ticket_class: {e}")
            return None


async def test_delete_ticket_class():
    """Test deleting a ticket class."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {
        "event_id": "your_event_id_here",
        "ticket_class_id": "your_ticket_class_id_here"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("delete_ticket_class", inputs, context)
            print(f"Delete Ticket Class Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            return result
        except Exception as e:
            print(f"Error testing delete_ticket_class: {e}")
            return None


async def test_list_categories():
    """Test listing event categories."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("list_categories", inputs, context)
            print(f"List Categories Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'categories' in result, "Response missing 'categories' field"
            if result.get('categories'):
                print(f"  -> Found {len(result['categories'])} category(ies)")
                for cat in result['categories'][:10]:
                    print(f"     - {cat.get('name')} (ID: {cat.get('id')})")
            return result
        except Exception as e:
            print(f"Error testing list_categories: {e}")
            return None


async def test_get_category():
    """Test getting a specific category."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"category_id": "103"}  # Music category

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("get_category", inputs, context)
            print(f"Get Category Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'category' in result, "Response missing 'category' field"
            return result
        except Exception as e:
            print(f"Error testing get_category: {e}")
            return None


async def test_get_event_description():
    """Test getting event description."""
    auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {
            "access_token": "your_access_token_here"
        }
    }

    inputs = {"event_id": "your_event_id_here"}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await eventbrite.execute_action("get_event_description", inputs, context)
            print(f"Get Event Description Result: {result}")
            assert result.get('result') == True, f"Action failed: {result.get('error', 'Unknown error')}"
            assert 'description' in result, "Response missing 'description' field"
            return result
        except Exception as e:
            print(f"Error testing get_event_description: {e}")
            return None


async def main():
    print("Testing Eventbrite Integration - 27 Actions")
    print("=" * 60)
    print()
    print("NOTE: Replace placeholders with actual values:")
    print("  - your_access_token_here: Your OAuth access token")
    print("  - your_organization_id_here: Your organization ID")
    print("  - your_event_id_here: An event ID")
    print("  - your_venue_id_here: A venue ID")
    print("  - your_order_id_here: An order ID")
    print("  - your_attendee_id_here: An attendee ID")
    print("  - your_ticket_class_id_here: A ticket class ID")
    print()
    print("TIP: Run get_current_user and list_organizations first to get org IDs!")
    print()
    print("=" * 60)
    print()

    # Test user and organization actions
    print("USER & ORGANIZATION DISCOVERY ACTIONS")
    print("-" * 60)
    print("1. Testing get_current_user (discover your user info)...")
    await test_get_current_user()
    print()

    print("2. Testing list_organizations (discover your organization IDs)...")
    await test_list_organizations()
    print()

    print("=" * 60)
    print()
    print("EVENT ACTIONS")
    print("-" * 60)

    print("3. Testing list_events...")
    await test_list_events()
    print()

    print("4. Testing get_event...")
    await test_get_event()
    print()

    print("5. Testing create_event...")
    await test_create_event()
    print()

    print("6. Testing update_event...")
    await test_update_event()
    print()

    print("7. Testing publish_event...")
    await test_publish_event()
    print()

    print("8. Testing unpublish_event...")
    await test_unpublish_event()
    print()

    print("9. Testing copy_event...")
    await test_copy_event()
    print()

    print("10. Testing delete_event...")
    await test_delete_event()
    print()

    print("11. Testing get_event_description...")
    await test_get_event_description()
    print()

    print("=" * 60)
    print()
    print("VENUE ACTIONS")
    print("-" * 60)

    print("12. Testing list_venues...")
    await test_list_venues()
    print()

    print("13. Testing get_venue...")
    await test_get_venue()
    print()

    print("14. Testing create_venue...")
    await test_create_venue()
    print()

    print("=" * 60)
    print()
    print("ORDER ACTIONS")
    print("-" * 60)

    print("15. Testing list_orders_by_event...")
    await test_list_orders_by_event()
    print()

    print("16. Testing list_orders_by_organization...")
    await test_list_orders_by_organization()
    print()

    print("17. Testing get_order...")
    await test_get_order()
    print()

    print("=" * 60)
    print()
    print("ATTENDEE ACTIONS")
    print("-" * 60)

    print("18. Testing list_attendees...")
    await test_list_attendees()
    print()

    print("19. Testing get_attendee...")
    await test_get_attendee()
    print()

    print("=" * 60)
    print()
    print("TICKET CLASS ACTIONS")
    print("-" * 60)

    print("20. Testing list_ticket_classes...")
    await test_list_ticket_classes()
    print()

    print("21. Testing get_ticket_class...")
    await test_get_ticket_class()
    print()

    print("22. Testing create_ticket_class (free)...")
    await test_create_ticket_class()
    print()

    print("23. Testing create_ticket_class (paid)...")
    await test_create_paid_ticket_class()
    print()

    print("24. Testing update_ticket_class...")
    await test_update_ticket_class()
    print()

    print("25. Testing delete_ticket_class...")
    await test_delete_ticket_class()
    print()

    print("=" * 60)
    print()
    print("CATEGORY ACTIONS")
    print("-" * 60)

    print("26. Testing list_categories...")
    await test_list_categories()
    print()

    print("27. Testing get_category...")
    await test_get_category()
    print()

    print("=" * 60)
    print("Testing completed - 27 actions total!")
    print("  - 2 user/organization discovery actions")
    print("  - 9 event management actions")
    print("  - 3 venue management actions")
    print("  - 3 order actions")
    print("  - 2 attendee actions")
    print("  - 6 ticket class actions")
    print("  - 2 category actions")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
