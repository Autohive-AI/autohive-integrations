"""Unit tests for the organization issue type/field actions and the sub-issue actions.

The original six issue actions are covered by test_github_issues_unit.py.
"""

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.unit

REPO_INPUTS = {"owner": "octocat", "repo": "Hello-World"}

SAMPLE_ISSUE_TYPE = {
    "id": 410,
    "node_id": "IT_kwDNAd3OAAABBg",
    "name": "Bug",
    "description": "An unexpected problem or behavior",
    "color": "red",
    "created_at": "2024-11-14T14:32:14Z",
    "updated_at": "2024-11-14T14:32:14Z",
    "is_enabled": True,
}

SAMPLE_SELECT_FIELD = {
    "id": 1,
    "node_id": "IF_kwDOAAAAAM4AAAAB",
    "name": "Priority",
    "description": "How urgent this work is",
    "data_type": "single_select",
    "visibility": "all",
    "options": [
        {
            "id": 11,
            "name": "P0",
            "description": "Drop everything",
            "color": "red",
            "priority": 1,
            "created_at": "2024-11-14T14:32:14Z",
            "updated_at": "2024-11-14T14:32:14Z",
        }
    ],
    "created_at": "2024-11-14T14:32:14Z",
    "updated_at": "2024-11-14T14:32:14Z",
}

SAMPLE_TEXT_FIELD = {
    "id": 2,
    "node_id": "IF_kwDOAAAAAM4AAAAC",
    "name": "Customer",
    "description": None,
    "data_type": "text",
    "visibility": "organization_members_only",
    "options": None,
    "created_at": "2024-11-14T14:32:14Z",
    "updated_at": "2024-11-14T14:32:14Z",
}

SAMPLE_USER = {"login": "octocat", "avatar_url": "https://github.com/images/octocat.png"}

SAMPLE_PARENT_ISSUE = {
    "id": 1001,
    "number": 42,
    "title": "Ship the API",
    "body": "Tracking issue",
    "state": "open",
    "created_at": "2021-01-01T00:00:00Z",
    "updated_at": "2021-01-02T00:00:00Z",
    "closed_at": None,
    "user": SAMPLE_USER,
    "assignees": [{"login": "hubot"}],
    "labels": [{"name": "epic", "color": "ededed"}],
    "sub_issues_summary": {"total": 3, "completed": 1, "percent_completed": 33},
    "html_url": "https://github.com/octocat/Hello-World/issues/42",
}

SAMPLE_SUB_ISSUE = {
    "id": 2002,
    "number": 43,
    "title": "Write the handler",
    "body": None,
    "state": "open",
    "created_at": "2021-01-01T00:00:00Z",
    "updated_at": "2021-01-02T00:00:00Z",
    "closed_at": None,
    "user": SAMPLE_USER,
    "assignees": [],
    "labels": [],
    "html_url": "https://github.com/octocat/Hello-World/issues/43",
}

PARENT_INPUTS = {**REPO_INPUTS, "issue_number": 42}


def _sub_issue(index: int) -> dict:
    """Build a distinct sub-issue payload for pagination tests."""
    return {**SAMPLE_SUB_ISSUE, "id": 3000 + index, "number": 100 + index, "title": f"sub-{index}"}


# ---- Organization issue types and fields ----


class TestListIssueTypes:
    @pytest.mark.asyncio
    async def test_returns_shaped_issue_types(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_ISSUE_TYPE])

        result = await github.execute_action("list_issue_types", {"org": "octo-org"}, mock_context)

        assert result.type == ResultType.ACTION
        issue_type = result.result.data[0]
        assert issue_type["id"] == 410
        assert issue_type["name"] == "Bug"
        assert issue_type["color"] == "red"
        assert issue_type["is_enabled"] is True

    @pytest.mark.asyncio
    async def test_request_targets_org_issue_types_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_ISSUE_TYPE])

        await github.execute_action("list_issue_types", {"org": "octo-org"}, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/orgs/octo-org/issue-types")

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=None)

        result = await github.execute_action("list_issue_types", {"org": "octo-org"}, mock_context)

        assert result.result.data == []


class TestListIssueFields:
    @pytest.mark.asyncio
    async def test_returns_shaped_fields_with_options(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_SELECT_FIELD])

        result = await github.execute_action("list_issue_fields", {"org": "octo-org"}, mock_context)

        assert result.type == ResultType.ACTION
        issue_field = result.result.data[0]
        assert issue_field["name"] == "Priority"
        assert issue_field["data_type"] == "single_select"
        assert issue_field["options"] == [
            {"id": 11, "name": "P0", "description": "Drop everything", "color": "red", "priority": 1}
        ]

    @pytest.mark.asyncio
    async def test_field_without_options_returns_none(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_TEXT_FIELD])

        result = await github.execute_action("list_issue_fields", {"org": "octo-org"}, mock_context)

        assert result.result.data[0]["options"] is None

    @pytest.mark.asyncio
    async def test_request_targets_org_issue_fields_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_TEXT_FIELD])

        await github.execute_action("list_issue_fields", {"org": "octo-org"}, mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/orgs/octo-org/issue-fields")


# ---- Sub-issues ----


class TestListSubIssues:
    @pytest.mark.asyncio
    async def test_returns_shaped_sub_issues(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_SUB_ISSUE])

        result = await github.execute_action("list_sub_issues", dict(PARENT_INPUTS), mock_context)

        assert result.type == ResultType.ACTION
        sub_issue = result.result.data[0]
        assert sub_issue["id"] == 2002
        assert sub_issue["number"] == 43
        assert sub_issue["url"] == SAMPLE_SUB_ISSUE["html_url"]
        assert sub_issue["author"]["login"] == "octocat"
        assert sub_issue["sub_issues_summary"] is None

    @pytest.mark.asyncio
    async def test_request_targets_plural_sub_issues_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_SUB_ISSUE])

        await github.execute_action("list_sub_issues", dict(PARENT_INPUTS), mock_context)

        assert mock_context.fetch.call_args.args[0].endswith("/repos/octocat/Hello-World/issues/42/sub_issues")

    @pytest.mark.asyncio
    async def test_follows_pagination_until_short_page(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data=[_sub_issue(index) for index in range(100)]),
            FetchResponse(status=200, headers={}, data=[_sub_issue(100)]),
        ]

        result = await github.execute_action("list_sub_issues", dict(PARENT_INPUTS), mock_context)

        assert mock_context.fetch.call_count == 2
        assert len(result.result.data) == 101

    @pytest.mark.asyncio
    async def test_limit_caps_returned_sub_issues(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data=[_sub_issue(index) for index in range(5)]
        )

        result = await github.execute_action("list_sub_issues", {**PARENT_INPUTS, "limit": 3}, mock_context)

        assert len(result.result.data) == 3

    @pytest.mark.asyncio
    async def test_author_missing_returns_none(self, mock_context):
        orphaned = {**SAMPLE_SUB_ISSUE, "user": None}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[orphaned])

        result = await github.execute_action("list_sub_issues", dict(PARENT_INPUTS), mock_context)

        assert result.result.data[0]["author"] is None


class TestAddSubIssue:
    @pytest.mark.asyncio
    async def test_returns_parent_issue(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PARENT_ISSUE)

        result = await github.execute_action("add_sub_issue", {**PARENT_INPUTS, "sub_issue_id": 2002}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["added"] is True
        assert result.result.data["sub_issue_id"] == 2002
        assert result.result.data["parent"]["number"] == 42
        assert result.result.data["parent"]["sub_issues_summary"]["total"] == 3

    @pytest.mark.asyncio
    async def test_posts_sub_issue_id_not_number(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PARENT_ISSUE)

        await github.execute_action("add_sub_issue", {**PARENT_INPUTS, "sub_issue_id": 2002}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"
        assert mock_context.fetch.call_args.args[0].endswith("/issues/42/sub_issues")
        assert mock_context.fetch.call_args.kwargs["json"] == {"sub_issue_id": 2002}

    @pytest.mark.asyncio
    async def test_replace_parent_is_forwarded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_PARENT_ISSUE)

        await github.execute_action(
            "add_sub_issue", {**PARENT_INPUTS, "sub_issue_id": 2002, "replace_parent": True}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"sub_issue_id": 2002, "replace_parent": True}


class TestRemoveSubIssue:
    @pytest.mark.asyncio
    async def test_returns_removed_marker_and_parent(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PARENT_ISSUE)

        result = await github.execute_action("remove_sub_issue", {**PARENT_INPUTS, "sub_issue_id": 2002}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["removed"] is True
        assert result.result.data["sub_issue_id"] == 2002
        assert result.result.data["parent"]["number"] == 42

    @pytest.mark.asyncio
    async def test_deletes_against_singular_sub_issue_path_with_body(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PARENT_ISSUE)

        await github.execute_action("remove_sub_issue", {**PARENT_INPUTS, "sub_issue_id": 2002}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"
        assert mock_context.fetch.call_args.args[0].endswith("/issues/42/sub_issue")
        assert mock_context.fetch.call_args.kwargs["json"] == {"sub_issue_id": 2002}


class TestReprioritizeSubIssue:
    @pytest.mark.asyncio
    async def test_returns_reprioritized_marker_and_parent(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PARENT_ISSUE)

        result = await github.execute_action(
            "reprioritize_sub_issue", {**PARENT_INPUTS, "sub_issue_id": 2002, "after_id": 2001}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["reprioritized"] is True
        assert result.result.data["parent"]["number"] == 42

    @pytest.mark.asyncio
    async def test_patches_priority_endpoint_with_after_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PARENT_ISSUE)

        await github.execute_action(
            "reprioritize_sub_issue", {**PARENT_INPUTS, "sub_issue_id": 2002, "after_id": 2001}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"
        assert mock_context.fetch.call_args.args[0].endswith("/issues/42/sub_issues/priority")
        assert mock_context.fetch.call_args.kwargs["json"] == {"sub_issue_id": 2002, "after_id": 2001}

    @pytest.mark.asyncio
    async def test_before_id_is_forwarded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_PARENT_ISSUE)

        await github.execute_action(
            "reprioritize_sub_issue", {**PARENT_INPUTS, "sub_issue_id": 2002, "before_id": 2003}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["json"] == {"sub_issue_id": 2002, "before_id": 2003}

    @pytest.mark.asyncio
    async def test_requires_exactly_one_position_argument(self, mock_context):
        result = await github.execute_action(
            "reprioritize_sub_issue",
            {**PARENT_INPUTS, "sub_issue_id": 2002, "after_id": 2001, "before_id": 2003},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "exactly one" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_position_argument_errors(self, mock_context):
        result = await github.execute_action(
            "reprioritize_sub_issue", {**PARENT_INPUTS, "sub_issue_id": 2002}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "exactly one" in result.result.message
        mock_context.fetch.assert_not_called()


class TestIssueExtensionErrorHandling:
    @pytest.mark.asyncio
    async def test_list_issue_types_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await github.execute_action("list_issue_types", {"org": "octo-org"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message

    @pytest.mark.asyncio
    async def test_add_sub_issue_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Validation Failed")

        result = await github.execute_action("add_sub_issue", {**PARENT_INPUTS, "sub_issue_id": 2002}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Validation Failed" in result.result.message
