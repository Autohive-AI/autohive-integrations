"""
Test suite for Stripe integration.

These tests require a valid Stripe API key to run.
Set your test key before running: export STRIPE_TEST_API_KEY=sk_test_xxx

Usage:
    cd stripe/tests
    python test_stripe.py sk_test_xxx           # Full test suite
    python test_stripe.py sk_test_xxx --quick   # Read-only tests
"""

import asyncio
import os
import sys

from context import stripe_integration
from autohive_integrations_sdk import ExecutionContext


# Test API key - from environment or will be set via argparse
API_KEY = os.environ.get("STRIPE_TEST_API_KEY", "sk_test_your_key_here")


async def test_list_customers():
    """Test listing customers."""
    print("\n=== Test: List Customers ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "list_customers",
                {"limit": 5},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            print(f"Customers found: {len(data.get('customers', []))}")
            print(f"Has more: {data.get('has_more')}")

            if data.get('customers'):
                customer = data['customers'][0]
                print(f"First customer ID: {customer.get('id')}")
                print(f"First customer email: {customer.get('email')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_create_customer():
    """Test creating a customer."""
    print("\n=== Test: Create Customer ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "create_customer",
                {
                    "email": "test@example.com",
                    "name": "Test Customer",
                    "description": "Created by integration test",
                    "metadata": {"test": "true"}
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            customer = data.get('customer', {})
            print(f"Customer ID: {customer.get('id')}")
            print(f"Customer email: {customer.get('email')}")

            return customer.get('id')
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_customer(customer_id: str):
    """Test getting a specific customer."""
    print("\n=== Test: Get Customer ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "get_customer",
                {"customer_id": customer_id},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            customer = data.get('customer', {})
            print(f"Customer ID: {customer.get('id')}")
            print(f"Customer name: {customer.get('name')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_update_customer(customer_id: str):
    """Test updating a customer."""
    print("\n=== Test: Update Customer ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "update_customer",
                {
                    "customer_id": customer_id,
                    "name": "Updated Test Customer",
                    "description": "Updated by integration test"
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            customer = data.get('customer', {})
            print(f"Updated name: {customer.get('name')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_create_invoice(customer_id: str):
    """Test creating a draft invoice."""
    print("\n=== Test: Create Invoice ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "create_invoice",
                {
                    "customer": customer_id,
                    "currency": "nzd",
                    "description": "Test Invoice - RUC Purchase",
                    "auto_advance": False,
                    "collection_method": "send_invoice",
                    "days_until_due": 30
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            invoice = data.get('invoice', {})
            print(f"Invoice ID: {invoice.get('id')}")
            print(f"Invoice status: {invoice.get('status')}")

            return invoice.get('id')
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_create_invoice_item(customer_id: str, invoice_id: str):
    """Test creating an invoice item."""
    print("\n=== Test: Create Invoice Item ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "create_invoice_item",
                {
                    "customer": customer_id,
                    "invoice": invoice_id,
                    "unit_amount": 6609,  # $66.09 in cents
                    "currency": "nzd",
                    "quantity": 5,
                    "description": "RUC - 5 units (5,000km)"
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            item = data.get('invoice_item', {})
            print(f"Invoice Item ID: {item.get('id')}")
            print(f"Amount: {item.get('amount')}")

            return item.get('id')
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_list_invoices():
    """Test listing invoices."""
    print("\n=== Test: List Invoices ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "list_invoices",
                {"limit": 5, "status": "draft"},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            print(f"Invoices found: {len(data.get('invoices', []))}")
        except Exception as e:
            print(f"Error: {e}")


async def test_get_invoice(invoice_id: str):
    """Test getting a specific invoice."""
    print("\n=== Test: Get Invoice ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "get_invoice",
                {"invoice_id": invoice_id},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            invoice = data.get('invoice', {})
            print(f"Invoice ID: {invoice.get('id')}")
            print(f"Invoice total: {invoice.get('total')}")
            print(f"Invoice status: {invoice.get('status')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_update_invoice(invoice_id: str):
    """Test updating an invoice."""
    print("\n=== Test: Update Invoice ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "update_invoice",
                {
                    "invoice_id": invoice_id,
                    "description": "Updated: RUC Purchase - GTR680 (Test Vehicle)\n5 units (5,000km)"
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            invoice = data.get('invoice', {})
            print(f"Updated description: {invoice.get('description')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_delete_invoice(invoice_id: str):
    """Test deleting a draft invoice."""
    print("\n=== Test: Delete Invoice ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "delete_invoice",
                {"invoice_id": invoice_id},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            print(f"Deleted: {data.get('deleted')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_delete_customer(customer_id: str):
    """Test deleting a customer."""
    print("\n=== Test: Delete Customer ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "delete_customer",
                {"customer_id": customer_id},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            print(f"Deleted: {data.get('deleted')}")
        except Exception as e:
            print(f"Error: {e}")


# ---- Product Tests ----

async def test_list_products():
    """Test listing products."""
    print("\n=== Test: List Products ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "list_products",
                {"limit": 5, "active": True},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            print(f"Products found: {len(data.get('products', []))}")
            print(f"Has more: {data.get('has_more')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_create_product():
    """Test creating a product."""
    print("\n=== Test: Create Product ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "create_product",
                {
                    "name": "Test Product",
                    "description": "Created by integration test",
                    "active": True,
                    "metadata": {"test": "true"}
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            product = data.get('product', {})
            print(f"Product ID: {product.get('id')}")
            print(f"Product name: {product.get('name')}")

            return product.get('id')
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_product(product_id: str):
    """Test getting a specific product."""
    print("\n=== Test: Get Product ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "get_product",
                {"product_id": product_id},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            product = data.get('product', {})
            print(f"Product ID: {product.get('id')}")
            print(f"Product name: {product.get('name')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_update_product(product_id: str):
    """Test updating a product."""
    print("\n=== Test: Update Product ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "update_product",
                {
                    "product_id": product_id,
                    "name": "Updated Test Product",
                    "description": "Updated by integration test"
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            product = data.get('product', {})
            print(f"Updated name: {product.get('name')}")
        except Exception as e:
            print(f"Error: {e}")


# ---- Price Tests ----

async def test_list_prices():
    """Test listing prices."""
    print("\n=== Test: List Prices ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "list_prices",
                {"limit": 5, "active": True},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            print(f"Prices found: {len(data.get('prices', []))}")
            print(f"Has more: {data.get('has_more')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_create_price(product_id: str):
    """Test creating a price for a product."""
    print("\n=== Test: Create Price ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "create_price",
                {
                    "product": product_id,
                    "currency": "usd",
                    "unit_amount": 1999,  # $19.99
                    "recurring": {
                        "interval": "month",
                        "interval_count": 1
                    }
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            price = data.get('price', {})
            print(f"Price ID: {price.get('id')}")
            print(f"Unit amount: {price.get('unit_amount')}")

            return price.get('id')
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_price(price_id: str):
    """Test getting a specific price."""
    print("\n=== Test: Get Price ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "get_price",
                {"price_id": price_id},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            price = data.get('price', {})
            print(f"Price ID: {price.get('id')}")
            print(f"Unit amount: {price.get('unit_amount')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_update_price(price_id: str):
    """Test updating a price."""
    print("\n=== Test: Update Price ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "update_price",
                {
                    "price_id": price_id,
                    "active": True,
                    "metadata": {"updated": "true"}
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            price = data.get('price', {})
            print(f"Price active: {price.get('active')}")
        except Exception as e:
            print(f"Error: {e}")


# ---- Subscription Tests ----

async def test_list_subscriptions():
    """Test listing subscriptions."""
    print("\n=== Test: List Subscriptions ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "list_subscriptions",
                {"limit": 5},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            print(f"Subscriptions found: {len(data.get('subscriptions', []))}")
            print(f"Has more: {data.get('has_more')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_create_subscription(customer_id: str, price_id: str):
    """Test creating a subscription."""
    print("\n=== Test: Create Subscription ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "create_subscription",
                {
                    "customer": customer_id,
                    "items": [{"price": price_id}],
                    "payment_behavior": "default_incomplete",
                    "metadata": {"test": "true"}
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            subscription = data.get('subscription', {})
            print(f"Subscription ID: {subscription.get('id')}")
            print(f"Subscription status: {subscription.get('status')}")

            return subscription.get('id')
        except Exception as e:
            print(f"Error: {e}")
            return None


async def test_get_subscription(subscription_id: str):
    """Test getting a specific subscription."""
    print("\n=== Test: Get Subscription ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "get_subscription",
                {"subscription_id": subscription_id},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            subscription = data.get('subscription', {})
            print(f"Subscription ID: {subscription.get('id')}")
            print(f"Subscription status: {subscription.get('status')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_update_subscription(subscription_id: str):
    """Test updating a subscription."""
    print("\n=== Test: Update Subscription ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "update_subscription",
                {
                    "subscription_id": subscription_id,
                    "metadata": {"updated": "true"}
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            subscription = data.get('subscription', {})
            print(f"Subscription ID: {subscription.get('id')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_cancel_subscription(subscription_id: str):
    """Test canceling a subscription."""
    print("\n=== Test: Cancel Subscription ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "cancel_subscription",
                {
                    "subscription_id": subscription_id,
                    "invoice_now": False,
                    "prorate": False
                },
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            subscription = data.get('subscription', {})
            print(f"Subscription status: {subscription.get('status')}")
        except Exception as e:
            print(f"Error: {e}")


# ---- Payment Method Tests ----

async def test_list_payment_methods(customer_id: str):
    """Test listing payment methods for a customer."""
    print("\n=== Test: List Payment Methods ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "list_payment_methods",
                {"customer": customer_id, "type": "card", "limit": 5},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            print(f"Payment methods found: {len(data.get('payment_methods', []))}")
            print(f"Has more: {data.get('has_more')}")
        except Exception as e:
            print(f"Error: {e}")


async def test_get_payment_method(payment_method_id: str):
    """Test getting a specific payment method."""
    print("\n=== Test: Get Payment Method ===")
    auth = {"credentials": {"api_key": API_KEY}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await stripe_integration.execute_action(
                "get_payment_method",
                {"payment_method_id": payment_method_id},
                context
            )

            data = result.result.data
            print(f"Result: {data.get('result')}")
            pm = data.get('payment_method', {})
            print(f"Payment Method ID: {pm.get('id')}")
            print(f"Type: {pm.get('type')}")
        except Exception as e:
            print(f"Error: {e}")


async def run_all_tests():
    """Run all tests in sequence."""
    print("=" * 60)
    print("STRIPE INTEGRATION TEST SUITE")
    print("=" * 60)

    if API_KEY == "sk_test_your_key_here":
        print("\nWARNING: Using placeholder API key. Tests will fail.")
        print("Set STRIPE_TEST_API_KEY environment variable with your test key.")
        print("=" * 60)

    # Test customer CRUD
    print("\n" + "-" * 40)
    print("CUSTOMER TESTS")
    print("-" * 40)
    await test_list_customers()

    customer_id = await test_create_customer()
    if customer_id:
        await test_get_customer(customer_id)
        await test_update_customer(customer_id)

        # Test invoice CRUD
        print("\n" + "-" * 40)
        print("INVOICE TESTS")
        print("-" * 40)
        invoice_id = await test_create_invoice(customer_id)
        if invoice_id:
            await test_create_invoice_item(customer_id, invoice_id)
            await test_get_invoice(invoice_id)
            await test_update_invoice(invoice_id)
            await test_list_invoices()

            # Clean up - delete invoice
            await test_delete_invoice(invoice_id)

        # Test product CRUD
        print("\n" + "-" * 40)
        print("PRODUCT TESTS")
        print("-" * 40)
        await test_list_products()
        product_id = await test_create_product()
        if product_id:
            await test_get_product(product_id)
            await test_update_product(product_id)

            # Test price CRUD (requires product)
            print("\n" + "-" * 40)
            print("PRICE TESTS")
            print("-" * 40)
            await test_list_prices()
            price_id = await test_create_price(product_id)
            if price_id:
                await test_get_price(price_id)
                await test_update_price(price_id)

                # Test subscription CRUD (requires customer and price)
                print("\n" + "-" * 40)
                print("SUBSCRIPTION TESTS")
                print("-" * 40)
                await test_list_subscriptions()
                subscription_id = await test_create_subscription(customer_id, price_id)
                if subscription_id:
                    await test_get_subscription(subscription_id)
                    await test_update_subscription(subscription_id)
                    # Clean up - cancel subscription
                    await test_cancel_subscription(subscription_id)

        # Test payment method operations
        print("\n" + "-" * 40)
        print("PAYMENT METHOD TESTS")
        print("-" * 40)
        await test_list_payment_methods(customer_id)

        # Clean up - delete customer
        print("\n" + "-" * 40)
        print("CLEANUP")
        print("-" * 40)
        await test_delete_customer(customer_id)

    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)


async def run_quick_tests():
    """Run quick read-only tests (no create/update/delete)."""
    print("=" * 60)
    print("STRIPE INTEGRATION QUICK TEST (READ-ONLY)")
    print("=" * 60)

    if API_KEY == "sk_test_your_key_here":
        print("\nWARNING: Using placeholder API key. Tests will fail.")
        print("Set STRIPE_TEST_API_KEY environment variable with your test key.")
        print("=" * 60)

    await test_list_customers()
    await test_list_invoices()
    await test_list_products()
    await test_list_prices()
    await test_list_subscriptions()

    print("\n" + "=" * 60)
    print("QUICK TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stripe Integration Tests")
    parser.add_argument("api_key", nargs="?", help="Stripe test API key")
    parser.add_argument("--quick", action="store_true", help="Run quick read-only tests")
    args = parser.parse_args()

    if args.api_key:
        API_KEY = args.api_key

    if args.quick:
        asyncio.run(run_quick_tests())
    else:
        asyncio.run(run_all_tests())
