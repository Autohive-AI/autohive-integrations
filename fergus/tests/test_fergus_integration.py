import asyncio
from pprint import pprint
from context import fergus
from autohive_integrations_sdk import ExecutionContext

AUTH = {"credentials": {"api_token": "YOUR_FERGUS_PAT"}}  # nosec B105


async def test_create_job():
    inputs = {
        "job_type": "Charge Up",
        "title": "Leaking Tap Repair – Kitchen Sink",
        "description": "Customer reports dripping tap under sink. Access via front door.",
        "customer_id": 111,  # replace with a real customer ID
        "site_id": 222,  # replace with a real site ID
        "customer_reference": "MP-WO-12345",
    }
    async with ExecutionContext(auth=AUTH) as context:
        result = await fergus.execute_action("create_job", inputs, context)
        print("\nCreate Job:")
        pprint(result)


async def test_list_jobs():
    inputs = {
        "status": "completed",
        "limit": 10,
    }
    async with ExecutionContext(auth=AUTH) as context:
        result = await fergus.execute_action("list_jobs", inputs, context)
        print("\nList Jobs (completed):")
        pprint(result)


async def test_get_job():
    inputs = {
        "job_id": 1,  # replace with a real job ID
    }
    async with ExecutionContext(auth=AUTH) as context:
        result = await fergus.execute_action("get_job", inputs, context)
        print("\nGet Job:")
        pprint(result)


async def main():
    print("Testing Fergus Integration")
    print("==========================")
    await test_create_job()
    await test_list_jobs()
    await test_get_job()


if __name__ == "__main__":
    asyncio.run(main())
