import asyncio, os
from context import box  # noqa
from autohive_integrations_sdk import ExecutionContext, IntegrationResult

AUTH = {"credentials": {"access_token": os.getenv("BOX_TOKEN", "")}}

async def test_list_shared_folders():
    async with ExecutionContext(auth=AUTH) as context:
        result = await box.execute_action("list_shared_folders", {}, context)
        assert isinstance(result, IntegrationResult)
        print(f"[OK] list_shared_folders: {result.result.data}")

if __name__ == "__main__":
    asyncio.run(test_list_shared_folders())
