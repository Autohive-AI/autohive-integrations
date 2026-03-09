import asyncio
from context import demo_integration
from autohive_integrations_sdk import ExecutionContext


async def test_get_data():
    """Test get_data action."""
    auth = {"credentials": {"api_key": "test_key"}}

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await demo_integration.execute_action("get_data", {"limit": 5}, context)

            data = result.data
            assert "result" in data
            print(f"Result: {data}")
        except Exception as e:
            print(f"Error: {e}")


async def run_all_tests():
    """Run all tests."""
    tests = [
        ("test_get_data", test_get_data),
    ]

    for name, test_func in tests:
        print(f"\nRunning {name}...")
        await test_func()

    print("\nAll tests completed!")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
