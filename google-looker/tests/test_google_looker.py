import asyncio
import os
import sys

from context import google_looker  # noqa
from autohive_integrations_sdk import ExecutionContext, IntegrationResult

AUTH = {"credentials": {"client_id": os.getenv("LOOKER_CLIENT_ID", ""), "client_secret": os.getenv("LOOKER_CLIENT_SECRET", ""), "base_url": os.getenv("LOOKER_BASE_URL", "")}}


async def test_list_dashboards():
    async with ExecutionContext(auth=AUTH) as context:
        result = await google_looker.execute_action("list_dashboards", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        print(f"[OK] list_dashboards: {data}")


if __name__ == "__main__":
    asyncio.run(test_list_dashboards())
