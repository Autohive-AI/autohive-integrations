"""Unit tests for the GitHub Actions workflow, run, job and artifact actions."""

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.unit


REPO = {"owner": "octocat", "repo": "Hello-World"}

SAMPLE_RUN = {
    "id": 30433642,
    "name": "Build",
    "display_title": "Fix the thing",
    "node_id": "MDEyOldvcmtmbG93IFJ1bjI2OTI4OQ==",
    "head_branch": "main",
    "head_sha": "acb5820ced9479c074f688cc328bf03f341a511d",
    "path": ".github/workflows/build.yml",
    "run_number": 562,
    "run_attempt": 1,
    "event": "push",
    "status": "completed",
    "conclusion": "failure",
    "workflow_id": 159038,
    "created_at": "2020-01-22T19:33:08Z",
    "updated_at": "2020-01-22T19:33:08Z",
    "run_started_at": "2020-01-22T19:33:08Z",
    "actor": {"login": "octocat", "avatar_url": "https://github.com/images/error/octocat.gif"},
    "triggering_actor": {"login": "hubot", "avatar_url": "https://github.com/images/error/hubot.gif"},
    "head_commit": {
        "id": "acb5820ced9479c074f688cc328bf03f341a511d",
        "message": "Fix the thing",
        "author": {"name": "Octo Cat", "email": "octocat@github.com"},
    },
    "logs_url": "https://api.github.com/repos/octocat/Hello-World/actions/runs/30433642/logs",
    "html_url": "https://github.com/octocat/Hello-World/actions/runs/30433642",
}

SAMPLE_JOB = {
    "id": 399444496,
    "run_id": 30433642,
    "run_attempt": 1,
    "workflow_name": "Build",
    "head_branch": "main",
    "head_sha": "acb5820ced9479c074f688cc328bf03f341a511d",
    "name": "build",
    "status": "completed",
    "conclusion": "success",
    "created_at": "2020-01-20T17:42:40Z",
    "started_at": "2020-01-20T17:42:40Z",
    "completed_at": "2020-01-20T17:44:39Z",
    "runner_name": "my-runner",
    "labels": ["ubuntu-latest"],
    "steps": [
        {
            "name": "Set up job",
            "status": "completed",
            "conclusion": "success",
            "number": 1,
            "started_at": "2020-01-20T09:42:40.000-08:00",
            "completed_at": "2020-01-20T09:42:41.000-08:00",
        }
    ],
    "html_url": "https://github.com/octocat/Hello-World/runs/399444496",
}

SAMPLE_ARTIFACT = {
    "id": 11,
    "node_id": "MDg6QXJ0aWZhY3QxMQ==",
    "name": "coverage-report",
    "size_in_bytes": 453,
    "url": "https://api.github.com/repos/octocat/Hello-World/actions/artifacts/11",
    "archive_download_url": "https://api.github.com/repos/octocat/Hello-World/actions/artifacts/11/zip",
    "expired": False,
    "created_at": "2020-01-10T14:59:22Z",
    "expires_at": "2020-03-21T14:59:22Z",
    "updated_at": "2020-02-21T14:59:22Z",
    "digest": "sha256:cfc3236bdad15b5898bca8408945c9e19e1917da8704adc20eaa618444fd4",
    "workflow_run": {
        "id": 30433642,
        "repository_id": 1296269,
        "head_repository_id": 1296269,
        "head_branch": "main",
        "head_sha": "acb5820ced9479c074f688cc328bf03f341a511d",
    },
}

SAMPLE_TIMING = {
    "billable": {
        "UBUNTU": {"total_ms": 180000, "jobs": 2, "job_runs": [{"job_id": 1, "duration_ms": 180000}]},
        "MACOS": {"total_ms": 240000, "jobs": 1, "job_runs": [{"job_id": 2, "duration_ms": 240000}]},
    },
    "run_duration_ms": 500000,
}


def _jobs_page(jobs):
    return FetchResponse(status=200, headers={}, data={"total_count": len(jobs), "jobs": jobs})


def _artifacts_page(artifacts):
    return FetchResponse(status=200, headers={}, data={"total_count": len(artifacts), "artifacts": artifacts})


class TestGetWorkflowRun:
    @pytest.mark.asyncio
    async def test_returns_shaped_run(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_RUN)

        result = await github.execute_action("get_workflow_run", {**REPO, "run_id": 30433642}, mock_context)

        assert result.result.data["id"] == 30433642
        assert result.result.data["conclusion"] == "failure"
        assert result.result.data["actor"] == {
            "login": "octocat",
            "avatar_url": "https://github.com/images/error/octocat.gif",
        }
        assert result.result.data["head_commit"]["author"] == "Octo Cat"
        assert result.result.data["url"] == "https://github.com/octocat/Hello-World/actions/runs/30433642"

    @pytest.mark.asyncio
    async def test_requests_run_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_RUN)

        await github.execute_action("get_workflow_run", {**REPO, "run_id": 30433642}, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/actions/runs/30433642")

    @pytest.mark.asyncio
    async def test_tolerates_missing_nested_objects(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"id": 1, "html_url": "https://github.com/x"}
        )

        result = await github.execute_action("get_workflow_run", {**REPO, "run_id": 1}, mock_context)

        assert result.result.data["actor"] is None
        assert result.result.data["head_commit"] is None
        assert result.result.data["run_attempt"] == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await github.execute_action("get_workflow_run", {**REPO, "run_id": 1}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message


class TestRunWorkflow:
    @pytest.mark.asyncio
    async def test_sends_ref_in_json_body_and_handles_empty_response(self, mock_context):
        # A workflow_dispatch answers 204 No Content, which the SDK surfaces as data=None.
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await github.execute_action(
            "run_workflow", {**REPO, "workflow_id": "ci.yml", "ref": "main"}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"
        assert mock_context.fetch.call_args.kwargs["json"]["ref"] == "main"
        assert mock_context.fetch.call_args.args[0].endswith("/actions/workflows/ci.yml/dispatches")
        assert result.result.data["dispatched"] is True
        assert result.result.data["run_id"] is None
        assert "204 No Content" in result.result.data["message"]

    @pytest.mark.asyncio
    async def test_empty_string_body_does_not_raise(self, mock_context):
        # 202/empty bodies come back as "" rather than None; .get() on that would blow up.
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data="")

        result = await github.execute_action(
            "run_workflow", {**REPO, "workflow_id": 161335, "ref": "main"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["workflow_id"] == "161335"

    @pytest.mark.asyncio
    async def test_sends_workflow_inputs(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await github.execute_action(
            "run_workflow",
            {**REPO, "workflow_id": "ci.yml", "ref": "release/1.0", "inputs": {"environment": "staging"}},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"]["inputs"] == {"environment": "staging"}
        assert "return_run_details" not in mock_context.fetch.call_args.kwargs["json"]
        assert result.result.data["inputs"] == {"environment": "staging"}

    @pytest.mark.asyncio
    async def test_return_run_details_surfaces_run_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "workflow_run_id": 30433642,
                "run_url": "https://api.github.com/repos/octocat/Hello-World/actions/runs/30433642",
                "html_url": "https://github.com/octocat/Hello-World/actions/runs/30433642",
            },
        )

        result = await github.execute_action(
            "run_workflow",
            {**REPO, "workflow_id": "ci.yml", "ref": "main", "return_run_details": True},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["json"]["return_run_details"] is True
        assert result.result.data["run_id"] == 30433642
        assert result.result.data["url"] == "https://github.com/octocat/Hello-World/actions/runs/30433642"

    @pytest.mark.asyncio
    async def test_rejects_more_than_25_inputs(self, mock_context):
        result = await github.execute_action(
            "run_workflow",
            {**REPO, "workflow_id": "ci.yml", "ref": "main", "inputs": {f"k{i}": "v" for i in range(26)}},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "at most 25 inputs" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_workflow_filename_is_url_encoded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await github.execute_action(
            "run_workflow", {**REPO, "workflow_id": "my workflow.yml", "ref": "main"}, mock_context
        )

        assert mock_context.fetch.call_args.args[0].endswith("/actions/workflows/my%20workflow.yml/dispatches")


class TestRerunWorkflowRun:
    @pytest.mark.asyncio
    async def test_posts_to_rerun_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=None)

        result = await github.execute_action("rerun_workflow_run", {**REPO, "run_id": 30433642}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"
        assert mock_context.fetch.call_args.args[0].endswith("/actions/runs/30433642/rerun")
        assert result.result.data["rerun_requested"] is True
        assert result.result.data["scope"] == "all_jobs"
        assert result.result.data["url"] == "https://github.com/octocat/Hello-World/actions/runs/30433642"

    @pytest.mark.asyncio
    async def test_forwards_enable_debug_logging(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data={})

        await github.execute_action(
            "rerun_workflow_run", {**REPO, "run_id": 1, "enable_debug_logging": True}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["json"]["enable_debug_logging"] is True


class TestRerunFailedJobs:
    @pytest.mark.asyncio
    async def test_posts_to_rerun_failed_jobs_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=None)

        result = await github.execute_action("rerun_failed_jobs", {**REPO, "run_id": 30433642}, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/actions/runs/30433642/rerun-failed-jobs")
        assert result.result.data["scope"] == "failed_jobs"


class TestCancelWorkflowRun:
    @pytest.mark.asyncio
    async def test_posts_to_cancel_endpoint(self, mock_context):
        # GitHub answers 202 Accepted; the SDK leaves an empty non-JSON body as "".
        mock_context.fetch.return_value = FetchResponse(status=202, headers={}, data="")

        result = await github.execute_action("cancel_workflow_run", {**REPO, "run_id": 30433642}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"
        assert mock_context.fetch.call_args.args[0].endswith("/actions/runs/30433642/cancel")
        assert result.result.data["cancelled"] is True
        assert result.result.data["run_id"] == 30433642


class TestListWorkflowJobs:
    @pytest.mark.asyncio
    async def test_returns_shaped_jobs_with_steps(self, mock_context):
        mock_context.fetch.return_value = _jobs_page([SAMPLE_JOB])

        result = await github.execute_action("list_workflow_jobs", {**REPO, "run_id": 30433642}, mock_context)

        assert len(result.result.data) == 1
        assert result.result.data[0]["id"] == 399444496
        assert result.result.data[0]["steps"][0]["name"] == "Set up job"
        assert result.result.data[0]["url"] == "https://github.com/octocat/Hello-World/runs/399444496"

    @pytest.mark.asyncio
    async def test_forwards_filter(self, mock_context):
        mock_context.fetch.return_value = _jobs_page([SAMPLE_JOB])

        await github.execute_action("list_workflow_jobs", {**REPO, "run_id": 30433642, "filter": "all"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["params"]["filter"] == "all"

    @pytest.mark.asyncio
    async def test_paginates_until_short_page(self, mock_context):
        full_page = [dict(SAMPLE_JOB, id=index) for index in range(100)]
        mock_context.fetch.side_effect = [_jobs_page(full_page), _jobs_page([dict(SAMPLE_JOB, id=100)])]

        result = await github.execute_action("list_workflow_jobs", {**REPO, "run_id": 30433642}, mock_context)

        assert len(result.result.data) == 101
        assert mock_context.fetch.call_count == 2


class TestGetJobLogs:
    @pytest.mark.asyncio
    async def test_returns_full_log_when_short(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data="line one\nline two")

        result = await github.execute_action("get_job_logs", {**REPO, "job_id": 399444496}, mock_context)

        assert result.result.data["logs"] == "line one\nline two"
        assert result.result.data["total_lines"] == 2
        assert result.result.data["returned_lines"] == 2
        assert result.result.data["truncated"] is False
        assert mock_context.fetch.call_args.args[0].endswith("/actions/jobs/399444496/logs")

    @pytest.mark.asyncio
    async def test_truncates_to_tail_lines(self, mock_context):
        log_text = "\n".join(f"line {index}" for index in range(1000))
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=log_text)

        result = await github.execute_action(
            "get_job_logs", {**REPO, "job_id": 399444496, "tail_lines": 10}, mock_context
        )

        assert result.result.data["total_lines"] == 1000
        assert result.result.data["returned_lines"] == 10
        assert result.result.data["truncated"] is True
        assert result.result.data["logs"].splitlines()[0] == "line 990"
        assert result.result.data["logs"].splitlines()[-1] == "line 999"

    @pytest.mark.asyncio
    async def test_defaults_to_500_tail_lines(self, mock_context):
        log_text = "\n".join(f"line {index}" for index in range(900))
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=log_text)

        result = await github.execute_action("get_job_logs", {**REPO, "job_id": 1}, mock_context)

        assert result.result.data["tail_lines"] == 500
        assert result.result.data["returned_lines"] == 500

    @pytest.mark.asyncio
    async def test_strips_leading_byte_order_mark(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data="\ufeff2020-01-01 hello")

        result = await github.execute_action("get_job_logs", {**REPO, "job_id": 1}, mock_context)

        assert result.result.data["logs"] == "2020-01-01 hello"

    @pytest.mark.asyncio
    async def test_empty_log_body_does_not_raise(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=None)

        result = await github.execute_action("get_job_logs", {**REPO, "job_id": 1}, mock_context)

        assert result.result.data["logs"] == ""
        assert result.result.data["total_lines"] == 0
        assert result.result.data["truncated"] is False


class TestGetWorkflowRunLogs:
    @pytest.mark.asyncio
    async def test_returns_archive_url_and_job_summaries(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_RUN),
            _jobs_page([SAMPLE_JOB]),
        ]

        result = await github.execute_action("get_workflow_run_logs", {**REPO, "run_id": 30433642}, mock_context)

        assert result.result.data["archive_returned"] is False
        assert result.result.data["logs_archive_url"].endswith("/actions/runs/30433642/logs")
        assert result.result.data["jobs"] == [
            {"id": 399444496, "name": "build", "status": "completed", "conclusion": "success"}
        ]
        assert "ZIP archive" in result.result.data["note"]

    @pytest.mark.asyncio
    async def test_never_requests_the_zip_archive(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=SAMPLE_RUN),
            _jobs_page([]),
        ]

        await github.execute_action("get_workflow_run_logs", {**REPO, "run_id": 30433642}, mock_context)

        requested = [call.args[0] for call in mock_context.fetch.call_args_list]
        assert not any(url.endswith("/logs") for url in requested)


class TestListWorkflowRunArtifacts:
    @pytest.mark.asyncio
    async def test_returns_shaped_artifacts(self, mock_context):
        mock_context.fetch.return_value = _artifacts_page([SAMPLE_ARTIFACT])

        result = await github.execute_action("list_workflow_run_artifacts", {**REPO, "run_id": 30433642}, mock_context)

        assert result.result.data[0]["name"] == "coverage-report"
        assert result.result.data[0]["size_in_bytes"] == 453
        assert result.result.data[0]["workflow_run"]["head_branch"] == "main"

    @pytest.mark.asyncio
    async def test_forwards_name_filter(self, mock_context):
        mock_context.fetch.return_value = _artifacts_page([SAMPLE_ARTIFACT])

        await github.execute_action(
            "list_workflow_run_artifacts", {**REPO, "run_id": 1, "name": "coverage-report"}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["params"]["name"] == "coverage-report"

    @pytest.mark.asyncio
    async def test_null_workflow_run_is_tolerated(self, mock_context):
        mock_context.fetch.return_value = _artifacts_page([dict(SAMPLE_ARTIFACT, workflow_run=None)])

        result = await github.execute_action("list_workflow_run_artifacts", {**REPO, "run_id": 1}, mock_context)

        assert result.result.data[0]["workflow_run"] is None


class TestDownloadWorkflowRunArtifact:
    @pytest.mark.asyncio
    async def test_returns_metadata_not_the_archive(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ARTIFACT)

        result = await github.execute_action(
            "download_workflow_run_artifact", {**REPO, "artifact_id": 11}, mock_context
        )

        assert mock_context.fetch.call_args.args[0].endswith("/actions/artifacts/11")
        assert not mock_context.fetch.call_args.args[0].endswith("/zip")
        assert result.result.data["archive_returned"] is False
        assert result.result.data["archive_download_url"].endswith("/actions/artifacts/11/zip")
        assert "ZIP" in result.result.data["note"]

    @pytest.mark.asyncio
    async def test_expired_artifact_gets_expired_note(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=dict(SAMPLE_ARTIFACT, expired=True)
        )

        result = await github.execute_action(
            "download_workflow_run_artifact", {**REPO, "artifact_id": 11}, mock_context
        )

        assert result.result.data["expired"] is True
        assert "410 Gone" in result.result.data["note"]


class TestGetWorkflowRunUsage:
    @pytest.mark.asyncio
    async def test_returns_billable_minutes_per_os(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_TIMING)

        result = await github.execute_action("get_workflow_run_usage", {**REPO, "run_id": 30433642}, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/actions/runs/30433642/timing")
        by_os = {entry["os"]: entry for entry in result.result.data["billable"]}
        assert by_os["UBUNTU"]["billable_minutes"] == 3.0
        assert by_os["MACOS"]["billable_minutes"] == 4.0
        assert by_os["UBUNTU"]["job_runs"] == [{"job_id": 1, "duration_ms": 180000}]
        assert result.result.data["total_billable_minutes"] == 7.0
        assert result.result.data["run_duration_minutes"] == 8.33

    @pytest.mark.asyncio
    async def test_missing_billable_block_returns_zeros(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await github.execute_action("get_workflow_run_usage", {**REPO, "run_id": 1}, mock_context)

        assert result.result.data["billable"] == []
        assert result.result.data["total_billable_minutes"] == 0.0


class TestDeleteWorkflowRunLogs:
    @pytest.mark.asyncio
    async def test_delete_returns_deleted_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await github.execute_action("delete_workflow_run_logs", {**REPO, "run_id": 30433642}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"
        assert mock_context.fetch.call_args.args[0].endswith("/actions/runs/30433642/logs")
        assert result.result.data == {"deleted": True, "run_id": 30433642}
