import asyncio
from pprint import pprint
from context import toggl_app
from autohive_integrations_sdk import ExecutionContext


async def test_create_time_entry():
    # Replace with a real token and workspace to run end-to-end
    auth = {"api_token": "YOUR_TOGGL_API_TOKEN"}  # nosec B105

    inputs = {
        "workspace_id": 1234567,  # replace with your workspace ID
        "start": "2025-08-14T10:00:00Z",
        "stop": "2025-08-14T11:00:00Z",
        "description": "Integration test entry",
        # "project_id": 7654321,
        # "billable": True,
        # "tags": ["autohive", "test"]
    }

    async with ExecutionContext(auth=auth) as context:
        try:
            result = await toggl_app.execute_action("create_time_entry", inputs, context)
            print("\nToggl Create Time Entry Results:")
            print("================================")
            pprint(result)
        except Exception as e:
            print(f"Error testing Toggl create_time_entry: {str(e)}")
            import traceback

            traceback.print_exc()


async def main():
    print("Testing Toggl Integration")
    print("=========================")
    await test_create_time_entry()


if __name__ == "__main__":
    asyncio.run(main())
