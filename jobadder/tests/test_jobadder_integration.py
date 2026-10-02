"""Read-only end-to-end tests for the JobAdder integration.

These tests call the real JobAdder API. Set JOBADDER_ACCESS_TOKEN and
JOBADDER_API_URL in the repository-root .env file. Detail tests also require
the corresponding JOBADDER_TEST_*_ID value.

Run safely with:
    pytest jobadder/tests/test_jobadder_integration.py -m "integration and not destructive"

The four write actions are intentionally excluded because JobAdder has no delete
endpoint for reliably cleaning up candidates, applications, or candidate
attachments created by tests, and attachment updates cannot be safely restored.
"""

import asyncio
import base64
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
        "contact": env_credentials("JOBADDER_TEST_CONTACT_ID"),
        "company": env_credentials("JOBADDER_TEST_COMPANY_ID"),
        "note": env_credentials("JOBADDER_TEST_NOTE_ID"),
        "application": env_credentials("JOBADDER_TEST_APPLICATION_ID"),
        "placement": env_credentials("JOBADDER_TEST_PLACEMENT_ID"),
    }


def assert_list_result(result, records_key: str, max_items: int | None = 2) -> None:
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert isinstance(data[records_key], list)
    if max_items is not None:
        assert len(data[records_key]) <= max_items
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

    async def test_list_candidate_attachment_categories(self, live_context):
        result = await jobadder.execute_action("list_candidate_attachment_categories", {}, live_context)
        assert_list_result(result, "categories", max_items=None)

    async def test_download_candidate_attachment(self, live_context, resource_ids):
        candidate_id = require_integer_id(resource_ids["candidate"], "JOBADDER_TEST_CANDIDATE_ID")
        list_result = await jobadder.execute_action(
            "list_candidate_attachments", {"candidate_id": candidate_id, "limit": 1}, live_context
        )
        attachments = list_result.result.data["attachments"]
        if not attachments:
            pytest.skip("The configured candidate has no attachments")

        attachment = attachments[0]
        result = await jobadder.execute_action(
            "download_candidate_attachment",
            {
                "candidate_id": candidate_id,
                "attachment_id": attachment["attachmentId"],
                "file_name": attachment.get("fileName") or "candidate-attachment",
            },
            live_context,
        )

        assert result.type == ResultType.ACTION
        file = result.result.data["file"]
        assert file["name"]
        assert file["contentType"]
        assert base64.b64decode(file["content"], validate=True)


NOTE_TYPE_ACTIONS = [
    "list_candidate_note_types",
    "list_contact_note_types",
    "list_job_note_types",
    "list_placement_note_types",
    "list_company_note_types",
]


class TestNoteTypes:
    @pytest.mark.parametrize("action", NOTE_TYPE_ACTIONS)
    async def test_list_note_types(self, live_context, action):
        result = await jobadder.execute_action(action, {}, live_context)
        assert_list_result(result, "note_types", max_items=None)


class TestContactsAndActivities:
    async def test_list_contacts(self, live_context):
        result = await jobadder.execute_action("list_contacts", {"limit": 2}, live_context)
        assert_list_result(result, "contacts")

    async def test_get_contact(self, live_context, resource_ids):
        contact_id = require_integer_id(resource_ids["contact"], "JOBADDER_TEST_CONTACT_ID")
        result = await jobadder.execute_action("get_contact", {"contact_id": contact_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["contact"]["contactId"] == contact_id

    async def test_list_contact_notes(self, live_context, resource_ids):
        contact_id = require_integer_id(resource_ids["contact"], "JOBADDER_TEST_CONTACT_ID")
        result = await jobadder.execute_action("list_contact_notes", {"contact_id": contact_id}, live_context)
        assert_list_result(result, "notes", max_items=None)

    async def test_list_contact_activities(self, live_context, resource_ids):
        contact_id = require_integer_id(resource_ids["contact"], "JOBADDER_TEST_CONTACT_ID")
        result = await jobadder.execute_action(
            "list_contact_activities", {"contact_id": contact_id, "limit": 2}, live_context
        )
        assert_list_result(result, "activities")

    async def test_list_all_contact_activities(self, live_context, resource_ids):
        contact_id = require_integer_id(resource_ids["contact"], "JOBADDER_TEST_CONTACT_ID")
        result = await jobadder.execute_action(
            "list_all_contact_activities",
            {
                "contact_ids": [contact_id],
                "created_at_from": "2000-01-01T00:00:00Z",
                "created_at_to": "2100-01-01T00:00:00Z",
                "limit": 2,
            },
            live_context,
        )
        assert_list_result(result, "activities")

    async def test_get_note(self, live_context, resource_ids):
        note_id = resource_ids["note"]
        if not note_id:
            pytest.skip("JOBADDER_TEST_NOTE_ID not set")
        result = await jobadder.execute_action("get_note", {"note_id": note_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["note"]["noteId"] == note_id

    async def test_list_contact_jobs(self, live_context, resource_ids):
        contact_id = require_integer_id(resource_ids["contact"], "JOBADDER_TEST_CONTACT_ID")
        result = await jobadder.execute_action("list_contact_jobs", {"contact_id": contact_id}, live_context)
        assert_list_result(result, "jobs", max_items=None)


class TestCompanies:
    async def test_list_companies(self, live_context):
        result = await jobadder.execute_action("list_companies", {"limit": 2}, live_context)
        assert_list_result(result, "companies")

    async def test_get_company(self, live_context, resource_ids):
        company_id = require_integer_id(resource_ids["company"], "JOBADDER_TEST_COMPANY_ID")
        result = await jobadder.execute_action("get_company", {"company_id": company_id}, live_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["company"]["companyId"] == company_id


RELATED_LIVE_CASES = [
    ("list_candidate_applications", "candidate", "candidate_id", "applications", {"limit": 2}),
    ("list_candidate_active_applications", "candidate", "candidate_id", "applications", {"limit": 2}),
    ("list_candidate_placements", "candidate", "candidate_id", "placements", {}),
    ("list_candidate_approved_placements", "candidate", "candidate_id", "placements", {}),
    ("list_candidate_attachments", "candidate", "candidate_id", "attachments", {"limit": 2}),
    ("list_candidate_skills", "candidate", "candidate_id", "skills", {}),
    ("list_candidate_notes", "candidate", "candidate_id", "notes", {"limit": 2}),
    ("list_job_applications", "job", "job_id", "applications", {"limit": 2}),
    ("list_job_active_applications", "job", "job_id", "applications", {"limit": 2}),
    ("list_job_placements", "job", "job_id", "placements", {}),
    ("list_job_approved_placements", "job", "job_id", "placements", {}),
    ("list_job_attachments", "job", "job_id", "attachments", {"limit": 2}),
    ("list_job_notes", "job", "job_id", "notes", {"limit": 2}),
    ("list_job_activities", "job", "job_id", "activities", {}),
    ("list_application_attachments", "application", "application_id", "attachments", {"limit": 2}),
    ("list_application_notes", "application", "application_id", "notes", {"limit": 2}),
    ("list_application_activities", "application", "application_id", "activities", {}),
    ("list_placement_attachments", "placement", "placement_id", "attachments", {"limit": 2}),
    ("list_placement_notes", "placement", "placement_id", "notes", {"limit": 2}),
    ("list_placement_timesheets", "placement", "placement_id", "timesheets", {}),
    ("list_placement_activities", "placement", "placement_id", "activities", {}),
    ("list_company_contacts", "company", "company_id", "contacts", {}),
    ("list_company_addresses", "company", "company_id", "addresses", {}),
    ("list_company_jobs", "company", "company_id", "jobs", {"limit": 2}),
    ("list_company_active_jobs", "company", "company_id", "jobs", {"limit": 2}),
    ("list_company_placements", "company", "company_id", "placements", {}),
    ("list_company_approved_placements", "company", "company_id", "placements", {}),
    ("list_company_attachments", "company", "company_id", "attachments", {"limit": 2}),
    ("list_company_notes", "company", "company_id", "notes", {"limit": 2}),
]


class TestRelatedResources:
    @pytest.mark.parametrize("action,resource_key,id_field,records_key,extra_inputs", RELATED_LIVE_CASES)
    async def test_list_related_resource(
        self, live_context, resource_ids, action, resource_key, id_field, records_key, extra_inputs
    ):
        resource_id = require_integer_id(resource_ids[resource_key], f"JOBADDER_TEST_{resource_key.upper()}_ID")
        result = await jobadder.execute_action(action, {id_field: resource_id, **extra_inputs}, live_context)

        assert_list_result(result, records_key, max_items=2 if "limit" in extra_inputs else None)

    async def test_get_candidate_availability(self, live_context, resource_ids):
        candidate_id = require_integer_id(resource_ids["candidate"], "JOBADDER_TEST_CANDIDATE_ID")
        result = await jobadder.execute_action(
            "get_candidate_availability", {"candidate_id": candidate_id}, live_context
        )

        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data["availability"], dict)


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
