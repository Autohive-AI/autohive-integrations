"""
End-to-end integration tests for the Supabase integration.

Requires credentials set in environment variables or a .env file at the repo root:
    SUPABASE_URL             — your project URL (e.g. https://xxxx.supabase.co)
    SUPABASE_SERVICE_ROLE_KEY — service_role key from Project Settings > API

Optional:
    SUPABASE_TEST_TABLE           — table name for DB action tests (select/insert/update/delete)
    SUPABASE_TEST_FUNCTION        — RPC function name for call_function test
    SUPABASE_TEST_DELETE_USER_ID  — user UUID to target for delete_user (destructive)

Run with:
    pytest supabase/tests/test_supabase_integration.py -m integration
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType
from supabase import supabase  # noqa: E402

pytestmark = pytest.mark.integration

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_TEST_TABLE = os.getenv("SUPABASE_TEST_TABLE", "")

skip_if_no_creds = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY,
    reason="SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required",
)
skip_if_no_table = pytest.mark.skipif(
    not SUPABASE_TEST_TABLE,
    reason="SUPABASE_TEST_TABLE required for database action tests",
)

# Shared bucket name for all storage tests in this run
TEST_BUCKET = f"integration-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def live_context(make_context):
    service_role_key = SUPABASE_SERVICE_ROLE_KEY

    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, body=None, **kwargs):
        merged = dict(headers or {})
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                data=body,
                headers=merged,
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()

                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, str(data), data)
                if resp.status < 200 or resp.status >= 300:
                    raise HTTPError(resp.status, str(data), data)

                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={"host": SUPABASE_URL, "service_role_secret": service_role_key})
    ctx.fetch.side_effect = real_fetch
    return ctx


# ---- Database Actions ----


@skip_if_no_creds
@skip_if_no_table
@pytest.mark.asyncio
async def test_01_insert_records(live_context):
    records = [
        {"id": str(uuid.uuid4()), "name": "integration-test-a"},
        {"id": str(uuid.uuid4()), "name": "integration-test-b"},
    ]
    result = await supabase.execute_action(
        "insert_records",
        {"table": SUPABASE_TEST_TABLE, "records": records},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data["count"] >= 1


@skip_if_no_creds
@skip_if_no_table
@pytest.mark.asyncio
async def test_02_select_records(live_context):
    result = await supabase.execute_action(
        "select_records",
        {"table": SUPABASE_TEST_TABLE, "limit": 10},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert isinstance(result.result.data["records"], list)


@skip_if_no_creds
@skip_if_no_table
@pytest.mark.asyncio
async def test_03_update_records(live_context):
    unique_name = f"update-{uuid.uuid4().hex[:6]}"
    record_id = str(uuid.uuid4())
    await supabase.execute_action(
        "insert_records",
        {"table": SUPABASE_TEST_TABLE, "records": [{"id": record_id, "name": unique_name}]},
        live_context,
    )
    result = await supabase.execute_action(
        "update_records",
        {
            "table": SUPABASE_TEST_TABLE,
            "data": {"name": "updated-name"},
            "filters": {"id": f"eq.{record_id}"},
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message


@skip_if_no_creds
@skip_if_no_table
@pytest.mark.asyncio
async def test_04_delete_records(live_context):
    unique_name = f"delete-{uuid.uuid4().hex[:6]}"
    record_id = str(uuid.uuid4())
    await supabase.execute_action(
        "insert_records",
        {"table": SUPABASE_TEST_TABLE, "records": [{"id": record_id, "name": unique_name}]},
        live_context,
    )
    result = await supabase.execute_action(
        "delete_records",
        {
            "table": SUPABASE_TEST_TABLE,
            "filters": {"id": f"eq.{record_id}"},
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message


@skip_if_no_creds
@pytest.mark.asyncio
async def test_05_call_function(live_context):
    func = os.getenv("SUPABASE_TEST_FUNCTION", "")
    if not func:
        pytest.skip("SUPABASE_TEST_FUNCTION not set")
    result = await supabase.execute_action(
        "call_function",
        {"function_name": func},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message


# ---- Storage Actions (ordered: create → get → list → public_url → delete_files → delete_bucket) ----


@skip_if_no_creds
@pytest.mark.asyncio
async def test_06_create_bucket(live_context):
    result = await supabase.execute_action(
        "create_bucket",
        {"name": TEST_BUCKET, "public": True},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message


@skip_if_no_creds
@pytest.mark.asyncio
async def test_07_list_buckets(live_context):
    result = await supabase.execute_action("list_buckets", {}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    buckets = result.result.data["buckets"]
    assert isinstance(buckets, list)
    assert any(b.get("id") == TEST_BUCKET or b.get("name") == TEST_BUCKET for b in buckets)


@skip_if_no_creds
@pytest.mark.asyncio
async def test_08_get_bucket(live_context):
    result = await supabase.execute_action("get_bucket", {"bucket_id": TEST_BUCKET}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data["bucket"] is not None


@skip_if_no_creds
@pytest.mark.asyncio
async def test_09_list_files(live_context):
    result = await supabase.execute_action("list_files", {"bucket_id": TEST_BUCKET}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert isinstance(result.result.data["files"], list)


@skip_if_no_creds
@pytest.mark.asyncio
async def test_10_get_public_url(live_context):
    result = await supabase.execute_action(
        "get_public_url",
        {"bucket_id": TEST_BUCKET, "path": "test/file.txt"},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert TEST_BUCKET in result.result.data["public_url"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_11_delete_files(live_context):
    # Deleting nonexistent file — Supabase returns empty list or benign response
    result = await supabase.execute_action(
        "delete_files",
        {"bucket_id": TEST_BUCKET, "paths": ["nonexistent/file.txt"]},
        live_context,
    )
    assert result is not None


@skip_if_no_creds
@pytest.mark.asyncio
async def test_12_delete_bucket(live_context):
    result = await supabase.execute_action("delete_bucket", {"bucket_id": TEST_BUCKET}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data["deleted"] is True


# ---- Auth Actions ----


@skip_if_no_creds
@pytest.mark.asyncio
async def test_13_list_users(live_context):
    result = await supabase.execute_action("list_users", {}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "users" in result.result.data
    assert "total" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_14_get_user(live_context):
    list_result = await supabase.execute_action("list_users", {}, live_context)
    assert list_result.type != ResultType.ACTION_ERROR
    users = list_result.result.data.get("users", [])
    if not users:
        pytest.skip("No users in project to fetch")
    user_id = users[0]["id"]
    result = await supabase.execute_action("get_user", {"user_id": user_id}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data["user"]["id"] == user_id


@skip_if_no_creds
@pytest.mark.asyncio
async def test_15_delete_user(live_context):
    test_user_id = os.getenv("SUPABASE_TEST_DELETE_USER_ID", "")
    if not test_user_id:
        pytest.skip("SUPABASE_TEST_DELETE_USER_ID not set — skipping destructive test")
    result = await supabase.execute_action("delete_user", {"user_id": test_user_id}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data["deleted"] is True
