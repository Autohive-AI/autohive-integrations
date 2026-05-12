"""
Live integration tests for the Count integration.

Requires COUNT_ACCESS_TOKEN set in the environment.

Run read-only:
    pytest count/tests/test_count_integration.py -m "integration and not destructive" --import-mode=importlib --tb=short

Run all (including destructive):
    pytest count/tests/test_count_integration.py -m "integration" --import-mode=importlib --tb=short
"""

import time

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from count.count import count

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    access_token = env_credentials("COUNT_ACCESS_TOKEN")
    client_id = env_credentials("COUNT_CLIENT_ID")
    if not access_token:
        pytest.skip("COUNT_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params, **kwargs) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "credentials": {"access_token": access_token},
            "client_id": client_id or "",
            "client_secret": "",
        }
    )
    ctx.fetch.side_effect = real_fetch
    return ctx


# ---- Read-Only Tests ----


async def test_list_accounts(live_context):
    result = await count.execute_action("list_accounts", {}, live_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["result"] is True
    assert isinstance(result.result.data["accounts"], list)


async def test_list_customers(live_context):
    result = await count.execute_action("list_customers", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["customers"], list)


async def test_list_vendors(live_context):
    result = await count.execute_action("list_vendors", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["vendors"], list)


async def test_list_products(live_context):
    result = await count.execute_action("list_products", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["products"], list)


async def test_list_transactions(live_context):
    result = await count.execute_action("list_transactions", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["transactions"], list)


async def test_list_journal_entries(live_context):
    result = await count.execute_action("list_journal_entries", {"limit": 5}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["journal_entries"], list)


async def test_list_tags(live_context):
    result = await count.execute_action("list_tags", {}, live_context)
    assert result.type == ResultType.ACTION
    assert isinstance(result.result.data["tags"], list)


async def test_get_trial_balance(live_context):
    result = await count.execute_action("get_trial_balance", {}, live_context)
    assert result.type == ResultType.ACTION
    assert "report" in result.result.data


async def test_get_balance_sheet(live_context):
    result = await count.execute_action("get_balance_sheet", {}, live_context)
    assert result.type == ResultType.ACTION
    assert "report" in result.result.data


async def test_get_profit_and_loss(live_context):
    result = await count.execute_action("get_profit_and_loss", {}, live_context)
    assert result.type == ResultType.ACTION
    assert "report" in result.result.data


# ---- Destructive / Lifecycle Tests ----


@pytest.mark.destructive
async def test_customer_lifecycle(live_context):
    """create -> get -> find_by_email -> update -> delete customer."""
    uid = int(time.time())
    email = f"ah-test-{uid}@example.com"

    create = await count.execute_action(
        "create_customer",
        {"name": f"AH Test Customer {uid}", "email": email},
        live_context,
    )
    assert create.type == ResultType.ACTION
    assert create.result.data["result"] is True
    customer_uuid = create.result.data["customer"]["uuid"]

    get = await count.execute_action("get_customer", {"customer_uuid": customer_uuid}, live_context)
    assert get.type == ResultType.ACTION
    assert get.result.data["customer"]["uuid"] == customer_uuid

    find = await count.execute_action("find_customer_by_email", {"email": email}, live_context)
    assert find.type == ResultType.ACTION
    assert find.result.data["result"] is True

    update = await count.execute_action(
        "update_customer",
        {"customer_uuid": customer_uuid, "name": f"AH Updated {uid}"},
        live_context,
    )
    assert update.type == ResultType.ACTION
    assert update.result.data["result"] is True

    delete = await count.execute_action("delete_customer", {"customer_uuid": customer_uuid}, live_context)
    assert delete.type == ResultType.ACTION
    assert delete.result.data["deleted"] is True


@pytest.mark.destructive
async def test_vendor_lifecycle(live_context):
    """create -> update -> delete vendor."""
    uid = int(time.time())

    create = await count.execute_action(
        "create_vendor",
        {"name": f"AH Test Vendor {uid}", "email": f"vendor-{uid}@example.com"},
        live_context,
    )
    assert create.type == ResultType.ACTION
    vendor_uuid = create.result.data["vendor"]["uuid"]

    update = await count.execute_action(
        "update_vendor",
        {"vendor_uuid": vendor_uuid, "name": f"AH Updated Vendor {uid}"},
        live_context,
    )
    assert update.type == ResultType.ACTION
    assert update.result.data["result"] is True

    delete = await count.execute_action("delete_vendor", {"vendor_uuid": vendor_uuid}, live_context)
    assert delete.type == ResultType.ACTION
    assert delete.result.data["deleted"] is True


@pytest.mark.destructive
async def test_product_lifecycle(live_context):
    """create -> get -> find_by_name -> update -> delete product."""
    uid = int(time.time())
    name = f"AH Test Product {uid}"

    create = await count.execute_action(
        "create_product",
        {"name": name, "price": 99.99, "type": "service"},
        live_context,
    )
    assert create.type == ResultType.ACTION
    product_uuid = create.result.data["product"]["uuid"]

    get = await count.execute_action("get_product", {"product_uuid": product_uuid}, live_context)
    assert get.type == ResultType.ACTION
    assert get.result.data["product"]["uuid"] == product_uuid

    find = await count.execute_action("find_product_by_name", {"name": name}, live_context)
    assert find.type == ResultType.ACTION
    assert find.result.data["result"] is True

    update = await count.execute_action(
        "update_product",
        {"product_uuid": product_uuid, "price": 49.99},
        live_context,
    )
    assert update.type == ResultType.ACTION
    assert update.result.data["result"] is True

    delete = await count.execute_action("delete_product", {"product_uuid": product_uuid}, live_context)
    assert delete.type == ResultType.ACTION
    assert delete.result.data["deleted"] is True


@pytest.mark.destructive
async def test_account_lifecycle(live_context):
    """create -> update -> delete account."""
    uid = int(time.time())

    create = await count.execute_action(
        "create_account",
        {"name": f"AH Test Account {uid}", "type": "expense"},
        live_context,
    )
    assert create.type == ResultType.ACTION
    account_uuid = create.result.data["account"]["uuid"]

    update = await count.execute_action(
        "update_account",
        {"account_uuid": account_uuid, "name": f"AH Updated Account {uid}"},
        live_context,
    )
    assert update.type == ResultType.ACTION
    assert update.result.data["result"] is True

    delete = await count.execute_action("delete_account", {"account_uuid": account_uuid}, live_context)
    assert delete.type == ResultType.ACTION
    assert delete.result.data["deleted"] is True


@pytest.mark.destructive
async def test_tag_lifecycle(live_context):
    """create -> update -> delete tag."""
    uid = int(time.time())

    create = await count.execute_action("create_tag", {"name": f"AH Test Tag {uid}"}, live_context)
    assert create.type == ResultType.ACTION
    tag_uuid = create.result.data["tag"]["uuid"]

    update = await count.execute_action(
        "update_tag",
        {"tag_uuid": tag_uuid, "name": f"AH Updated Tag {uid}"},
        live_context,
    )
    assert update.type == ResultType.ACTION
    assert update.result.data["result"] is True

    delete = await count.execute_action("delete_tag", {"tag_uuid": tag_uuid}, live_context)
    assert delete.type == ResultType.ACTION
    assert delete.result.data["deleted"] is True
