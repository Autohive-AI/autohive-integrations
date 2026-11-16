"""Inspect composed HTTP requests through both production and live-test transports."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from autohive_integrations_sdk import ExecutionContext
from autohive_integrations_sdk.integration import ResultType
from yarl import URL

from jobadder.jobadder import jobadder
from jobadder.tests import test_jobadder_integration as live_tests


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("transport", ["sdk", "live_test"])
@pytest.mark.parametrize("date_field,query_key", [("created_at_from", "CreatedAt"), ("updated_at_from", "UpdatedAt")])
async def test_activity_http_query_matches_published_contract(
    mock_context, make_context, monkeypatch, transport, date_field, query_key
):
    """Do not mock fetch: inspect aiohttp's final query after transport encoding."""
    date = "2026-10-17T01:14:04.123456+00:00"
    seen = []
    http_response = MagicMock()
    http_response.status = 200
    http_response.ok = True
    http_response.headers = {"Content-Type": "application/json"}
    http_response.json = AsyncMock(return_value={"items": [], "totalCount": 0})

    def capture_request(method, url, **kwargs):
        request = aiohttp.ClientRequest(method, URL(url), params=kwargs.get("params"))
        seen.append(request.url)
        # These exact names come from GET /jobs/activities in JobAdder's OpenAPI,
        # independently of the action's mapping and the transport implementation.
        assert dict(request.url.query) == {
            query_key: ">" + date,
            "IncludeDetails": "false",
            "Offset": "0",
            "Limit": "2",
        }
        manager = MagicMock()
        manager.__aenter__ = AsyncMock(return_value=http_response)
        manager.__aexit__ = AsyncMock(return_value=False)
        return manager

    session = MagicMock()
    session.request.side_effect = capture_request
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    if transport == "sdk":
        context = ExecutionContext(auth=mock_context.auth)
        context.metadata = mock_context.metadata
        context._session = session
    else:
        monkeypatch.setattr(aiohttp, "ClientSession", lambda: session)
        credentials = {
            "JOBADDER_ACCESS_TOKEN": mock_context.auth["credentials"]["access_token"],
            "JOBADDER_API_URL": mock_context.metadata["api"],
        }
        context = live_tests.live_context.__wrapped__(credentials.get, make_context)

    result = await jobadder.execute_action(
        "search_job_activities", {date_field: date, "include_details": False, "limit": 2}, context
    )

    assert result.type == ResultType.ACTION, result.result
    assert result.result.data == {"activities": [], "total_count": 0, "links": {}}
    assert len(seen) == 1
    assert seen[0].path == "/v2/jobs/activities"
