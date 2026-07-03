"""
End-to-end integration tests for the Supabase integration.

Requires credentials set in environment variables or a .env file at the repo root:
    SUPABASE_URL             — your project URL (e.g. https://xxxx.supabase.co)
    SUPABASE_SERVICE_ROLE_KEY — service_role key from Project Settings > API

Optional:
    SUPABASE_TEST_TABLE           — table name for DB action tests (select/insert/update/delete)
    SUPABASE_TEST_FUNCTION        — RPC function name for call_function test
    SUPABASE_TEST_DELETE_USER_ID  — user UUID to target for delete_user (destructive)

Run safely (read-only):
    pytest supabase/tests/test_supabase_integration.py -m "integration and not destructive"

Run destructive (mutates real data — use deliberately on a test account):
    pytest supabase/tests/test_supabase_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
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


@pytest.fixture
def live_context(make_context):
    service_role_key = SUPABASE_SERVICE_ROLE_KEY

    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, **kwargs):
        merged = dict(headers or {})
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
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

    ctx = make_context(
        auth={
            "auth_type": "Custom",
            "credentials": {"host": SUPABASE_URL, "service_role_secret": service_role_key},
        }
    )
    ctx.fetch.side_effect = real_fetch
    return ctx


# ---- Read-Only Tests ----


@skip_if_no_creds
@skip_if_no_table
@pytest.mark.asyncio
async def test_02_select_records(live_context):
    result = await supabase.execute_action(
        "select_records",
        {"table": SUPABASE_TEST_TABLE, "limit": 10},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert isinstance(result.result.data["records"], list)


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
    assert result.type == ResultType.ACTION, result.result.message


@skip_if_no_creds
@pytest.mark.asyncio
async def test_07_list_buckets(live_context):
    result = await supabase.execute_action("list_buckets", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert isinstance(result.result.data["buckets"], list)


@skip_if_no_creds
@pytest.mark.asyncio
async def test_10_get_public_url(live_context):
    result = await supabase.execute_action(
        "get_public_url",
        {"bucket_id": "any-bucket", "path": "test/file.txt"},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data["public_url"].startswith("http")


@skip_if_no_creds
@pytest.mark.asyncio
async def test_13_list_users(live_context):
    result = await supabase.execute_action("list_users", {}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert "users" in result.result.data
    assert "total" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_14_get_user(live_context):
    list_result = await supabase.execute_action("list_users", {}, live_context)
    assert list_result.type == ResultType.ACTION, list_result.result.message
    users = list_result.result.data.get("users", [])
    if not users:
        pytest.skip("No users in project to fetch")
    user_id = users[0]["id"]
    result = await supabase.execute_action("get_user", {"user_id": user_id}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data["user"]["id"] == user_id


# ---- Destructive Tests (Write Operations) ----
# These create, update, or delete real data.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
@skip_if_no_creds
@skip_if_no_table
@pytest.mark.asyncio
async def test_01_insert_records(live_context):
    records = [
        {"id": str(uuid.uuid4()), "name": "integration-test-a"},
        {"id": str(uuid.uuid4()), "name": "integration-test-b"},
    ]
    try:
        result = await supabase.execute_action(
            "insert_records",
            {"table": SUPABASE_TEST_TABLE, "records": records},
            live_context,
        )
        assert result.type == ResultType.ACTION, result.result.message
        assert result.result.data["count"] >= 1
    finally:
        for r in records:
            await supabase.execute_action(
                "delete_records",
                {"table": SUPABASE_TEST_TABLE, "filters": {"id": f"eq.{r['id']}"}},
                live_context,
            )


@pytest.mark.destructive
@skip_if_no_creds
@skip_if_no_table
@pytest.mark.asyncio
async def test_03_update_records(live_context):
    record_id = str(uuid.uuid4())
    await supabase.execute_action(
        "insert_records",
        {"table": SUPABASE_TEST_TABLE, "records": [{"id": record_id, "name": f"update-{uuid.uuid4().hex[:6]}"}]},
        live_context,
    )
    try:
        result = await supabase.execute_action(
            "update_records",
            {
                "table": SUPABASE_TEST_TABLE,
                "data": {"name": "updated-name"},
                "filters": {"id": f"eq.{record_id}"},
            },
            live_context,
        )
        assert result.type == ResultType.ACTION, result.result.message
    finally:
        await supabase.execute_action(
            "delete_records",
            {"table": SUPABASE_TEST_TABLE, "filters": {"id": f"eq.{record_id}"}},
            live_context,
        )


@pytest.mark.destructive
@skip_if_no_creds
@skip_if_no_table
@pytest.mark.asyncio
async def test_04_delete_records(live_context):
    record_id = str(uuid.uuid4())
    await supabase.execute_action(
        "insert_records",
        {"table": SUPABASE_TEST_TABLE, "records": [{"id": record_id, "name": f"delete-{uuid.uuid4().hex[:6]}"}]},
        live_context,
    )
    result = await supabase.execute_action(
        "delete_records",
        {"table": SUPABASE_TEST_TABLE, "filters": {"id": f"eq.{record_id}"}},
        live_context,
    )
    assert result.type == ResultType.ACTION, result.result.message


@pytest.mark.destructive
@skip_if_no_creds
@pytest.mark.asyncio
async def test_storage_lifecycle(live_context):
    """create_bucket → get_bucket → list_files → delete_files → delete_bucket."""
    bucket = f"integration-test-{uuid.uuid4().hex[:8]}"
    try:
        # create_bucket
        create_result = await supabase.execute_action("create_bucket", {"name": bucket, "public": True}, live_context)
        assert create_result.type == ResultType.ACTION, create_result.result.message

        # get_bucket
        get_result = await supabase.execute_action("get_bucket", {"bucket_id": bucket}, live_context)
        assert get_result.type == ResultType.ACTION, get_result.result.message
        assert get_result.result.data["bucket"] is not None

        # list_files
        list_result = await supabase.execute_action("list_files", {"bucket_id": bucket}, live_context)
        assert list_result.type == ResultType.ACTION, list_result.result.message
        assert isinstance(list_result.result.data["files"], list)

        # delete_files (nonexistent path — Supabase returns empty list)
        delete_files_result = await supabase.execute_action(
            "delete_files", {"bucket_id": bucket, "paths": ["nonexistent/file.txt"]}, live_context
        )
        assert delete_files_result.type == ResultType.ACTION, delete_files_result.result.message

    finally:
        # delete_bucket (cleanup)
        delete_result = await supabase.execute_action("delete_bucket", {"bucket_id": bucket}, live_context)
        assert delete_result.type == ResultType.ACTION, delete_result.result.message
        assert delete_result.result.data["deleted"] is True


@pytest.mark.destructive
@skip_if_no_creds
@pytest.mark.asyncio
async def test_15_delete_user(live_context):
    test_user_id = os.getenv("SUPABASE_TEST_DELETE_USER_ID", "")
    if not test_user_id:
        pytest.skip("SUPABASE_TEST_DELETE_USER_ID not set — skipping destructive test")
    result = await supabase.execute_action("delete_user", {"user_id": test_user_id}, live_context)
    assert result.type == ResultType.ACTION, result.result.message
    assert result.result.data["deleted"] is True
