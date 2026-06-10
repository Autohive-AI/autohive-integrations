from unittest.mock import AsyncMock, MagicMock
import pytest
from fergus.fergus import fergus

pytestmark = pytest.mark.unit


def _fetch_result(data):
    result = MagicMock()
    result.data = data
    return result


@pytest.mark.asyncio
async def test_create_job_non_draft(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 1, "title": "Fix Tap"}))
    result = await fergus.execute_action(
        "create_job",
        {
            "job_type": "Charge Up",
            "title": "Fix Tap",
            "description": "Leaking tap",
            "customer_id": 10,
            "site_id": 20,
        },
        mock_context,
    )
    assert result.result.data["job"]["id"] == 1
    mock_context.fetch.assert_called_once()
    call_kwargs = mock_context.fetch.call_args
    assert call_kwargs[1]["method"] == "POST"


@pytest.mark.asyncio
async def test_create_job_draft(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 2, "isDraft": True}))
    result = await fergus.execute_action(
        "create_job",
        {"job_type": "Quote", "title": "Draft Job", "is_draft": True},
        mock_context,
    )
    assert result.result.data["job"]["id"] == 2


@pytest.mark.asyncio
async def test_create_job_missing_fields_non_draft(mock_context):
    with pytest.raises(Exception):
        await fergus.execute_action(
            "create_job",
            {"job_type": "Charge Up", "title": "No Details"},
            mock_context,
        )


@pytest.mark.asyncio
async def test_update_job(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 5, "title": "Updated"}))
    result = await fergus.execute_action(
        "update_job",
        {"job_id": 5, "title": "Updated"},
        mock_context,
    )
    assert result.result.data["job"]["id"] == 5
    call_kwargs = mock_context.fetch.call_args
    assert call_kwargs[1]["method"] == "PUT"


@pytest.mark.asyncio
async def test_update_job_no_fields(mock_context):
    with pytest.raises(Exception):
        await fergus.execute_action("update_job", {"job_id": 5}, mock_context)


@pytest.mark.asyncio
async def test_finalise_job(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 7, "status": "Active"}))
    result = await fergus.execute_action("finalise_job", {"job_id": 7}, mock_context)
    assert result.result.data["job"]["id"] == 7
    call_kwargs = mock_context.fetch.call_args
    assert "/finalise" in call_kwargs[0][0]


@pytest.mark.asyncio
async def test_get_job(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 3, "title": "Tap Fix"}))
    result = await fergus.execute_action("get_job", {"job_id": 3}, mock_context)
    assert result.result.data["job"]["id"] == 3
    call_kwargs = mock_context.fetch.call_args
    assert call_kwargs[1]["method"] == "GET"


@pytest.mark.asyncio
async def test_list_jobs_no_filters(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result([{"id": 1}, {"id": 2}]))
    result = await fergus.execute_action("list_jobs", {}, mock_context)
    assert isinstance(result.result.data["jobs"], list)


@pytest.mark.asyncio
async def test_list_jobs_with_filters(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result([{"id": 10}]))
    result = await fergus.execute_action(
        "list_jobs",
        {"status": "Completed", "page_size": 5, "customer_id": 99},
        mock_context,
    )
    assert result.result.data["jobs"][0]["id"] == 10
    params = mock_context.fetch.call_args[1]["params"]
    assert params["filterJobStatus"] == "Completed"
    assert params["pageSize"] == 5
    assert params["filterCustomerId"] == 99


@pytest.mark.asyncio
async def test_search_customers(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result([{"id": 1, "name": "Acme"}]))
    result = await fergus.execute_action(
        "search_customers",
        {"search": "Acme"},
        mock_context,
    )
    assert result.result.data["customers"][0]["name"] == "Acme"
    params = mock_context.fetch.call_args[1]["params"]
    assert params["filterSearchText"] == "Acme"


@pytest.mark.asyncio
async def test_search_customers_no_search(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result([]))
    result = await fergus.execute_action("search_customers", {}, mock_context)
    assert result.result.data["customers"] == []


@pytest.mark.asyncio
async def test_get_customer(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result({"id": 42, "name": "Bob"}))
    result = await fergus.execute_action("get_customer", {"customer_id": 42}, mock_context)
    assert result.result.data["customer"]["id"] == 42
    call_kwargs = mock_context.fetch.call_args
    assert "42" in call_kwargs[0][0]


@pytest.mark.asyncio
async def test_list_sites(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result([{"id": 1, "address": "123 Main St"}]))
    result = await fergus.execute_action("list_sites", {"page_size": 5}, mock_context)
    assert result.result.data["sites"][0]["id"] == 1
    params = mock_context.fetch.call_args[1]["params"]
    assert params["pageSize"] == 5


@pytest.mark.asyncio
async def test_list_sites_with_search(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result([]))
    await fergus.execute_action("list_sites", {"search": "Wellington"}, mock_context)
    params = mock_context.fetch.call_args[1]["params"]
    assert params["filterSearchText"] == "Wellington"


@pytest.mark.asyncio
async def test_list_users(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]))
    result = await fergus.execute_action("list_users", {}, mock_context)
    assert len(result.result.data["users"]) == 2


@pytest.mark.asyncio
async def test_list_users_with_search(mock_context):
    mock_context.fetch = AsyncMock(return_value=_fetch_result([{"id": 1, "name": "Alice"}]))
    await fergus.execute_action("list_users", {"search": "Alice", "page_size": 10}, mock_context)
    params = mock_context.fetch.call_args[1]["params"]
    assert params["filterSearchText"] == "Alice"
    assert params["pageSize"] == 10


@pytest.mark.asyncio
async def test_auth_token_missing(mock_context):
    mock_context.auth = {}
    with pytest.raises(Exception):
        await fergus.execute_action("list_jobs", {}, mock_context)
