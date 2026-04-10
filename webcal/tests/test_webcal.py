# Test suite for Webcal integration
import asyncio
from context import webcal
from autohive_integrations_sdk import ExecutionContext

# Test configuration - No authentication required for webcal
TEST_AUTH = {
    "credentials": {}
}

# Public test calendar URLs
# Using public iCal feeds for testing
TEST_WEBCAL_URL = "https://www.calendarlabs.com/ical-calendar/ics/76/US_Holidays.ics"
TEST_WEBCAL_URL_ALT = "webcal://www.calendarlabs.com/ical-calendar/ics/76/US_Holidays.ics"


async def test_fetch_events_basic():
    """Test fetching events with default settings."""
    print("\n[TEST] Fetching events with default settings...")

    inputs = {
        "webcal_url": TEST_WEBCAL_URL
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await webcal.execute_action("fetch_events", inputs, context)

            # Access the ActionResult's data field
            response_data = result.result.data

            assert response_data.get("result") is True, "Should have result=True"
            assert response_data.get("timezone") == "UTC", "Default timezone should be UTC"
            assert "events" in response_data, "Should return events array"

            events = response_data["events"]
            print(f"✓ Found {len(events)} event(s) in next 7 days")

            if events:
                event = events[0]
                print(f"  First event: {event.get('summary', 'Unnamed')}")
                print(f"  Start: {event.get('start_time')}")
                print(f"  All-day: {event.get('all_day')}")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_fetch_events_with_timezone():
    """Test fetching events with a specific timezone."""
    print("\n[TEST] Fetching events with Pacific/Auckland timezone...")

    inputs = {
        "webcal_url": TEST_WEBCAL_URL,
        "timezone": "Pacific/Auckland",
        "look_ahead_days": 30
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await webcal.execute_action("fetch_events", inputs, context)

            response_data = result.result.data

            assert response_data.get("result") is True, "Should have result=True"
            assert response_data.get("timezone") == "Pacific/Auckland", "Should use specified timezone"

            events = response_data["events"]
            print(f"✓ Found {len(events)} event(s) in next 30 days (Pacific/Auckland)")

            if events:
                for i, event in enumerate(events[:3]):
                    print(f"  - {event.get('summary')}: {event.get('start_time')}")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_fetch_events_webcal_protocol():
    """Test fetching events using webcal:// protocol URL."""
    print("\n[TEST] Fetching events with webcal:// protocol...")

    inputs = {
        "webcal_url": TEST_WEBCAL_URL_ALT,
        "look_ahead_days": 60
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await webcal.execute_action("fetch_events", inputs, context)

            response_data = result.result.data

            assert response_data.get("result") is True, "Should have result=True"

            events = response_data["events"]
            print(f"✓ Successfully fetched {len(events)} event(s) using webcal:// URL")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_fetch_events_extended_range():
    """Test fetching events with extended look-ahead range."""
    print("\n[TEST] Fetching events with 90-day look-ahead...")

    inputs = {
        "webcal_url": TEST_WEBCAL_URL,
        "timezone": "America/New_York",
        "look_ahead_days": 90
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await webcal.execute_action("fetch_events", inputs, context)

            response_data = result.result.data

            assert response_data.get("result") is True, "Should have result=True"

            events = response_data["events"]
            print(f"✓ Found {len(events)} event(s) in next 90 days")

            # Check event structure
            if events:
                event = events[0]
                required_fields = ['summary', 'start_time', 'end_time', 'all_day']
                for field in required_fields:
                    assert field in event, f"Event should have {field} field"
                print(f"  ✓ Event structure validated")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_search_events_basic():
    """Test searching events with a search term."""
    print("\n[TEST] Searching events for 'Day'...")

    inputs = {
        "webcal_url": TEST_WEBCAL_URL,
        "search_term": "Day",
        "look_ahead_days": 365
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await webcal.execute_action("search_events", inputs, context)

            response_data = result.result.data

            assert response_data.get("result") is True, "Should have result=True"
            assert response_data.get("search_term") == "Day", "Should return search term"
            assert "events" in response_data, "Should return events array"

            events = response_data["events"]
            print(f"✓ Found {len(events)} event(s) matching 'Day'")

            if events:
                for i, event in enumerate(events[:5]):
                    print(f"  - {event.get('summary')} (matched in: {event.get('match_field')})")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_search_events_case_insensitive():
    """Test case-insensitive search."""
    print("\n[TEST] Testing case-insensitive search...")

    inputs = {
        "webcal_url": TEST_WEBCAL_URL,
        "search_term": "day",  # lowercase
        "case_sensitive": False,
        "look_ahead_days": 365
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await webcal.execute_action("search_events", inputs, context)

            response_data = result.result.data

            assert response_data.get("result") is True, "Should have result=True"

            events = response_data["events"]
            print(f"✓ Found {len(events)} event(s) with case-insensitive search")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_search_events_case_sensitive():
    """Test case-sensitive search."""
    print("\n[TEST] Testing case-sensitive search...")

    inputs = {
        "webcal_url": TEST_WEBCAL_URL,
        "search_term": "day",  # lowercase - might not match "Day"
        "case_sensitive": True,
        "look_ahead_days": 365
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await webcal.execute_action("search_events", inputs, context)

            response_data = result.result.data

            assert response_data.get("result") is True, "Should have result=True"

            events = response_data["events"]
            print(f"✓ Found {len(events)} event(s) with case-sensitive search")
            print(f"  (May differ from case-insensitive results)")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_search_events_no_results():
    """Test search with term that shouldn't match anything."""
    print("\n[TEST] Searching for non-existent term...")

    inputs = {
        "webcal_url": TEST_WEBCAL_URL,
        "search_term": "xyznonexistent123",
        "look_ahead_days": 365
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await webcal.execute_action("search_events", inputs, context)

            response_data = result.result.data

            assert response_data.get("result") is True, "Should have result=True even with no matches"

            events = response_data["events"]
            print(f"✓ Found {len(events)} event(s) (expected 0)")
            assert len(events) == 0, "Should find no events for non-existent term"

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_search_events_with_timezone():
    """Test search with specific timezone."""
    print("\n[TEST] Searching events with Europe/London timezone...")

    inputs = {
        "webcal_url": TEST_WEBCAL_URL,
        "search_term": "Day",
        "timezone": "Europe/London",
        "look_ahead_days": 180
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await webcal.execute_action("search_events", inputs, context)

            response_data = result.result.data

            assert response_data.get("result") is True, "Should have result=True"
            assert response_data.get("timezone") == "Europe/London", "Should use specified timezone"

            events = response_data["events"]
            print(f"✓ Found {len(events)} event(s) in Europe/London timezone")

            return result

        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def main():
    print("=" * 70)
    print("Webcal Integration Test Suite")
    print("=" * 70)
    print("\n📝 TEST CONFIGURATION:")
    print(f"   Calendar URL: {TEST_WEBCAL_URL}")
    print("   Authentication: None required (public feeds)")
    print("\n" + "=" * 70)

    try:
        # Test fetch_events action
        print("\n" + "=" * 70)
        print("FETCH EVENTS (4 tests)")
        print("=" * 70)
        await test_fetch_events_basic()
        await test_fetch_events_with_timezone()
        await test_fetch_events_webcal_protocol()
        await test_fetch_events_extended_range()

        # Test search_events action
        print("\n" + "=" * 70)
        print("SEARCH EVENTS (5 tests)")
        print("=" * 70)
        await test_search_events_basic()
        await test_search_events_case_insensitive()
        await test_search_events_case_sensitive()
        await test_search_events_no_results()
        await test_search_events_with_timezone()

        print("\n" + "=" * 70)
        print("✓ Test suite completed!")
        print("=" * 70)
        print("\n📊 Summary: 9 tests executed")
        print("  - fetch_events: 4 tests")
        print("  - search_events: 5 tests")
        print("  - No authentication required")
        print("  - No costs (free public calendar feeds)")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
