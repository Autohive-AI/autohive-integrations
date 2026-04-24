"""
Integration tests for Salesforce — require real API credentials.
Run with: pytest salesforce/tests/test_salesforce.py -m integration
"""

import asyncio
import os
import sys

import pytest
from autohive_integrations_sdk import ExecutionContext, IntegrationResult

from context import salesforce  # noqa

pytestmark = pytest.mark.integration

ACCESS_TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SALESFORCE_TOKEN", "")
INSTANCE_URL = os.getenv("SALESFORCE_INSTANCE_URL", "https://login.salesforce.com")
TEST_AUTH = {"credentials": {"access_token": ACCESS_TOKEN, "instance_url": INSTANCE_URL}}

RECORD_ID = os.getenv("SALESFORCE_RECORD_ID", "")
TASK_ID = os.getenv("SALESFORCE_TASK_ID", "")
EVENT_ID = os.getenv("SALESFORCE_EVENT_ID", "")


async def test_search_records():
    inputs = {"soql": "SELECT Id, Name FROM Contact LIMIT 5"}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await salesforce.execute_action("search_records", inputs, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] search_records: {len(data.get('records', []))} record(s)")


async def test_list_tasks():
    inputs = {"limit": 5}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await salesforce.execute_action("list_tasks", inputs, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_tasks: {len(data.get('tasks', []))} task(s)")


async def test_list_events():
    inputs = {"limit": 5}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await salesforce.execute_action("list_events", inputs, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_events: {len(data.get('events', []))} event(s)")


async def test_get_record():
    if not RECORD_ID:
        print("[SKIP] get_record: set SALESFORCE_RECORD_ID to test")
        return
    inputs = {"object_type": "Contact", "record_id": RECORD_ID}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await salesforce.execute_action("get_record", inputs, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] get_record: {data.get('record', {}).get('Id')}")


async def test_get_task_summary():
    if not TASK_ID:
        print("[SKIP] get_task_summary: set SALESFORCE_TASK_ID to test")
        return
    inputs = {"task_id": TASK_ID}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await salesforce.execute_action("get_task_summary", inputs, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] get_task_summary:\n{data.get('summary')}")


async def test_get_event_summary():
    if not EVENT_ID:
        print("[SKIP] get_event_summary: set SALESFORCE_EVENT_ID to test")
        return
    inputs = {"event_id": EVENT_ID}
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await salesforce.execute_action("get_event_summary", inputs, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] get_event_summary:\n{data.get('summary')}")


if __name__ == "__main__":
    asyncio.run(test_search_records())
    asyncio.run(test_list_tasks())
    asyncio.run(test_list_events())
    asyncio.run(test_get_record())
    asyncio.run(test_get_task_summary())
    asyncio.run(test_get_event_summary())
