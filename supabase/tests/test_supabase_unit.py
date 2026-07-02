import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import ResultType
from supabase import supabase  # noqa: E402

pytestmark = pytest.mark.unit


# ---- Database Actions ----


@pytest.mark.asyncio
async def test_select_records(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data=[{"id": 1, "name": "Alice"}]))
    result = await supabase.execute_action("select_records", {"table": "users"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["records"] == [{"id": 1, "name": "Alice"}]
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_select_records_with_filters(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data=[]))
    result = await supabase.execute_action(
        "select_records",
        {"table": "users", "filters": {"status": "eq.active"}, "limit": 10, "offset": 0},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["records"] == []


@pytest.mark.asyncio
async def test_select_records_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("connection error"))
    result = await supabase.execute_action("select_records", {"table": "users"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "connection error" in result.result.message


@pytest.mark.asyncio
async def test_insert_records(mock_context):
    records = [{"name": "Bob", "email": "bob@example.com"}]
    mock_context.fetch = AsyncMock(return_value=MagicMock(data=records))
    result = await supabase.execute_action("insert_records", {"table": "users", "records": records}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_insert_records_upsert(mock_context):
    records = [{"id": 1, "name": "Bob"}]
    mock_context.fetch = AsyncMock(return_value=MagicMock(data=records))
    result = await supabase.execute_action(
        "insert_records",
        {"table": "users", "records": records, "on_conflict": "id"},
        mock_context,
    )
    assert result.type == ResultType.ACTION


@pytest.mark.asyncio
async def test_update_records(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data=[{"id": 1, "name": "Updated"}]))
    result = await supabase.execute_action(
        "update_records",
        {"table": "users", "data": {"name": "Updated"}, "filters": {"id": "eq.1"}},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["count"] == 1


@pytest.mark.asyncio
async def test_delete_records(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data=[]))
    result = await supabase.execute_action(
        "delete_records",
        {"table": "users", "filters": {"id": "eq.99"}},
        mock_context,
    )
    assert result.type == ResultType.ACTION


@pytest.mark.asyncio
async def test_call_function(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data={"result": 42}))
    result = await supabase.execute_action(
        "call_function",
        {"function_name": "my_func", "params": {"x": 1}},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["data"] == {"result": 42}


# ---- Storage Actions ----


@pytest.mark.asyncio
async def test_list_buckets(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data=[{"id": "images", "name": "images"}]))
    result = await supabase.execute_action("list_buckets", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert len(result.result.data["buckets"]) == 1


@pytest.mark.asyncio
async def test_get_bucket(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data={"id": "images", "public": True}))
    result = await supabase.execute_action("get_bucket", {"bucket_id": "images"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["bucket"]["id"] == "images"


@pytest.mark.asyncio
async def test_create_bucket(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data={"name": "uploads"}))
    result = await supabase.execute_action("create_bucket", {"name": "uploads", "public": False}, mock_context)
    assert result.type == ResultType.ACTION


@pytest.mark.asyncio
async def test_delete_bucket(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data={}))
    result = await supabase.execute_action("delete_bucket", {"bucket_id": "old-bucket"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


@pytest.mark.asyncio
async def test_list_files(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data=[{"name": "photo.jpg"}]))
    result = await supabase.execute_action("list_files", {"bucket_id": "images", "path": "photos/"}, mock_context)
    assert result.type == ResultType.ACTION
    assert len(result.result.data["files"]) == 1


@pytest.mark.asyncio
async def test_delete_files(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data=[{"name": "photo.jpg"}]))
    result = await supabase.execute_action(
        "delete_files",
        {"bucket_id": "images", "paths": ["photos/photo.jpg"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION


@pytest.mark.asyncio
async def test_delete_files_error_response(mock_context):
    mock_context.fetch = AsyncMock(
        return_value=MagicMock(data={"error": "Object Not Found", "message": "File not found"})
    )
    result = await supabase.execute_action(
        "delete_files",
        {"bucket_id": "images", "paths": ["missing.jpg"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "File not found" in result.result.message


@pytest.mark.asyncio
async def test_get_public_url(mock_context):
    result = await supabase.execute_action(
        "get_public_url",
        {"bucket_id": "images", "path": "photos/cat.jpg"},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert "images/photos/cat.jpg" in result.result.data["public_url"]


# ---- Auth Actions ----


@pytest.mark.asyncio
async def test_list_users(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data={"users": [{"id": "abc"}], "total": 1}))
    result = await supabase.execute_action("list_users", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["total"] == 1


@pytest.mark.asyncio
async def test_get_user(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data={"id": "user-uuid", "email": "test@example.com"}))
    result = await supabase.execute_action("get_user", {"user_id": "user-uuid"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_delete_user(mock_context):
    mock_context.fetch = AsyncMock(return_value=MagicMock(data={}))
    result = await supabase.execute_action("delete_user", {"user_id": "user-uuid"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["deleted"] is True


# ---- Wrapped Auth Envelope ----


@pytest.mark.asyncio
async def test_select_records_wrapped_auth(mock_context):
    mock_context.auth = {
        "auth_type": "Custom",
        "credentials": {
            "host": "https://test.supabase.co",
            "service_role_secret": "test-service-role-secret",  # nosec B105
        },
    }
    mock_context.fetch = AsyncMock(return_value=MagicMock(data=[{"id": 1, "name": "Alice"}]))
    result = await supabase.execute_action("select_records", {"table": "users"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["records"] == [{"id": 1, "name": "Alice"}]
    assert result.result.data["count"] == 1
