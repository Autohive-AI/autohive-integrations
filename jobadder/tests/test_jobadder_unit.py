import json
from pathlib import Path

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from jobadder.jobadder import get_api_base_url, jobadder


_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

pytestmark = pytest.mark.unit


def response(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def list_payload(items=None, total=0):
    return {
        "items": items or [],
        "totalCount": total,
        "links": {"self": "https://au-api.jobadder.com/v2/example"},
    }


class TestConfig:
    def test_actions_match_registered_handlers(self):
        with _CONFIG_PATH.open() as config_file:
            config = json.load(config_file)

        assert set(config["actions"]) == set(jobadder._action_handlers)

    def test_scopes_match_shipped_capabilities(self):
        with _CONFIG_PATH.open() as config_file:
            scopes = set(json.load(config_file)["auth"]["scopes"])

        assert scopes == {
            "offline_access",
            "read_user",
            "read_job",
            "read_candidate",
            "write_candidate",
            "read_jobapplication",
            "write_jobapplication",
            "read_placement",
        }


class TestGetApiBaseUrl:
    def test_uses_oauth_api_url_from_connection_metadata(self, mock_context):
        assert get_api_base_url(mock_context) == "https://au-api.jobadder.com/v2"

    def test_rejects_missing_oauth_api_url(self, mock_context):
        mock_context.metadata = {}
        with pytest.raises(ValueError, match="API URL is missing"):
            get_api_base_url(mock_context)

    @pytest.mark.parametrize("api_url", ["http://api.jobadder.com/v2", "https://example.com/v2"])
    def test_rejects_untrusted_api_url(self, mock_context, api_url):
        mock_context.metadata["api"] = api_url
        with pytest.raises(ValueError, match="HTTPS URL on jobadder.com"):
            get_api_base_url(mock_context)


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_returns_user_and_calls_current_endpoint(self, mock_context):
        user = {"userId": 7, "firstName": "Jane", "lastName": "Recruiter"}
        mock_context.fetch.return_value = response(user)

        result = await jobadder.execute_action("get_current_user", {}, mock_context)

        assert result.result.data["user"] == user
        mock_context.fetch.assert_awaited_once_with("https://au-api.jobadder.com/v2/users/current", method="GET")

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("not authorised")
        result = await jobadder.execute_action("get_current_user", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "not authorised" in result.result.message


class TestListJobs:
    @pytest.mark.asyncio
    async def test_returns_items_count_and_links(self, mock_context):
        jobs = [{"jobId": 11, "jobTitle": "Engineer"}]
        mock_context.fetch.return_value = response(list_payload(jobs, 1))

        result = await jobadder.execute_action("list_jobs", {}, mock_context)

        assert result.result.data["jobs"] == jobs
        assert result.result.data["total_count"] == 1
        assert "self" in result.result.data["links"]

    @pytest.mark.asyncio
    async def test_maps_filters_and_pagination(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())

        await jobadder.execute_action(
            "list_jobs",
            {
                "job_title": "Engineer",
                "company_name": "Acme",
                "company_id": 9,
                "status_id": 2,
                "active": False,
                "owner_user_id": 4,
                "created_at": ">2026-01-01T00:00:00Z",
                "updated_at": "<2026-02-01T00:00:00Z",
                "sort": "-updatedAt",
                "offset": 20,
                "limit": 50,
            },
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.args[0].endswith("/jobs")
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["params"] == {
            "jobTitle": "Engineer",
            "company.name": "Acme",
            "companyId": 9,
            "statusId": 2,
            "active": False,
            "ownerUserId": 4,
            "createdAt": ">2026-01-01T00:00:00Z",
            "updatedAt": "<2026-02-01T00:00:00Z",
            "sort": "-updatedAt",
            "offset": 20,
            "limit": 50,
        }

    @pytest.mark.asyncio
    async def test_uses_default_pagination(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())
        await jobadder.execute_action("list_jobs", {}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"] == {"offset": 0, "limit": 100}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("jobs unavailable")
        result = await jobadder.execute_action("list_jobs", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetJob:
    @pytest.mark.asyncio
    async def test_returns_job_and_uses_id(self, mock_context):
        job = {"jobId": 11, "jobTitle": "Engineer"}
        mock_context.fetch.return_value = response(job)
        result = await jobadder.execute_action("get_job", {"job_id": 11}, mock_context)
        assert result.result.data["job"] == job
        assert mock_context.fetch.call_args.args[0].endswith("/jobs/11")
        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("job not found")
        result = await jobadder.execute_action("get_job", {"job_id": 11}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestListCandidates:
    @pytest.mark.asyncio
    async def test_returns_candidates(self, mock_context):
        candidates = [{"candidateId": 21, "firstName": "Alex"}]
        mock_context.fetch.return_value = response(list_payload(candidates, 1))
        result = await jobadder.execute_action("list_candidates", {}, mock_context)
        assert result.result.data["candidates"] == candidates
        assert result.result.data["total_count"] == 1

    @pytest.mark.asyncio
    async def test_maps_search_filters(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())
        await jobadder.execute_action(
            "list_candidates",
            {
                "name": "Alex",
                "email": "alex@example.com",
                "phone": "123",
                "keywords": "python",
                "status_id": 3,
                "recruiter_user_id": 7,
                "created_at": ">2026-01-01T00:00:00Z",
                "updated_at": "<2026-03-01T00:00:00Z",
                "sort": "lastName",
                "offset": 10,
                "limit": 25,
            },
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0].endswith("/candidates")
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["params"] == {
            "name": "Alex",
            "email": "alex@example.com",
            "phone": "123",
            "keywords": "python",
            "statusId": 3,
            "recruiterUserId": 7,
            "createdAt": ">2026-01-01T00:00:00Z",
            "updatedAt": "<2026-03-01T00:00:00Z",
            "sort": "lastName",
            "offset": 10,
            "limit": 25,
        }

    @pytest.mark.asyncio
    async def test_preserves_zero_limit_for_count_only(self, mock_context):
        mock_context.fetch.return_value = response(list_payload(total=42))
        await jobadder.execute_action("list_candidates", {"limit": 0}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"]["limit"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("candidate search failed")
        result = await jobadder.execute_action("list_candidates", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetCandidate:
    @pytest.mark.asyncio
    async def test_returns_candidate_and_uses_id(self, mock_context):
        candidate = {"candidateId": 21, "firstName": "Alex"}
        mock_context.fetch.return_value = response(candidate)
        result = await jobadder.execute_action("get_candidate", {"candidate_id": 21}, mock_context)
        assert result.result.data["candidate"] == candidate
        assert mock_context.fetch.call_args.args[0].endswith("/candidates/21")
        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("candidate not found")
        result = await jobadder.execute_action("get_candidate", {"candidate_id": 21}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateCandidate:
    @pytest.mark.asyncio
    async def test_returns_created_candidate(self, mock_context):
        candidate = {"candidateId": 21, "firstName": "Alex", "lastName": "Smith"}
        mock_context.fetch.return_value = response(candidate, 201)
        result = await jobadder.execute_action(
            "create_candidate", {"first_name": "Alex", "last_name": "Smith"}, mock_context
        )
        assert result.result.data["candidate"] == candidate

    @pytest.mark.asyncio
    async def test_maps_fields_to_jobadder_body(self, mock_context):
        mock_context.fetch.return_value = response({"candidateId": 21}, 201)
        await jobadder.execute_action(
            "create_candidate",
            {
                "first_name": "Alex",
                "last_name": "Smith",
                "email": "alex@example.com",
                "status_id": 3,
                "seeking": "Yes",
                "skill_tags": ["Python"],
                "recruiter_user_ids": [7],
                "custom_fields": [{"fieldId": 9, "value": "Remote"}],
            },
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0].endswith("/candidates")
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {
            "firstName": "Alex",
            "lastName": "Smith",
            "email": "alex@example.com",
            "statusId": 3,
            "seeking": "Yes",
            "skillTags": ["Python"],
            "recruiterUserId": [7],
            "custom": [{"fieldId": 9, "value": "Remote"}],
        }

    @pytest.mark.asyncio
    async def test_duplicate_override_sets_header(self, mock_context):
        mock_context.fetch.return_value = response({"candidateId": 21}, 201)
        await jobadder.execute_action(
            "create_candidate",
            {"first_name": "Alex", "last_name": "Smith", "allow_duplicates": "override-code"},
            mock_context,
        )
        assert mock_context.fetch.call_args.kwargs["headers"]["X-Allow-Duplicates"] == "override-code"

    @pytest.mark.asyncio
    async def test_allows_provider_supported_email_only_candidate(self, mock_context):
        mock_context.fetch.return_value = response({"candidateId": 21}, 201)

        await jobadder.execute_action("create_candidate", {"email": "alex@example.com"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["json"] == {"email": "alex@example.com"}

    @pytest.mark.asyncio
    async def test_rejects_multiple_availability_shapes(self, mock_context):
        result = await jobadder.execute_action(
            "create_candidate",
            {"availability": {"immediate": True, "date": "2026-10-01"}},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_requires_custom_field_id(self, mock_context):
        result = await jobadder.execute_action(
            "create_candidate",
            {"custom_fields": [{"value": "Remote"}]},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("duplicate candidate")
        result = await jobadder.execute_action(
            "create_candidate", {"first_name": "Alex", "last_name": "Smith"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "duplicate candidate" in result.result.message


class TestListApplications:
    @pytest.mark.asyncio
    async def test_returns_applications(self, mock_context):
        applications = [{"applicationId": 31, "jobTitle": "Engineer"}]
        mock_context.fetch.return_value = response(list_payload(applications, 1))
        result = await jobadder.execute_action("list_applications", {}, mock_context)
        assert result.result.data["applications"] == applications

    @pytest.mark.asyncio
    async def test_maps_filters_including_false_booleans(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())
        await jobadder.execute_action(
            "list_applications",
            {
                "candidate_id": 21,
                "job_id": 11,
                "status_id": 4,
                "job_title": "Engineer",
                "active": False,
                "rejected": False,
                "keywords": "python",
                "sort": "-createdAt",
            },
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0].endswith("/applications")
        assert call.kwargs["method"] == "GET"
        params = call.kwargs["params"]
        assert params["candidateId"] == 21
        assert params["jobId"] == 11
        assert params["active"] is False
        assert params["rejected"] is False
        assert params["sort"] == "-createdAt"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("applications unavailable")
        result = await jobadder.execute_action("list_applications", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetApplication:
    @pytest.mark.asyncio
    async def test_returns_application_and_uses_id(self, mock_context):
        application = {"applicationId": 31}
        mock_context.fetch.return_value = response(application)
        result = await jobadder.execute_action("get_application", {"application_id": 31}, mock_context)
        assert result.result.data["application"] == application
        assert mock_context.fetch.call_args.args[0].endswith("/applications/31")
        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("application not found")
        result = await jobadder.execute_action("get_application", {"application_id": 31}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestAddCandidatesToJob:
    @pytest.mark.asyncio
    async def test_returns_created_applications(self, mock_context):
        applications = [{"applicationId": 31}, {"applicationId": 32}]
        mock_context.fetch.return_value = response(list_payload(applications, 2), 201)
        result = await jobadder.execute_action(
            "add_candidates_to_job", {"job_id": 11, "candidate_ids": [21, 22]}, mock_context
        )
        assert result.result.data["applications"] == applications
        assert result.result.data["total_count"] == 2

    @pytest.mark.asyncio
    async def test_request_url_method_and_body(self, mock_context):
        mock_context.fetch.return_value = response(list_payload(), 201)
        await jobadder.execute_action(
            "add_candidates_to_job",
            {"job_id": 11, "candidate_ids": [21, 22], "source": "Autohive"},
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0].endswith("/jobs/11/applications")
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {"candidateId": [21, 22], "source": "Autohive"}
        assert call.kwargs["headers"] == {"Content-Type": "application/json"}

    @pytest.mark.asyncio
    async def test_omits_source_when_not_supplied(self, mock_context):
        mock_context.fetch.return_value = response(list_payload(), 201)
        await jobadder.execute_action("add_candidates_to_job", {"job_id": 11, "candidate_ids": [21]}, mock_context)
        assert mock_context.fetch.call_args.kwargs["json"] == {"candidateId": [21]}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("candidate already applied")
        result = await jobadder.execute_action(
            "add_candidates_to_job", {"job_id": 11, "candidate_ids": [21]}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR


class TestListPlacements:
    @pytest.mark.asyncio
    async def test_returns_placements(self, mock_context):
        placements = [{"placementId": 41}]
        mock_context.fetch.return_value = response(list_payload(placements, 1))
        result = await jobadder.execute_action("list_placements", {}, mock_context)
        assert result.result.data["placements"] == placements

    @pytest.mark.asyncio
    async def test_maps_placement_filters(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())
        await jobadder.execute_action(
            "list_placements",
            {
                "candidate_id": 21,
                "job_id": 11,
                "company_id": 9,
                "status_id": 5,
                "approved": False,
                "created_at": ">2026-01-01T00:00:00Z",
                "updated_at": "<2026-12-31T23:59:59Z",
                "offset": 5,
                "limit": 10,
            },
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert call.args[0].endswith("/placements")
        assert call.kwargs["method"] == "GET"
        assert call.kwargs["params"] == {
            "candidateId": 21,
            "jobId": 11,
            "companyId": 9,
            "statusId": 5,
            "approved": False,
            "createdAt": ">2026-01-01T00:00:00Z",
            "updatedAt": "<2026-12-31T23:59:59Z",
            "offset": 5,
            "limit": 10,
        }

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("placements unavailable")
        result = await jobadder.execute_action("list_placements", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetPlacement:
    @pytest.mark.asyncio
    async def test_returns_placement_and_uses_id(self, mock_context):
        placement = {"placementId": 41}
        mock_context.fetch.return_value = response(placement)
        result = await jobadder.execute_action("get_placement", {"placement_id": 41}, mock_context)
        assert result.result.data["placement"] == placement
        assert mock_context.fetch.call_args.args[0].endswith("/placements/41")
        assert mock_context.fetch.call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("placement not found")
        result = await jobadder.execute_action("get_placement", {"placement_id": 41}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
