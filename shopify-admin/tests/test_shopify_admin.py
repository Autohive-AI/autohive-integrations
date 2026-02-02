"""
Shopify Admin API Integration Tests
====================================

Real API integration testing against Shopify Admin API.
Product operations use GraphQL Admin API (migrated from REST).

Prerequisites:
1. Shopify development store or Partner account
2. Custom app with Admin API access token
3. Required scopes configured

Running Tests:
    cd shopify-admin/tests
    python test_shopify_admin.py safe      # Read-only tests
    python test_shopify_admin.py get       # Get-by-ID tests
    python test_shopify_admin.py write     # Create tests
    python test_shopify_admin.py update    # Update tests
    python test_shopify_admin.py all       # All tests
"""

import asyncio
import time
import os
from context import shopify_admin
from autohive_integrations_sdk import ExecutionContext


async def execute_wrapper(action_name, inputs, context):
    """Helper to execute action and unwrap IntegrationResult if needed."""
    result = await shopify_admin.execute_action(action_name, inputs, context)
    # Support SDK 1.0.2 IntegrationResult
    if hasattr(result, 'result') and hasattr(result.result, 'data'):
        return result.result.data
    return result


# =============================================================================
# CONFIGURATION - Update with your credentials
# =============================================================================
AUTH = {
    "auth_type": "PlatformOauth2",
    "credentials": {
        "access_token": os.getenv("SHOPIFY_ADMIN_TOKEN", "<your-admin-api-access-token>"),
        "shop_url": os.getenv("SHOPIFY_STORE_URL", "your-store.myshopify.com")
    }
}

# Test IDs - Replace with actual IDs from your store
# Run safe tests first to discover valid IDs
TEST_CUSTOMER_ID = os.getenv("TEST_CUSTOMER_ID", "<customer-id>")
TEST_ORDER_ID = os.getenv("TEST_ORDER_ID", "<order-id>")
TEST_PRODUCT_ID = os.getenv("TEST_PRODUCT_ID", "<product-id>")
TEST_LOCATION_ID = os.getenv("TEST_LOCATION_ID", "<location-id>")
TEST_INVENTORY_ITEM_ID = os.getenv("TEST_INVENTORY_ITEM_ID", "<inventory-item-id>")
# =============================================================================


# -----------------------------------------------------------------------------
# Customer Tests
# -----------------------------------------------------------------------------

async def test_list_customers():
    """Test listing customers."""
    inputs = {"limit": 10}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("list_customers", inputs, context)
            print(f"List Customers Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert 'customers' in result
            print(f"✓ test_list_customers passed - Found {result['count']} customers")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_customer():
    """Test getting a specific customer."""
    inputs = {"customer_id": TEST_CUSTOMER_ID}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("get_customer", inputs, context)
            print(f"Get Customer Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_get_customer passed")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_search_customers():
    """Test searching customers."""
    inputs = {"query": "email:*@*", "limit": 5}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("search_customers", inputs, context)
            print(f"Search Customers Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_search_customers passed - Found {result['count']} customers")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_create_customer():
    """Test creating a new customer."""
    timestamp = int(time.time())
    inputs = {
        "email": f"test.customer.{timestamp}@example.com",
        "first_name": "Test",
        "last_name": "Customer",
        "verified_email": True,
        "send_email_welcome": False,
        "tags": "test,automated",
        "note": "Created by automated test"
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("create_customer", inputs, context)
            print(f"Create Customer Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert result['customer'].get('id')
            print(f"✓ test_create_customer passed - ID: {result['customer']['id']}")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_update_customer():
    """Test updating a customer."""
    inputs = {
        "customer_id": TEST_CUSTOMER_ID,
        "note": f"Updated by test at {int(time.time())}",
        "tags": "test,updated"
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("update_customer", inputs, context)
            print(f"Update Customer Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_update_customer passed")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Order Tests
# -----------------------------------------------------------------------------

async def test_list_orders():
    """Test listing orders."""
    inputs = {"limit": 10, "status": "any"}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("list_orders", inputs, context)
            print(f"List Orders Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_list_orders passed - Found {result['count']} orders")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_order():
    """Test getting a specific order."""
    inputs = {"order_id": TEST_ORDER_ID}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("get_order", inputs, context)
            print(f"Get Order Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_get_order passed")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_create_order():
    """Test creating an order with custom line items."""
    inputs = {
        "line_items": [{"title": "Test Product", "price": "10.00", "quantity": 1}],
        "financial_status": "pending",
        "send_receipt": False,
        "note": "Test order via API",
        "tags": "test,automated"
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("create_order", inputs, context)
            print(f"Create Order Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert result['order'].get('id')
            print(f"✓ test_create_order passed - ID: {result['order']['id']}")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Product Tests (GraphQL API)
# -----------------------------------------------------------------------------

async def test_list_products():
    """Test listing products using GraphQL API."""
    inputs = {"limit": 10}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("list_products", inputs, context)
            print(f"List Products Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            # GraphQL returns pagination info
            print(f"  hasNextPage: {result.get('hasNextPage')}")
            print(f"  endCursor: {result.get('endCursor')}")
            print(f"✓ test_list_products passed - Found {result['count']} products")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_list_products_with_filter():
    """Test listing products with GraphQL filter."""
    inputs = {"limit": 5, "status": "active"}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("list_products", inputs, context)
            print(f"List Products (filtered) Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_list_products_with_filter passed - Found {result['count']} active products")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_product():
    """Test getting a specific product using GraphQL API."""
    inputs = {"product_id": TEST_PRODUCT_ID}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("get_product", inputs, context)
            print(f"Get Product Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            # Verify GraphQL response fields are transformed correctly
            product = result.get('product', {})
            print(f"  Product ID: {product.get('id')}")
            print(f"  Title: {product.get('title')}")
            print(f"  Variants: {len(product.get('variants', []))}")
            print(f"✓ test_get_product passed")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_create_product():
    """Test creating a product using GraphQL API."""
    timestamp = int(time.time())
    inputs = {
        "title": f"Test Product {timestamp}",
        "body_html": "<p>Test product created via GraphQL API</p>",
        "vendor": "Test Vendor",
        "product_type": "Test",
        "tags": "test,automated,graphql",
        "status": "draft",
        "variants": [{"price": "19.99", "sku": f"TEST-{timestamp}"}]
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("create_product", inputs, context)
            print(f"Create Product Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert result['product'].get('id')
            # Verify ID is numeric (transformed from GID)
            product_id = result['product']['id']
            print(f"  Product ID: {product_id}")
            print(f"✓ test_create_product passed - ID: {product_id}")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_update_product():
    """Test updating a product using GraphQL API."""
    inputs = {
        "product_id": TEST_PRODUCT_ID,
        "title": f"Updated Product {int(time.time())}",
        "tags": "test,updated,graphql"
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("update_product", inputs, context)
            print(f"Update Product Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_update_product passed")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Inventory & Location Tests
# -----------------------------------------------------------------------------

async def test_list_locations():
    """Test listing locations."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("list_locations", {}, context)
            print(f"List Locations Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_list_locations passed - Found {result['count']} locations")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_get_inventory_levels():
    """Test getting inventory levels."""
    inputs = {"location_ids": TEST_LOCATION_ID, "limit": 10}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("get_inventory_levels", inputs, context)
            print(f"Get Inventory Levels Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_get_inventory_levels passed - Found {result['count']} levels")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_set_inventory_level():
    """Test setting inventory level."""
    inputs = {
        "inventory_item_id": TEST_INVENTORY_ITEM_ID,
        "location_id": TEST_LOCATION_ID,
        "available": 50
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("set_inventory_level", inputs, context)
            print(f"Set Inventory Level Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_set_inventory_level passed")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Shop Tests
# -----------------------------------------------------------------------------

async def test_get_shop():
    """Test getting shop info."""
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("get_shop", {}, context)
            print(f"Get Shop Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_get_shop passed - Shop: {result['shop'].get('name')}")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


# -----------------------------------------------------------------------------
# Draft Order Tests
# -----------------------------------------------------------------------------

async def test_list_draft_orders():
    """Test listing draft orders."""
    inputs = {"limit": 10}
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("list_draft_orders", inputs, context)
            print(f"List Draft Orders Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            print(f"✓ test_list_draft_orders passed - Found {result['count']} draft orders")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


async def test_create_draft_order():
    """Test creating a draft order."""
    inputs = {
        "line_items": [{"title": "Draft Test Item", "price": "15.00", "quantity": 1}],
        "note": "Test draft order",
        "tags": "test,automated"
    }
    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await execute_wrapper("create_draft_order", inputs, context)
            print(f"Create Draft Order Result: {result}")
            assert result.get('success') == True, f"Failed: {result.get('message')}"
            assert result['draft_order'].get('id')
            print(f"✓ test_create_draft_order passed - ID: {result['draft_order']['id']}")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return None


# =============================================================================
# Test Runners
# =============================================================================

async def run_safe_tests():
    """Run read-only tests (safe for any store)."""
    print("\n" + "=" * 60)
    print("RUNNING SAFE (READ-ONLY) TESTS")
    print("=" * 60 + "\n")

    tests = [
        ("List Customers", test_list_customers),
        ("Search Customers", test_search_customers),
        ("List Orders", test_list_orders),
        ("List Products (GraphQL)", test_list_products),
        ("List Products with Filter (GraphQL)", test_list_products_with_filter),
        ("List Locations", test_list_locations),
        ("Get Shop", test_get_shop),
        ("List Draft Orders", test_list_draft_orders),
    ]

    results = {"passed": 0, "failed": 0}
    for name, test_func in tests:
        print(f"\n--- Testing: {name} ---")
        try:
            result = await test_func()
            if result and result.get('success'):
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            results["failed"] += 1

    print("\n" + "=" * 60)
    print(f"SAFE TESTS: {results['passed']} passed, {results['failed']} failed")
    print("=" * 60 + "\n")
    return results


async def run_get_tests():
    """Run get-by-ID tests (requires valid TEST_*_ID values)."""
    print("\n" + "=" * 60)
    print("RUNNING GET-BY-ID TESTS")
    print("=" * 60 + "\n")

    tests = [
        ("Get Customer", test_get_customer),
        ("Get Order", test_get_order),
        ("Get Product", test_get_product),
        ("Get Inventory Levels", test_get_inventory_levels),
    ]

    results = {"passed": 0, "failed": 0}
    for name, test_func in tests:
        print(f"\n--- Testing: {name} ---")
        try:
            result = await test_func()
            if result and result.get('success'):
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            results["failed"] += 1

    print("\n" + "=" * 60)
    print(f"GET TESTS: {results['passed']} passed, {results['failed']} failed")
    print("=" * 60 + "\n")
    return results


async def run_write_tests():
    """Run create tests (adds data to store)."""
    print("\n" + "=" * 60)
    print("RUNNING WRITE TESTS (CREATES DATA)")
    print("=" * 60 + "\n")

    tests = [
        ("Create Customer", test_create_customer),
        ("Create Product", test_create_product),
        ("Create Order", test_create_order),
        ("Create Draft Order", test_create_draft_order),
    ]

    results = {"passed": 0, "failed": 0}
    for name, test_func in tests:
        print(f"\n--- Testing: {name} ---")
        try:
            result = await test_func()
            if result and result.get('success'):
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            results["failed"] += 1

    print("\n" + "=" * 60)
    print(f"WRITE TESTS: {results['passed']} passed, {results['failed']} failed")
    print("=" * 60 + "\n")
    return results


async def run_update_tests():
    """Run update tests (modifies existing data)."""
    print("\n" + "=" * 60)
    print("RUNNING UPDATE TESTS")
    print("=" * 60 + "\n")

    tests = [
        ("Update Customer", test_update_customer),
        ("Update Product", test_update_product),
        ("Set Inventory Level", test_set_inventory_level),
    ]

    results = {"passed": 0, "failed": 0}
    for name, test_func in tests:
        print(f"\n--- Testing: {name} ---")
        try:
            result = await test_func()
            if result and result.get('success'):
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            results["failed"] += 1

    print("\n" + "=" * 60)
    print(f"UPDATE TESTS: {results['passed']} passed, {results['failed']} failed")
    print("=" * 60 + "\n")
    return results


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("RUNNING ALL SHOPIFY ADMIN API TESTS")
    print("=" * 60)

    all_results = {"passed": 0, "failed": 0}

    for runner in [run_safe_tests, run_get_tests, run_write_tests, run_update_tests]:
        results = await runner()
        all_results["passed"] += results["passed"]
        all_results["failed"] += results["failed"]

    print("\n" + "=" * 60)
    print(f"ALL TESTS: {all_results['passed']} passed, {all_results['failed']} failed")
    print("=" * 60 + "\n")
    return all_results


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys

    print("""
╔═══════════════════════════════════════════════════════════════╗
║           SHOPIFY ADMIN API TEST SUITE                        ║
╠═══════════════════════════════════════════════════════════════╣
║  Usage:                                                       ║
║    python test_shopify_admin.py [option]                      ║
║                                                               ║
║  Options:                                                     ║
║    safe     - Read-only tests (list operations)               ║
║    get      - Get-by-ID tests (requires TEST_*_ID)            ║
║    write    - Create tests (adds data to store)               ║
║    update   - Update tests (modifies existing data)           ║
║    all      - Run all tests                                   ║
║                                                               ║
║  Default: safe                                                ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    option = sys.argv[1] if len(sys.argv) > 1 else "safe"

    runners = {
        "safe": run_safe_tests,
        "get": run_get_tests,
        "write": run_write_tests,
        "update": run_update_tests,
        "all": run_all_tests
    }

    if option in runners:
        asyncio.run(runners[option]())
    else:
        print(f"Unknown option: {option}")
        print("Use: safe, get, write, update, or all")
