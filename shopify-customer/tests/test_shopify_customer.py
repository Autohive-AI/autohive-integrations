"""
Shopify Customer Account API Integration Tests
===============================================

Real API integration testing against Shopify Customer Account API.

Prerequisites:
1. Shopify development store with customer accounts enabled
2. OAuth client configured in Headless channel
3. Customer access token obtained via OAuth flow

Running Tests:
    cd shopify-customer/tests
    python test_shopify_customer.py safe      # Read-only tests (profile, addresses, orders)
    python test_shopify_customer.py profile   # Profile modification tests
    python test_shopify_customer.py orders    # Order tests
    python test_shopify_customer.py all       # All tests

Note: You must complete the OAuth flow manually first to obtain an access token.
See docs/OAUTH_PKCE.md for instructions.
"""

import asyncio
import os
from context import shopify_customer
from autohive_integrations_sdk import ExecutionContext


async def execute_wrapper(action_name, inputs, context):
    """Helper to execute action and unwrap IntegrationResult if needed."""
    result = await shopify_customer.execute_action(action_name, inputs, context)
    # Support SDK 1.0.2 IntegrationResult
    if hasattr(result, 'result') and hasattr(result.result, 'data'):
        return result.result.data
    return result


# =============================================================================
# CONFIGURATION - Update with your credentials
# =============================================================================
AUTH = {
    "auth_type": "CustomerAccountOAuth",
    "credentials": {
        "access_token": os.getenv("SHOPIFY_CUSTOMER_ACCESS_TOKEN", "<your-customer-access-token>"),
        "refresh_token": os.getenv("SHOPIFY_CUSTOMER_REFRESH_TOKEN", ""),
        "shop_url": os.getenv("SHOPIFY_STORE_URL", "your-store.myshopify.com"),
        "client_id": os.getenv("SHOPIFY_CLIENT_ID", "<your-client-id>")
    }
}

# Test data - will be populated during tests
TEST_ADDRESS_ID = ""  # Created during address tests
TEST_ORDER_ID = os.getenv("TEST_ORDER_ID", "")  # Existing order ID
# =============================================================================


# -----------------------------------------------------------------------------
# Profile Tests (Safe - Read Only)
# -----------------------------------------------------------------------------

async def test_get_profile():
    """Test getting customer profile."""
    inputs = {}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("customer_get_profile", inputs, context)
            print(f"Get Profile Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert result.get('customer') is not None

            customer = result['customer']
            print(f"  test_get_profile passed - {customer.get('email', 'No email')}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_list_addresses():
    """Test listing customer addresses."""
    global TEST_ADDRESS_ID

    inputs = {"first": 10}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("customer_list_addresses", inputs, context)
            print(f"List Addresses Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert 'addresses' in result

            print(f"  test_list_addresses passed - Found {result['count']} addresses")
            if result.get('default_address_id'):
                print(f"  Default address: {result['default_address_id'][:50]}...")

            # Store first address ID for later tests
            if result['addresses']:
                TEST_ADDRESS_ID = result['addresses'][0].get('id', '')

            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_list_orders():
    """Test listing customer orders."""
    global TEST_ORDER_ID

    inputs = {"first": 10}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("customer_list_orders", inputs, context)
            print(f"List Orders Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert 'orders' in result

            print(f"  test_list_orders passed - Found {result['count']} orders")

            # Store first order ID for later tests
            if result['orders'] and not TEST_ORDER_ID:
                TEST_ORDER_ID = result['orders'][0].get('id', '')
                print(f"  Stored order ID: {TEST_ORDER_ID[:50]}...")

            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_get_order():
    """Test getting a specific order."""
    if not TEST_ORDER_ID:
        print("  test_get_order skipped - No order ID available")
        return None

    inputs = {"order_id": TEST_ORDER_ID}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("customer_get_order", inputs, context)
            print(f"Get Order Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"

            order = result.get('order', {})
            print(f"  test_get_order passed - Order #{order.get('orderNumber', 'N/A')}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Profile Modification Tests
# -----------------------------------------------------------------------------

async def test_update_profile():
    """Test updating customer profile."""
    # First get current profile to save original values
    async with ExecutionContext(auth=AUTH) as context:
        try:
            # Get current profile
            current = await shopify_customer.execute_action("customer_get_profile", {}, context)
            if not current.get('success'):
                print(f"  test_update_profile skipped - Could not get profile")
                return None

            original_phone = current['customer'].get('phone')

            # Update phone
            update_inputs = {"phone": "+1234567890"}
            result = await execute_wrapper("customer_update_profile", update_inputs, context)
            print(f"Update Profile Result: {result}")

            if result.get('success'):
                print(f"  test_update_profile passed - Phone updated")

                # Restore original phone
                if original_phone:
                    restore_inputs = {"phone": original_phone}
                    await shopify_customer.execute_action("customer_update_profile", restore_inputs, context)
                    print(f"  Restored original phone")
            else:
                print(f"  test_update_profile - Note: {result.get('message')}")

            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Address Tests
# -----------------------------------------------------------------------------

async def test_create_address():
    """Test creating a new address."""
    global TEST_ADDRESS_ID

    inputs = {
        "address1": "123 Test Street",
        "city": "Test City",
        "province": "CA",
        "country": "US",
        "zip": "90210",
        "phone": "+1555123456",
        "first_name": "Test",
        "last_name": "Address"
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("customer_create_address", inputs, context)
            print(f"Create Address Result: {result}")

            if result.get('success'):
                address = result.get('address', {})
                TEST_ADDRESS_ID = address.get('id', '')
                print(f"  test_create_address passed - ID: {TEST_ADDRESS_ID[:50]}...")
            else:
                print(f"  test_create_address - Note: {result.get('message')}")

            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_update_address():
    """Test updating an address."""
    if not TEST_ADDRESS_ID:
        print("  test_update_address skipped - No address ID available")
        return None

    inputs = {
        "address_id": TEST_ADDRESS_ID,
        "city": "Updated City"
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("customer_update_address", inputs, context)
            print(f"Update Address Result: {result}")

            if result.get('success'):
                print(f"  test_update_address passed - City updated")
            else:
                print(f"  test_update_address - Note: {result.get('message')}")

            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_set_default_address():
    """Test setting default address."""
    if not TEST_ADDRESS_ID:
        print("  test_set_default_address skipped - No address ID available")
        return None

    inputs = {"address_id": TEST_ADDRESS_ID}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("customer_set_default_address", inputs, context)
            print(f"Set Default Address Result: {result}")

            if result.get('success'):
                print(f"  test_set_default_address passed")
            else:
                print(f"  test_set_default_address - Note: {result.get('message')}")

            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_delete_address():
    """Test deleting an address."""
    if not TEST_ADDRESS_ID:
        print("  test_delete_address skipped - No address ID available")
        return None

    inputs = {"address_id": TEST_ADDRESS_ID}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("customer_delete_address", inputs, context)
            print(f"Delete Address Result: {result}")

            if result.get('success'):
                print(f"  test_delete_address passed - Address deleted")
            else:
                print(f"  test_delete_address - Note: {result.get('message')}")

            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


# -----------------------------------------------------------------------------
# OAuth Helper Tests
# -----------------------------------------------------------------------------

async def test_generate_oauth_url():
    """Test generating OAuth authorization URL."""
    inputs = {
        "client_id": AUTH['credentials'].get('client_id', 'test-client-id'),
        "redirect_uri": "https://localhost:3000/callback",
        "scopes": ["customer_read_customers", "customer_read_orders"]
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("customer_generate_oauth_url", inputs, context)
            print(f"Generate OAuth URL Result: {result}")

            if result.get('success'):
                print(f"  test_generate_oauth_url passed")
                print(f"  Authorization URL: {result.get('authorization_url', '')[:80]}...")
                print(f"  State: {result.get('state')}")
                # Note: code_verifier should be stored securely for token exchange
            else:
                print(f"  test_generate_oauth_url - Note: {result.get('message')}")

            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_refresh_token():
    """Test refreshing access token."""
    refresh_token = AUTH['credentials'].get('refresh_token')
    client_id = AUTH['credentials'].get('client_id')

    if not refresh_token or refresh_token == "":
        print("  test_refresh_token skipped - No refresh token available")
        return None

    inputs = {
        "refresh_token": refresh_token,
        "client_id": client_id
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("customer_refresh_token", inputs, context)
            print(f"Refresh Token Result: {result}")

            if result.get('success'):
                print(f"  test_refresh_token passed - New token expires in {result.get('expires_in')} seconds")
            else:
                print(f"  test_refresh_token - Note: {result.get('message')}")

            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Test Runners
# -----------------------------------------------------------------------------

async def run_safe_tests():
    """Run read-only tests."""
    print("\n" + "=" * 60)
    print("RUNNING SAFE (READ-ONLY) TESTS")
    print("=" * 60 + "\n")

    tests = [
        ("Get Profile", test_get_profile),
        ("List Addresses", test_list_addresses),
        ("List Orders", test_list_orders),
        ("Get Order", test_get_order),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"\n--- Testing: {name} ---")
        result = await test_func()
        if result and result.get('success'):
            passed += 1
        else:
            failed += 1
        await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"SAFE TESTS: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")


async def run_profile_tests():
    """Run profile and address tests."""
    print("\n" + "=" * 60)
    print("RUNNING PROFILE & ADDRESS TESTS")
    print("=" * 60 + "\n")

    tests = [
        ("Update Profile", test_update_profile),
        ("Create Address", test_create_address),
        ("Update Address", test_update_address),
        ("Set Default Address", test_set_default_address),
        ("Delete Address", test_delete_address),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"\n--- Testing: {name} ---")
        result = await test_func()
        if result and result.get('success'):
            passed += 1
        else:
            failed += 1
        await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"PROFILE TESTS: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")


async def run_orders_tests():
    """Run order tests."""
    print("\n" + "=" * 60)
    print("RUNNING ORDER TESTS")
    print("=" * 60 + "\n")

    tests = [
        ("List Orders", test_list_orders),
        ("Get Order", test_get_order),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"\n--- Testing: {name} ---")
        result = await test_func()
        if result and result.get('success'):
            passed += 1
        else:
            failed += 1
        await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"ORDER TESTS: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")


async def run_oauth_tests():
    """Run OAuth helper tests."""
    print("\n" + "=" * 60)
    print("RUNNING OAUTH HELPER TESTS")
    print("=" * 60 + "\n")

    tests = [
        ("Generate OAuth URL", test_generate_oauth_url),
        ("Refresh Token", test_refresh_token),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"\n--- Testing: {name} ---")
        result = await test_func()
        if result and result.get('success'):
            passed += 1
        else:
            failed += 1
        await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"OAUTH TESTS: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")


async def run_all_tests():
    """Run all tests."""
    await run_safe_tests()
    await run_profile_tests()
    await run_oauth_tests()


def main():
    """Main entry point."""
    import sys

    test_type = sys.argv[1] if len(sys.argv) > 1 else "safe"

    print("\n" + "=" * 60)
    print("SHOPIFY CUSTOMER ACCOUNT API INTEGRATION TESTS")
    print("=" * 60)
    print(f"Store: {AUTH['credentials'].get('shop_url', 'Not configured')}")
    print(f"Test Type: {test_type}")
    print("=" * 60 + "\n")

    if test_type == "safe":
        asyncio.run(run_safe_tests())
    elif test_type == "profile":
        asyncio.run(run_profile_tests())
    elif test_type == "orders":
        asyncio.run(run_orders_tests())
    elif test_type == "oauth":
        asyncio.run(run_oauth_tests())
    elif test_type == "all":
        asyncio.run(run_all_tests())
    else:
        print(f"Unknown test type: {test_type}")
        print("Usage: python test_shopify_customer.py [safe|profile|orders|oauth|all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
