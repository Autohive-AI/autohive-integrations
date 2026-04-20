import asyncio
import os
import sys

from context import workflowmax
from autohive_integrations_sdk import ExecutionContext, IntegrationResult

ACCESS_TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.getenv("WORKFLOWMAX_TOKEN", "")

TEST_AUTH = {
    "auth_type": "PlatformOauth2",
    "credentials": {"access_token": ACCESS_TOKEN},
}

TEST_CLIENT_UUID = os.getenv("WORKFLOWMAX_CLIENT_UUID", "")
TEST_JOB_UUID = os.getenv("WORKFLOWMAX_JOB_UUID", "")
TEST_STAFF_UUID = os.getenv("WORKFLOWMAX_STAFF_UUID", "")
TEST_TASK_UUID = os.getenv("WORKFLOWMAX_TASK_UUID", "")
TEST_INVOICE_UUID = os.getenv("WORKFLOWMAX_INVOICE_UUID", "")
TEST_SUPPLIER_UUID = os.getenv("WORKFLOWMAX_SUPPLIER_UUID", "")


async def test_list_clients():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action("list_clients", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_clients: {len(data.get('clients', []))} clients")


async def test_get_client():
    if not TEST_CLIENT_UUID:
        print("[SKIP] get_client: set WORKFLOWMAX_CLIENT_UUID")
        return
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action(
            "get_client", {"uuid": TEST_CLIENT_UUID}, context
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] get_client: {data.get('client', {}).get('name', '')}")


async def test_create_client():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        inputs = {"name": "Test Client (Autohive)", "email": "test@example.com"}
        result = await workflowmax.execute_action("create_client", inputs, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] create_client: {data.get('client', {})}")


async def test_list_client_contacts():
    if not TEST_CLIENT_UUID:
        print("[SKIP] list_client_contacts: set WORKFLOWMAX_CLIENT_UUID")
        return
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action(
            "list_client_contacts", {"client_uuid": TEST_CLIENT_UUID}, context
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_client_contacts: {len(data.get('contacts', []))} contacts")


async def test_list_jobs():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action("list_jobs", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_jobs: {len(data.get('jobs', []))} jobs")


async def test_get_job():
    if not TEST_JOB_UUID:
        print("[SKIP] get_job: set WORKFLOWMAX_JOB_UUID")
        return
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action(
            "get_job", {"identifier": TEST_JOB_UUID}, context
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] get_job: {data.get('job', {}).get('name', '')}")


async def test_list_timesheets():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action("list_timesheets", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_timesheets: {len(data.get('timesheets', []))} entries")


async def test_list_invoices():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action("list_invoices", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_invoices: {len(data.get('invoices', []))} invoices")


async def test_get_invoice():
    if not TEST_INVOICE_UUID:
        print("[SKIP] get_invoice: set WORKFLOWMAX_INVOICE_UUID")
        return
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action(
            "get_invoice", {"uuid": TEST_INVOICE_UUID}, context
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] get_invoice: {data.get('invoice', {})}")


async def test_list_quotes():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action("list_quotes", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_quotes: {len(data.get('quotes', []))} quotes")


async def test_list_tasks():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action("list_tasks", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_tasks: {len(data.get('tasks', []))} tasks")


async def test_list_staff():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action("list_staff", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_staff: {len(data.get('staff', []))} staff members")


async def test_get_staff():
    if not TEST_STAFF_UUID:
        print("[SKIP] get_staff: set WORKFLOWMAX_STAFF_UUID")
        return
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action(
            "get_staff", {"uuid": TEST_STAFF_UUID}, context
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] get_staff: {data.get('staff_member', {})}")


async def test_list_leads():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action("list_leads", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_leads: {len(data.get('leads', []))} leads")


async def test_list_costs():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action("list_costs", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(f"[OK] list_costs: {len(data.get('costs', []))} costs")


async def test_list_purchase_orders():
    async with ExecutionContext(auth=TEST_AUTH) as context:
        result = await workflowmax.execute_action("list_purchase_orders", {}, context)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is True
        print(
            f"[OK] list_purchase_orders: {len(data.get('purchase_orders', []))} purchase orders"
        )


if __name__ == "__main__":
    asyncio.run(test_list_clients())
    asyncio.run(test_get_client())
    asyncio.run(test_create_client())
    asyncio.run(test_list_client_contacts())
    asyncio.run(test_list_jobs())
    asyncio.run(test_get_job())
    asyncio.run(test_list_timesheets())
    asyncio.run(test_list_invoices())
    asyncio.run(test_get_invoice())
    asyncio.run(test_list_quotes())
    asyncio.run(test_list_tasks())
    asyncio.run(test_list_staff())
    asyncio.run(test_get_staff())
    asyncio.run(test_list_leads())
    asyncio.run(test_list_costs())
    asyncio.run(test_list_purchase_orders())
