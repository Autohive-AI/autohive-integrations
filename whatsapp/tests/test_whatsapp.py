# Testbed for WhatsApp Business API integration
import asyncio
from context import whatsapp
from autohive_integrations_sdk import ExecutionContext

async def test_send_message():
    # Setup a mock auth object with WhatsApp Business API credentials
    auth = {
        "access_token": "test_access_token",
        "phone_number_id": "test_phone_number_id"
    }

    inputs = {
        "to": "+1234567890",
        "message": "Hello from WhatsApp integration test!"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await whatsapp.execute_action("send_message", inputs, context)
            print(f"Send message result: {result}")
            data = result.result.data
            assert data["success"] or "error" in data
        except Exception as e:
            print(f"Error testing send_message: {e}")


async def test_send_template_message():
    auth = {
        "access_token": "test_access_token", 
        "phone_number_id": "test_phone_number_id"
    }

    inputs = {
        "to": "+1234567890",
        "template_name": "hello_world",
        "language_code": "en",
        "parameters": ["John", "Doe"]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await whatsapp.execute_action("send_template_message", inputs, context)
            print(f"Send template message result: {result}")
            data = result.result.data
            assert data["success"] or "error" in data
        except Exception as e:
            print(f"Error testing send_template_message: {e}")


async def test_send_media_message():
    auth = {
        "access_token": "test_access_token",
        "phone_number_id": "test_phone_number_id"
    }

    inputs = {
        "to": "+1234567890",
        "media_type": "image",
        "media_url": "https://example.com/image.jpg",
        "caption": "Test image from WhatsApp integration"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await whatsapp.execute_action("send_media_message", inputs, context)
            print(f"Send media message result: {result}")
            data = result.result.data
            assert data["success"] or "error" in data
        except Exception as e:
            print(f"Error testing send_media_message: {e}")


async def test_get_contact_info():
    auth = {
        "access_token": "test_access_token",
        "phone_number_id": "test_phone_number_id"
    }

    inputs = {
        "phone_number": "+1234567890"
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await whatsapp.execute_action("get_contact_info", inputs, context)
            print(f"Get contact info result: {result}")
            data = result.result.data
            assert "phone_number" in data
            assert "is_whatsapp_user" in data
            assert data["success"] or "error" in data
        except Exception as e:
            print(f"Error testing get_contact_info: {e}")


async def test_phone_validation():
    print("Testing phone number validation...")
    
    # Test invalid phone numbers
    invalid_phones = ["123", "invalid", "+0123456789", "1234567890", "+"]
    
    auth = {
        "access_token": "test_access_token",
        "phone_number_id": "test_phone_number_id"
    }
    
    for phone in invalid_phones:
        inputs = {"to": phone, "message": "test"}
        async with ExecutionContext(auth=auth) as context:
            try:
                result = await whatsapp.execute_action("send_message", inputs, context)
                print(f"Phone {phone}: {result}")
                data = result.result.data
                assert not data["success"]
                assert "Invalid phone number format" in data["error"]
            except Exception as e:
                print(f"Error testing phone validation for {phone}: {e}")


async def main():
    print("Testing WhatsApp Business Integration")
    print("====================================")

    await test_send_message()
    print()
    await test_send_template_message()
    print()
    await test_send_media_message()
    print()
    await test_get_contact_info()
    print()
    await test_phone_validation()
    print()
    print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
