"""Read-only end-to-end tests for the JobAdder integration.

These tests call the real JobAdder API. Set JOBADDER_ACCESS_TOKEN and
JOBADDER_API_URL in the repository-root .env file. Detail tests also require
the corresponding JOBADDER_TEST_*_ID value.

Run safely with:
    pytest jobadder/tests/test_jobadder_integration.py -m "integration and not destructive"

The write actions are intentionally excluded because JobAdder has no delete
endpoint for reliably cleaning up candidates or applications created by tests.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from jobadder.jobadder import jobadder


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def respect_jobadder_rate_limit():
    await asyncio.sleep(1)


def require_integer_id(value: str | None, variable_name: str) -> int:
    if not value:
        pytest.skip(f"{variable_name} not set")
    try:
        return int(value)
    except ValueError:
        pytest.fail(f"{variable_name} must be an integer")


@pytest.fixture
def live_context(env_credentials, make_context):
    access_token = env_credentials("JOBADDER_ACCESS_TOKEN")
    api_url = env_credentials("JOBADDER_API_URL")
    if not access_token or not api_url:
        pytest.skip("JOBADDER_ACCESS_TOKEN and JOBADDER_API_URL are required")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {access_token}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=merged_headers, params=params) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    raise RuntimeError(f"JobAdder returned HTTP {response.status}: {data}")
                return FetchResponse(status=response.status, headers=dict(response.headers), data=data)

    context = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_token},
        }
    )
    context.fetch = AsyncMock(side_effect=real_fetch)
    context.metadata = {"api": api_url}
    return context


@pytest.fixture
def resource_ids(env_credentials):
    return {
        "job": env_credentials("JOBADDER_TEST_JOB_ID"),
        "candidate": env_credentials("JOBADDER_TEST_CANDIDATE_ID"),
        "application": env_credentials("JOBADDER_TEST_APPLICATION_ID"),
        "placement": env_credentials("JOBADDER_TEST_PLACEMENT_ID"),
    }


def assert_list_result(result, records_key: str) -> None:
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert isinstance(data[records_key], list)
    assert len(data[records_key]) <= 2
    assert isinstance(data["total_count"], int)
    assert isinstance(data["links"], dict)


class TestCurrentUser:
    async def test_get_current_user(self, live_context):
        result = await jobadder.execute_action("get_current_user", {}, live_context)

        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data["user"], dict)
        assert "userId" in result.result.data["user"]


class TestJobs:
    async def test_list_jobs(self, live_context):
        result = await jobadder.execute_action("list_jobs", {"limit": 2}, live_context)
        assert_list_result(result, "jobs")

    async def test_get_job(self, live_context, resource_ids):
        job_id = require_integer_id(resource_ids["job"], "JOBADDER_TEST_JOB_ID")
        result = await jobadder.execute_action("get_job", {"job_id": job_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["job"]["jobId"] == job_id


class TestCandidates:
    async def test_list_candidates(self, live_context):
        result = await jobadder.execute_action("list_candidates", {"limit": 2}, live_context)
        assert_list_result(result, "candidates")

    async def test_get_candidate(self, live_context, resource_ids):
        candidate_id = require_integer_id(resource_ids["candidate"], "JOBADDER_TEST_CANDIDATE_ID")
        result = await jobadder.execute_action("get_candidate", {"candidate_id": candidate_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["candidate"]["candidateId"] == candidate_id


class TestApplications:
    async def test_list_applications(self, live_context):
        result = await jobadder.execute_action("list_applications", {"limit": 2}, live_context)
        assert_list_result(result, "applications")

    async def test_get_application(self, live_context, resource_ids):
        application_id = require_integer_id(resource_ids["application"], "JOBADDER_TEST_APPLICATION_ID")
        result = await jobadder.execute_action("get_application", {"application_id": application_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["application"]["applicationId"] == application_id


class TestPlacements:
    async def test_list_placements(self, live_context):
        result = await jobadder.execute_action("list_placements", {"limit": 2}, live_context)
        assert_list_result(result, "placements")

    async def test_get_placement(self, live_context, resource_ids):
        placement_id = require_integer_id(resource_ids["placement"], "JOBADDER_TEST_PLACEMENT_ID")
        result = await jobadder.execute_action("get_placement", {"placement_id": placement_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["placement"]["placementId"] == placement_id
