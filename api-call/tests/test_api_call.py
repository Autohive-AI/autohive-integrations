# Testbed for the API Call integration.
# The IUT (integration under test) is the api_call.py file
import asyncio
from context import api_call
from autohive_integrations_sdk import ExecutionContext

async def test_get_request():
    auth = {}

    inputs = {
        "url": "https://httpbin.org/get",
        "headers": {"Accept": "application/json"},
        "params": {"test_param": "test_value"}
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await api_call.execute_action("get_request", inputs, context)
            print(f"GET Request Result: {result}")
        except Exception as e:
            print(f"Error testing get_request: {e}")

async def test_post_request():
    auth = {}

    inputs = {
        "url": "https://httpbin.org/post",
        "headers": {"Accept": "application/json"},
        "json_body": {"key": "value", "test": True}
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await api_call.execute_action("post_request", inputs, context)
            print(f"POST Request Result: {result}")
        except Exception as e:
            print(f"Error testing post_request: {e}")


async def main():
    print("Testing API Call Integration")
    print("============================")

    await test_get_request()
    await test_post_request()

if __name__ == "__main__":
    asyncio.run(main())
