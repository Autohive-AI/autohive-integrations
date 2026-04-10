"""
Shopify Storefront API Integration Tests
========================================

Real API integration testing against Shopify Storefront API.

Prerequisites:
1. Shopify development store
2. Headless channel installed with Storefront access
3. Public or Private storefront access token

Running Tests:
    cd shopify-storefront/tests
    python test_shopify_storefront.py safe      # Read-only tests (products, collections)
    python test_shopify_storefront.py cart      # Cart operation tests
    python test_shopify_storefront.py customer  # Customer tests (creates accounts)
    python test_shopify_storefront.py all       # All tests
"""

import asyncio
import time
import os
from context import shopify_storefront
from autohive_integrations_sdk import ExecutionContext


async def execute_wrapper(action_name, inputs, context):
    """Helper to execute action and unwrap IntegrationResult if needed."""
    result = await shopify_storefront.execute_action(action_name, inputs, context)
    # Support SDK 1.0.2 IntegrationResult
    if hasattr(result, 'result') and hasattr(result.result, 'data'):
        return result.result.data
    return result


# =============================================================================
# CONFIGURATION - Update with your credentials
# =============================================================================
AUTH = {
    "auth_type": "StorefrontPublic",
    "credentials": {
        "public_token": os.getenv("SHOPIFY_STOREFRONT_PUBLIC_TOKEN", "<your-storefront-access-token>"),
        "shop_url": os.getenv("SHOPIFY_STORE_URL", "your-store.myshopify.com")
    }
}

# For private token access (server-side)
AUTH_PRIVATE = {
    "auth_type": "StorefrontPrivate",
    "credentials": {
        "private_token": os.getenv("SHOPIFY_STOREFRONT_PRIVATE_TOKEN", "<your-private-token>"),
        "shop_url": os.getenv("SHOPIFY_STORE_URL", "your-store.myshopify.com")
    }
}

# Test data - will be populated during tests
TEST_PRODUCT_HANDLE = os.getenv("TEST_PRODUCT_HANDLE", "")
TEST_COLLECTION_HANDLE = os.getenv("TEST_COLLECTION_HANDLE", "")
TEST_VARIANT_ID = ""  # Populated from product query
TEST_CART_ID = ""     # Populated from cart creation
TEST_CUSTOMER_ACCESS_TOKEN = ""  # Populated from customer login
# =============================================================================


# -----------------------------------------------------------------------------
# Product Tests (Safe - Read Only)
# -----------------------------------------------------------------------------

async def test_list_products():
    """Test listing products."""
    inputs = {"first": 10}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_list_products", inputs, context)
            print(f"List Products Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert 'products' in result
            print(f"  test_list_products passed - Found {result['count']} products")

            # Store first product handle for subsequent tests
            if result['products']:
                global TEST_PRODUCT_HANDLE
                TEST_PRODUCT_HANDLE = result['products'][0].get('handle', '')
                print(f"  Stored product handle: {TEST_PRODUCT_HANDLE}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_get_product():
    """Test getting a specific product."""
    global TEST_VARIANT_ID

    if not TEST_PRODUCT_HANDLE:
        print("  test_get_product skipped - No product handle available")
        return None

    inputs = {"handle": TEST_PRODUCT_HANDLE}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_get_product", inputs, context)
            print(f"Get Product Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert result.get('product') is not None

            product = result['product']
            print(f"  test_get_product passed - {product.get('title', 'Unknown')}")

            # Extract variant ID for cart tests
            variants = product.get('variants', {}).get('edges', [])
            if variants:
                TEST_VARIANT_ID = variants[0]['node']['id']
                print(f"  Stored variant ID: {TEST_VARIANT_ID}")

            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_search_products():
    """Test searching products."""
    inputs = {"query": "shirt", "first": 5}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_search_products", inputs, context)
            print(f"Search Products Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"  test_search_products passed - Found {result['count']} products")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_list_collections():
    """Test listing collections."""
    global TEST_COLLECTION_HANDLE

    inputs = {"first": 10}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_list_collections", inputs, context)
            print(f"List Collections Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert 'collections' in result
            print(f"  test_list_collections passed - Found {result['count']} collections")

            if result['collections']:
                TEST_COLLECTION_HANDLE = result['collections'][0].get('handle', '')
                print(f"  Stored collection handle: {TEST_COLLECTION_HANDLE}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_get_collection():
    """Test getting a specific collection."""
    if not TEST_COLLECTION_HANDLE:
        print("  test_get_collection skipped - No collection handle available")
        return None

    inputs = {"handle": TEST_COLLECTION_HANDLE, "products_first": 5}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_get_collection", inputs, context)
            print(f"Get Collection Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert result.get('collection') is not None
            print(f"  test_get_collection passed - {result['collection'].get('title', 'Unknown')}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Cart Tests (Low Risk - Creates temporary carts)
# -----------------------------------------------------------------------------

async def test_create_cart():
    """Test creating an empty cart."""
    global TEST_CART_ID

    inputs = {}  # Empty cart
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_create_cart", inputs, context)
            print(f"Create Cart Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert result.get('cart') is not None

            TEST_CART_ID = result['cart']['id']
            print(f"  test_create_cart passed - Cart ID: {TEST_CART_ID[:50]}...")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_add_to_cart():
    """Test adding items to cart."""
    if not TEST_CART_ID:
        print("  test_add_to_cart skipped - No cart ID available")
        return None
    if not TEST_VARIANT_ID:
        print("  test_add_to_cart skipped - No variant ID available")
        return None

    inputs = {
        "cart_id": TEST_CART_ID,
        "lines": [{"merchandiseId": TEST_VARIANT_ID, "quantity": 2}]
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_add_to_cart", inputs, context)
            print(f"Add to Cart Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"  test_add_to_cart passed - Total quantity: {result['cart'].get('totalQuantity', 0)}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_get_cart():
    """Test getting cart contents."""
    if not TEST_CART_ID:
        print("  test_get_cart skipped - No cart ID available")
        return None

    inputs = {"cart_id": TEST_CART_ID}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_get_cart", inputs, context)
            print(f"Get Cart Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"

            cart = result.get('cart', {})
            print(f"  test_get_cart passed - Items: {cart.get('totalQuantity', 0)}, Checkout: {cart.get('checkoutUrl', 'N/A')[:50]}...")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_update_cart_line():
    """Test updating cart line quantity."""
    if not TEST_CART_ID:
        print("  test_update_cart_line skipped - No cart ID available")
        return None

    # First get cart to get line IDs
    get_inputs = {"cart_id": TEST_CART_ID}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            cart_result = await shopify_storefront.execute_action("storefront_get_cart", get_inputs, context)
            if not cart_result.get('success') or not cart_result.get('cart'):
                print("  test_update_cart_line skipped - Could not get cart")
                return None

            lines = cart_result['cart'].get('lines', {}).get('edges', [])
            if not lines:
                print("  test_update_cart_line skipped - Cart is empty")
                return None

            line_id = lines[0]['node']['id']

            # Update quantity
            update_inputs = {
                "cart_id": TEST_CART_ID,
                "lines": [{"id": line_id, "quantity": 3}]
            }
            result = await execute_wrapper("storefront_update_cart_line", update_inputs, context)
            print(f"Update Cart Line Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"  test_update_cart_line passed - New total: {result['cart'].get('totalQuantity', 0)}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_remove_from_cart():
    """Test removing items from cart."""
    if not TEST_CART_ID:
        print("  test_remove_from_cart skipped - No cart ID available")
        return None

    # First get cart to get line IDs
    get_inputs = {"cart_id": TEST_CART_ID}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            cart_result = await shopify_storefront.execute_action("storefront_get_cart", get_inputs, context)
            if not cart_result.get('success') or not cart_result.get('cart'):
                print("  test_remove_from_cart skipped - Could not get cart")
                return None

            lines = cart_result['cart'].get('lines', {}).get('edges', [])
            if not lines:
                print("  test_remove_from_cart skipped - Cart is empty")
                return None

            line_ids = [line['node']['id'] for line in lines]

            # Remove all items
            remove_inputs = {
                "cart_id": TEST_CART_ID,
                "line_ids": line_ids
            }
            result = await execute_wrapper("storefront_remove_from_cart", remove_inputs, context)
            print(f"Remove from Cart Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"  test_remove_from_cart passed - Remaining: {result['cart'].get('totalQuantity', 0)}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Customer Tests (Medium Risk - Creates customer accounts)
# -----------------------------------------------------------------------------

async def test_create_customer():
    """Test creating a new customer."""
    timestamp = int(time.time())
    email = f"test.customer.{timestamp}@example.com"

    inputs = {
        "email": email,
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "Customer"
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_create_customer", inputs, context)
            print(f"Create Customer Result: {result}")
            # Note: May fail if customer registration is disabled
            if result.get('success'):
                print(f"  test_create_customer passed - Email: {email}")
            else:
                print(f"  test_create_customer - Note: {result.get('message')}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_customer_login():
    """Test customer login."""
    global TEST_CUSTOMER_ACCESS_TOKEN

    # Use environment variable for test credentials
    email = os.getenv("TEST_CUSTOMER_EMAIL", "test@example.com")
    password = os.getenv("TEST_CUSTOMER_PASSWORD", "TestPassword123!")

    inputs = {"email": email, "password": password}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_customer_login", inputs, context)
            print(f"Customer Login Result: {result}")
            if result.get('success') and result.get('customer_access_token'):
                TEST_CUSTOMER_ACCESS_TOKEN = result['customer_access_token']
                print(f"  test_customer_login passed - Token expires: {result.get('expires_at')}")
            else:
                print(f"  test_customer_login - Note: {result.get('message')}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_get_customer():
    """Test getting customer profile."""
    if not TEST_CUSTOMER_ACCESS_TOKEN:
        print("  test_get_customer skipped - No access token available")
        return None

    inputs = {"customer_access_token": TEST_CUSTOMER_ACCESS_TOKEN}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_get_customer", inputs, context)
            print(f"Get Customer Result: {result}")
            if result.get('success'):
                customer = result.get('customer', {})
                print(f"  test_get_customer passed - {customer.get('email')}")
            else:
                print(f"  test_get_customer - Note: {result.get('message')}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


async def test_recover_customer():
    """Test password recovery email."""
    email = os.getenv("TEST_CUSTOMER_EMAIL", "test@example.com")

    inputs = {"email": email}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("storefront_recover_customer", inputs, context)
            print(f"Recover Customer Result: {result}")
            if result.get('success'):
                print(f"  test_recover_customer passed - Recovery email sent")
            else:
                print(f"  test_recover_customer - Note: {result.get('message')}")
            return result
        except Exception as e:
            print(f"  Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Test Runners
# -----------------------------------------------------------------------------

async def run_safe_tests():
    """Run read-only tests (products, collections)."""
    print("\n" + "=" * 60)
    print("RUNNING SAFE (READ-ONLY) TESTS")
    print("=" * 60 + "\n")

    tests = [
        ("List Products", test_list_products),
        ("Get Product", test_get_product),
        ("Search Products", test_search_products),
        ("List Collections", test_list_collections),
        ("Get Collection", test_get_collection),
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
        await asyncio.sleep(0.5)  # Rate limit buffer

    print("\n" + "=" * 60)
    print(f"SAFE TESTS: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")


async def run_cart_tests():
    """Run cart operation tests."""
    print("\n" + "=" * 60)
    print("RUNNING CART TESTS")
    print("=" * 60 + "\n")

    # Need product data first
    if not TEST_VARIANT_ID:
        print("Getting product data for cart tests...")
        await test_list_products()
        await test_get_product()

    tests = [
        ("Create Cart", test_create_cart),
        ("Add to Cart", test_add_to_cart),
        ("Get Cart", test_get_cart),
        ("Update Cart Line", test_update_cart_line),
        ("Remove from Cart", test_remove_from_cart),
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
    print(f"CART TESTS: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")


async def run_customer_tests():
    """Run customer account tests."""
    print("\n" + "=" * 60)
    print("RUNNING CUSTOMER TESTS")
    print("=" * 60 + "\n")

    tests = [
        ("Create Customer", test_create_customer),
        ("Customer Login", test_customer_login),
        ("Get Customer", test_get_customer),
        ("Recover Customer", test_recover_customer),
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
    print(f"CUSTOMER TESTS: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")


async def run_all_tests():
    """Run all tests."""
    await run_safe_tests()
    await run_cart_tests()
    await run_customer_tests()


def main():
    """Main entry point."""
    import sys

    test_type = sys.argv[1] if len(sys.argv) > 1 else "safe"

    print("\n" + "=" * 60)
    print("SHOPIFY STOREFRONT API INTEGRATION TESTS")
    print("=" * 60)
    print(f"Store: {AUTH['credentials'].get('shop_url', 'Not configured')}")
    print(f"Test Type: {test_type}")
    print("=" * 60 + "\n")

    if test_type == "safe":
        asyncio.run(run_safe_tests())
    elif test_type == "cart":
        asyncio.run(run_cart_tests())
    elif test_type == "customer":
        asyncio.run(run_customer_tests())
    elif test_type == "all":
        asyncio.run(run_all_tests())
    else:
        print(f"Unknown test type: {test_type}")
        print("Usage: python test_shopify_storefront.py [safe|cart|customer|all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
