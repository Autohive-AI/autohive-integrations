# Testbed for WhatsApp Business API integration
import asyncio
import sys
from context import whatsapp
from autohive_integrations_sdk import ExecutionContext

# Constants for testing
AUTH = {
    "access_token": "ACCESS_TOKEN"
}

PHONE_NUMBER_ID = "PHONE_NUMBER_ID"  # Using the ID from the first test case
TEST_RECIPIENT_PHONE = "TEST_RECIPIENT_PHONE"  # Using the phone number from the first test case

async def test_send_message():
    """Test sending a simple text message."""
    inputs = {
        "to": TEST_RECIPIENT_PHONE,
        "message": "Hello from WhatsApp integration test!",
        "phone_number_id": PHONE_NUMBER_ID
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await whatsapp.execute_action("send_message", inputs, context)
            print(f"Send message result: {result}")
            data = result.result.data
            assert data["success"] or "error" in data
        except Exception as e:
            print(f"Error testing send_message: {e}")


async def test_send_template_message():
    """Test sending a template message (hello_world)."""
    inputs = {
        "to": TEST_RECIPIENT_PHONE,
        "template_name": "hello_world",
        "language_code": "en_US",
        "phone_number_id": PHONE_NUMBER_ID
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await whatsapp.execute_action("send_template_message", inputs, context)
            print(f"Send template message result: {result}")
            data = result.result.data
            assert data["success"] or "error" in data
        except Exception as e:
            print(f"Error testing send_template_message: {e}")


async def test_send_media_message():
    """Test sending a media message (image)."""
    inputs = {
        "to": TEST_RECIPIENT_PHONE,
        "media_type": "image",
        "media_url": "https://cdn.prod.website-files.com/67f5c4ac73ceeeb74774a8ee/691b8e27af0bfbc9290f345d_bee-left.webp",
        "caption": "Test image from WhatsApp integration",
        "phone_number_id": PHONE_NUMBER_ID
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await whatsapp.execute_action("send_media_message", inputs, context)
            print(f"Send media message result: {result}")
            data = result.result.data
            assert data["success"] or "error" in data
        except Exception as e:
            print(f"Error testing send_media_message: {e}")


async def test_get_phone_number_health():
    """Test retrieving phone number health status."""
    inputs = {
        "phone_number_id": PHONE_NUMBER_ID
    }

    async with ExecutionContext(auth=AUTH) as context:
        try:
            result = await whatsapp.execute_action("get_phone_number_health", inputs, context)
            print(f"Get phone number health result: {result}")
            data = result.result.data
            assert "status" in data
            assert "quality_rating" in data
            assert data["success"] or "error" in data
        except Exception as e:
            print(f"Error testing get_phone_number_health: {e}")


async def test_phone_validation():
    """Test phone number validation logic with invalid inputs."""
    print("Testing phone number validation...")
    
    # Test invalid phone numbers
    invalid_phones = ["123", "invalid", "+0123456789", "1234567890", "+"]
    
    for phone in invalid_phones:
        inputs = {"to": phone, "message": "test", "phone_number_id": PHONE_NUMBER_ID}
        async with ExecutionContext(auth=AUTH) as context:
            try:
                result = await whatsapp.execute_action("send_message", inputs, context)
                print(f"Phone {phone}: {result}")
                data = result.result.data
                assert not data["success"]
                assert "Invalid phone number format" in data["error"]
            except Exception as e:
                print(f"Error testing phone validation for {phone}: {e}")


async def test_media_url_validation():
    """Test media URL validation logic with invalid inputs."""
    print("Testing media URL validation...")
    
    # Test invalid media URLs
    invalid_urls = ["http://example.com/image.png", "ftp://example.com/image.png", "/local/path/image.png", "C:\\image.png", "example.com/image.png"]
    
    # Use a valid phone number to bypass phone validation
    valid_phone = "+1234567890"
    
    for url in invalid_urls:
        inputs = {
            "to": valid_phone,
            "media_type": "image",
            "media_url": url,
            "phone_number_id": PHONE_NUMBER_ID
        }
        async with ExecutionContext(auth=AUTH) as context:
            try:
                result = await whatsapp.execute_action("send_media_message", inputs, context)
                print(f"URL {url}: {result}")
                data = result.result.data
                assert not data["success"]
                assert "Invalid media URL" in data["error"]
            except Exception as e:
                print(f"Error testing media URL validation for {url}: {e}")


async def main():
    print("Testing WhatsApp Business Integration")
    print("====================================")

    # Map of test names to functions
    tests = {
        "test_send_message": test_send_message,
        "test_send_template_message": test_send_template_message,
        "test_send_media_message": test_send_media_message,
        "test_get_phone_number_health": test_get_phone_number_health,
        "test_phone_validation": test_phone_validation,
        "test_media_url_validation": test_media_url_validation
    }

    # Check for specific test to run from command line args
    test_to_run = sys.argv[1] if len(sys.argv) > 1 else None

    if test_to_run:
        if test_to_run in tests:
            print(f"Running single test: {test_to_run}")
            await tests[test_to_run]()
        else:
            print(f"Test '{test_to_run}' not found. Available tests:")
            for name in tests.keys():
                print(f"  - {name}")
    else:
        # Run all tests
        for name, test_func in tests.items():
            print(f"Running {name}...")
            await test_func()
            print()
            
        print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
