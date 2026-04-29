import asyncio, os, sys
from context import elevenlabs
from autohive_integrations_sdk import ExecutionContext, IntegrationResult

API_KEY = sys.argv[1] if len(sys.argv) > 1 else os.getenv("ELEVENLABS_API_KEY", "")
TEST_AUTH = {"credentials": {"api_key": API_KEY}}


async def test_get_user_subscription():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await elevenlabs.execute_action("get_user_subscription", {}, context)
        assert isinstance(result, IntegrationResult)
        assert result.result.data.get("result") is True
        print(f"[OK] get_user_subscription: {result.result.data}")


async def test_list_voices():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await elevenlabs.execute_action("list_voices", {"page_size": 5}, context)
        assert isinstance(result, IntegrationResult)
        assert result.result.data.get("result") is True
        print(f"[OK] list_voices: {result.result.data}")


async def test_list_history():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await elevenlabs.execute_action("list_history", {"page_size": 5}, context)
        assert isinstance(result, IntegrationResult)
        assert result.result.data.get("result") is True
        print(f"[OK] list_history: {result.result.data}")


async def main():
    if not API_KEY:
        print("Usage: python test_elevenlabs.py <api_key>  OR  set ELEVENLABS_API_KEY env var")
        sys.exit(1)
    await test_get_user_subscription()
    await test_list_voices()
    await test_list_history()
    print("\n[DONE] All tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
