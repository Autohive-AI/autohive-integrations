import asyncio
from context import viator
from autohive_integrations_sdk import ExecutionContext

# Test configuration
# Replace these with your actual test credentials
TEST_CONFIG = {
    "api_key": "YOUR_VIATOR_API_KEY_HERE",  # Replace with your Viator Partner API key
    "destination_id": 684,  # New York City
    "product_code": "5010SYDNEY",  # Example product code
    "currency": "USD"
}

# Authentication configuration for tests
def get_auth():
    """Get authentication configuration"""
    return {
        "api_key": TEST_CONFIG["api_key"]
    }


async def test_get_destinations():
    """Test getting list of destinations"""
    print("\n=== Testing Get Destinations ===")

    auth = get_auth()
    inputs = {}

    async with ExecutionContext(auth=auth) as context:
        result = await viator.execute_action("get_destinations", inputs, context)
        print(f"Found {len(result.get('destinations', []))} destinations")
        if result.get('destinations'):
            print(f"First destination: {result['destinations'][0]}")
        return result


async def test_search_products():
    """Test searching for products"""
    print("\n=== Testing Search Products ===")

    auth = get_auth()
    inputs = {
        "destination_id": TEST_CONFIG["destination_id"],
        "currency": TEST_CONFIG["currency"],
        "page": 1,
        "page_size": 5
    }

    async with ExecutionContext(auth=auth) as context:
        result = await viator.execute_action("search_products", inputs, context)
        print(f"Found {result.get('total_count', 0)} total products")
        print(f"Returned {len(result.get('products', []))} products on page {result.get('page', 1)}")
        if result.get('products'):
            product = result['products'][0]
            print(f"First product: {product.get('title')}")
            print(f"Price: {product.get('price', {}).get('amount')} {product.get('price', {}).get('currency')}")
        return result


async def test_get_product_details():
    """Test getting product details"""
    print("\n=== Testing Get Product Details ===")

    auth = get_auth()
    inputs = {
        "product_code": TEST_CONFIG["product_code"],
        "currency": TEST_CONFIG["currency"]
    }

    async with ExecutionContext(auth=auth) as context:
        result = await viator.execute_action("get_product_details", inputs, context)
        print(f"Product: {result.get('title')}")
        print(f"Description: {result.get('description', '')[:100]}...")
        print(f"Duration: {result.get('duration')}")
        print(f"Rating: {result.get('rating')} ({result.get('reviews_count')} reviews)")
        return result


async def test_check_availability():
    """Test checking product availability"""
    print("\n=== Testing Check Availability ===")

    auth = get_auth()
    inputs = {
        "product_code": TEST_CONFIG["product_code"],
        "travel_date": "2025-12-01",  # Update with a future date
        "currency": TEST_CONFIG["currency"],
        "adult_count": 2,
        "child_count": 1
    }

    async with ExecutionContext(auth=auth) as context:
        result = await viator.execute_action("check_availability", inputs, context)
        print(f"Available: {result.get('available')}")
        if result.get('product_options'):
            print(f"Found {len(result['product_options'])} product options")
            option = result['product_options'][0]
            print(f"First option: {option.get('title')}")
            print(f"Price: {option.get('price', {}).get('amount')} {option.get('price', {}).get('currency')}")
        return result


async def test_calculate_price():
    """Test calculating booking price"""
    print("\n=== Testing Calculate Price ===")

    # Note: You'll need to get a valid product_option_code from check_availability first
    auth = get_auth()
    inputs = {
        "product_code": TEST_CONFIG["product_code"],
        "product_option_code": "OPTION_CODE_HERE",  # Replace with actual option code
        "travel_date": "2025-12-01",
        "currency": TEST_CONFIG["currency"],
        "adult_count": 2,
        "child_count": 1,
        "infant_count": 0
    }

    async with ExecutionContext(auth=auth) as context:
        result = await viator.execute_action("calculate_price", inputs, context)
        print(f"Subtotal: {result.get('subtotal')} {result.get('currency')}")
        print(f"Total: {result.get('total')} {result.get('currency')}")
        breakdown = result.get('breakdown', {})
        print(f"Breakdown - Adult: {breakdown.get('adult_price')}, Child: {breakdown.get('child_price')}, Infant: {breakdown.get('infant_price')}")
        return result


async def test_get_product_reviews():
    """Test getting product reviews"""
    print("\n=== Testing Get Product Reviews ===")

    auth = get_auth()
    inputs = {
        "product_code": TEST_CONFIG["product_code"],
        "page": 1,
        "page_size": 5
    }

    async with ExecutionContext(auth=auth) as context:
        result = await viator.execute_action("get_product_reviews", inputs, context)
        print(f"Average rating: {result.get('average_rating')}")
        print(f"Total reviews: {result.get('total_reviews')}")
        print(f"Returned {len(result.get('reviews', []))} reviews")
        if result.get('reviews'):
            review = result['reviews'][0]
            print(f"First review: {review.get('title')}")
            print(f"Rating: {review.get('rating')}")
        return result


async def test_create_booking():
    """Test creating a booking (commented out by default for safety)"""
    print("\n=== Testing Create Booking ===")
    print("SKIPPED - Uncomment to test actual booking creation")
    return None

    # Uncomment below to test actual booking creation
    # WARNING: This will create a real booking and may incur charges
    """
    auth = get_auth()
    inputs = {
        "product_code": TEST_CONFIG["product_code"],
        "product_option_code": "OPTION_CODE_HERE",
        "travel_date": "2025-12-01",
        "currency": TEST_CONFIG["currency"],
        "traveler_details": [
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "+1234567890",
                "age_band": "ADULT"
            }
        ],
        "booker_details": {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "+1234567890"
        }
    }

    async with ExecutionContext(auth=auth) as context:
        result = await viator.execute_action("create_booking", inputs, context)
        print(f"Booking reference: {result.get('booking_reference')}")
        print(f"Status: {result.get('booking_status')}")
        print(f"Total price: {result.get('total_price')} {result.get('currency')}")
        print(f"Voucher URL: {result.get('voucher_url')}")
        return result
    """


async def test_get_booking():
    """Test getting booking details"""
    print("\n=== Testing Get Booking ===")
    print("SKIPPED - Requires a valid booking reference")
    return None

    # Uncomment below with a valid booking reference
    """
    auth = get_auth()
    inputs = {
        "booking_reference": "BR-123456789"  # Replace with actual booking reference
    }

    async with ExecutionContext(auth=auth) as context:
        result = await viator.execute_action("get_booking", inputs, context)
        print(f"Booking reference: {result.get('booking_reference')}")
        print(f"Status: {result.get('booking_status')}")
        print(f"Product: {result.get('product_title')}")
        print(f"Travel date: {result.get('travel_date')}")
        return result
    """


async def test_cancel_booking():
    """Test cancelling a booking"""
    print("\n=== Testing Cancel Booking ===")
    print("SKIPPED - Requires a valid booking reference")
    return None

    # Uncomment below with a valid booking reference
    """
    auth = get_auth()
    inputs = {
        "booking_reference": "BR-123456789",  # Replace with actual booking reference
        "cancellation_reason_code": "Customer Request"
    }

    async with ExecutionContext(auth=auth) as context:
        result = await viator.execute_action("cancel_booking", inputs, context)
        print(f"Booking reference: {result.get('booking_reference')}")
        print(f"Cancellation status: {result.get('cancellation_status')}")
        print(f"Refund amount: {result.get('refund_amount')} {result.get('currency')}")
        print(f"Cancellation fee: {result.get('cancellation_fee')}")
        return result
    """


async def test_workflow():
    """Test a complete workflow: search -> details -> availability -> reviews"""
    print("\n=== Testing Complete Workflow ===")

    # 1. Get destinations
    destinations = await test_get_destinations()

    # 2. Search for products
    products = await test_search_products()

    # 3. Get details for first product (if available)
    if products and products.get('products'):
        product_code = products['products'][0].get('product_code')
        if product_code:
            TEST_CONFIG["product_code"] = product_code
            await test_get_product_details()

            # 4. Check availability
            await test_check_availability()

            # 5. Get reviews
            await test_get_product_reviews()

    print("\n=== Workflow Complete ===")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Viator Integration Tests")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Destination ID: {TEST_CONFIG['destination_id']}")
    print(f"  Product Code: {TEST_CONFIG['product_code']}")
    print(f"  Currency: {TEST_CONFIG['currency']}")
    print("\nNote: Update TEST_CONFIG with your API key and test data")
    print("=" * 60)

    try:
        # Run individual tests
        await test_get_destinations()
        await test_search_products()
        await test_get_product_details()
        await test_check_availability()
        await test_get_product_reviews()

        # Booking tests (commented out by default)
        await test_create_booking()
        await test_get_booking()
        await test_cancel_booking()

        # Run workflow test
        # await test_workflow()

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n!!! Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
