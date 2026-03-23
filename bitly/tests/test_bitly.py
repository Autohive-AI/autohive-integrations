# Test suite for Bitly integration
import asyncio
from context import bitly
from autohive_integrations_sdk import ExecutionContext


# Test credentials - replace with your actual OAuth token
TEST_AUTH = {
    "auth_type": "PlatformOauth2",
    "credentials": {
        "access_token": "your_access_token_here"
    }
}


# ---- User Tests ----

async def test_get_user():
    """Test getting current user information."""
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("get_user", {}, context)
            print(f"Get User Result: {result}")
            assert result.data.get('result') == True
            assert 'user' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_user: {e}")
            return None


# ---- Link Management Tests ----

async def test_shorten_url():
    """Test shortening a URL."""
    inputs = {"long_url": "https://www.example.com/very/long/url/path"}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("shorten_url", inputs, context)
            print(f"Shorten URL Result: {result}")
            assert result.data.get('result') == True
            assert 'bitlink' in result.data
            return result
        except Exception as e:
            print(f"Error testing shorten_url: {e}")
            return None


async def test_create_bitlink():
    """Test creating a bitlink with options."""
    inputs = {
        "long_url": "https://www.example.com/another/url",
        "title": "Test Link",
        "tags": ["test", "autohive"]
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("create_bitlink", inputs, context)
            print(f"Create Bitlink Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing create_bitlink: {e}")
            return None


async def test_get_bitlink():
    """Test getting bitlink information."""
    inputs = {"bitlink": "bit.ly/example"}  # Replace with actual bitlink

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("get_bitlink", inputs, context)
            print(f"Get Bitlink Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing get_bitlink: {e}")
            return None


async def test_update_bitlink():
    """Test updating a bitlink."""
    inputs = {
        "bitlink": "bit.ly/example",  # Replace with actual bitlink
        "title": "Updated Title"
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("update_bitlink", inputs, context)
            print(f"Update Bitlink Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing update_bitlink: {e}")
            return None


async def test_expand_bitlink():
    """Test expanding a bitlink to get original URL."""
    inputs = {"bitlink": "bit.ly/example"}  # Replace with actual bitlink

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("expand_bitlink", inputs, context)
            print(f"Expand Bitlink Result: {result}")
            assert result.data.get('result') == True
            assert 'long_url' in result.data
            return result
        except Exception as e:
            print(f"Error testing expand_bitlink: {e}")
            return None


async def test_list_bitlinks():
    """Test listing bitlinks."""
    inputs = {"size": 10}

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("list_bitlinks", inputs, context)
            print(f"List Bitlinks Result: {result}")
            assert result.data.get('result') == True
            assert 'bitlinks' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_bitlinks: {e}")
            return None


# ---- Click Analytics Tests ----

async def test_get_clicks():
    """Test getting click counts."""
    inputs = {
        "bitlink": "bit.ly/example",  # Replace with actual bitlink
        "unit": "day",
        "units": 7
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("get_clicks", inputs, context)
            print(f"Get Clicks Result: {result}")
            assert result.data.get('result') == True
            assert 'clicks' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_clicks: {e}")
            return None


async def test_get_clicks_summary():
    """Test getting clicks summary."""
    inputs = {
        "bitlink": "bit.ly/example",  # Replace with actual bitlink
        "unit": "day",
        "units": 30
    }

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("get_clicks_summary", inputs, context)
            print(f"Get Clicks Summary Result: {result}")
            assert result.data.get('result') == True
            assert 'total_clicks' in result.data
            return result
        except Exception as e:
            print(f"Error testing get_clicks_summary: {e}")
            return None


# ---- Group & Organization Tests ----

async def test_list_groups():
    """Test listing groups."""
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("list_groups", {}, context)
            print(f"List Groups Result: {result}")
            assert result.data.get('result') == True
            assert 'groups' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_groups: {e}")
            return None


async def test_get_group():
    """Test getting a group."""
    inputs = {"group_guid": "your_group_guid"}  # Replace with actual group GUID

    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("get_group", inputs, context)
            print(f"Get Group Result: {result}")
            assert result.data.get('result') == True
            return result
        except Exception as e:
            print(f"Error testing get_group: {e}")
            return None


async def test_list_organizations():
    """Test listing organizations."""
    async with ExecutionContext(auth=TEST_AUTH) as context:
        try:
            result = await bitly.execute_action("list_organizations", {}, context)
            print(f"List Organizations Result: {result}")
            assert result.data.get('result') == True
            assert 'organizations' in result.data
            return result
        except Exception as e:
            print(f"Error testing list_organizations: {e}")
            return None


# Main test runner
async def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("Bitly Integration Test Suite")
    print("=" * 60)
    print()
    print("NOTE: Replace placeholders with actual values:")
    print("  - your_access_token_here: Your OAuth access token")
    print("  - bit.ly/example: Replace with actual bitlinks")
    print("  - your_group_guid: Replace with actual group GUID")
    print()
    print("TIP: Run get_user and list_groups first to discover IDs!")
    print()

    test_functions = [
        # User
        ("Get User", test_get_user),
        # Link Management
        ("Shorten URL", test_shorten_url),
        ("Create Bitlink", test_create_bitlink),
        ("Get Bitlink", test_get_bitlink),
        ("Update Bitlink", test_update_bitlink),
        ("Expand Bitlink", test_expand_bitlink),
        ("List Bitlinks", test_list_bitlinks),
        # Click Analytics
        ("Get Clicks", test_get_clicks),
        ("Get Clicks Summary", test_get_clicks_summary),
        # Groups & Organizations
        ("List Groups", test_list_groups),
        ("Get Group", test_get_group),
        ("List Organizations", test_list_organizations),
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
