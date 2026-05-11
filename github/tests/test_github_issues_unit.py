import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("github_mod", os.path.join(_parent, "github.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

github = _mod.github

pytestmark = pytest.mark.unit

SAMPLE_USER = {"login": "octocat", "avatar_url": "https://github.com/images/octocat.png"}

SAMPLE_ISSUE = {
    "number": 42,
    "title": "Found a bug",
    "body": "Something isn't working",
    "state": "open",
    "created_at": "2021-01-01T00:00:00Z",
    "updated_at": "2021-01-02T00:00:00Z",
    "closed_at": None,
    "user": SAMPLE_USER,
    "assignees": [],
    "labels": [],
    "comments": 0,
    "html_url": "https://github.com/octocat/Hello-World/issues/42",
}

SAMPLE_COMMENT = {
    "id": 1,
    "body": "A comment",
    "created_at": "2021-01-01T00:00:00Z",
    "updated_at": "2021-01-01T00:00:00Z",
    "user": SAMPLE_USER,
    "html_url": "https://github.com/octocat/Hello-World/issues/42#issuecomment-1",
}


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


# ---- Issue Actions ----


class TestGetIssue:
    @pytest.mark.asyncio
    async def test_returns_issue_data(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ISSUE)

        result = await github.execute_action(
            "get_issue", {"owner": "octocat", "repo": "Hello-World", "issue_number": 42}, mock_context
        )

        assert result.result.data["number"] == 42
        assert result.result.data["title"] == "Found a bug"
        assert result.result.data["author"]["login"] == "octocat"

    @pytest.mark.asyncio
    async def test_request_url_includes_issue_number(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ISSUE)

        await github.execute_action(
            "get_issue", {"owner": "octocat", "repo": "Hello-World", "issue_number": 42}, mock_context
        )

        url = mock_context.fetch.call_args.args[0]
        assert "issues/42" in url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await github.execute_action(
            "get_issue", {"owner": "octocat", "repo": "Hello-World", "issue_number": 42}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestListIssues:
    @pytest.mark.asyncio
    async def test_returns_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_ISSUE])

        result = await github.execute_action("list_issues", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        assert isinstance(result.result.data, list)
        assert result.result.data[0]["number"] == 42

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        result = await github.execute_action("list_issues", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        assert result.result.data == []


class TestCreateIssue:
    @pytest.mark.asyncio
    async def test_creates_issue(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_ISSUE)

        result = await github.execute_action(
            "create_issue", {"owner": "octocat", "repo": "Hello-World", "title": "Found a bug"}, mock_context
        )

        assert result.result.data["number"] == 42
        assert result.result.data["title"] == "Found a bug"

    @pytest.mark.asyncio
    async def test_request_uses_post(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_ISSUE)

        await github.execute_action(
            "create_issue", {"owner": "octocat", "repo": "Hello-World", "title": "Found a bug"}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"
        assert "issues" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_title_in_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_ISSUE)

        await github.execute_action(
            "create_issue", {"owner": "octocat", "repo": "Hello-World", "title": "Found a bug"}, mock_context
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["title"] == "Found a bug"


class TestUpdateIssue:
    @pytest.mark.asyncio
    async def test_updates_issue(self, mock_context):
        updated = {**SAMPLE_ISSUE, "state": "closed", "closed_at": "2021-01-03T00:00:00Z"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated)

        result = await github.execute_action(
            "update_issue",
            {"owner": "octocat", "repo": "Hello-World", "issue_number": 42, "state": "closed"},
            mock_context,
        )

        assert result.result.data["state"] == "closed"

    @pytest.mark.asyncio
    async def test_request_uses_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_ISSUE)

        await github.execute_action(
            "update_issue", {"owner": "octocat", "repo": "Hello-World", "issue_number": 42}, mock_context
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"


class TestCreateIssueComment:
    @pytest.mark.asyncio
    async def test_creates_comment(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_COMMENT)

        result = await github.execute_action(
            "create_issue_comment",
            {"owner": "octocat", "repo": "Hello-World", "issue_number": 42, "body": "A comment"},
            mock_context,
        )

        assert result.result.data["id"] == 1
        assert result.result.data["body"] == "A comment"

    @pytest.mark.asyncio
    async def test_body_in_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_COMMENT)

        await github.execute_action(
            "create_issue_comment",
            {"owner": "octocat", "repo": "Hello-World", "issue_number": 42, "body": "A comment"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["body"] == "A comment"


class TestGetIssueComments:
    @pytest.mark.asyncio
    async def test_returns_comments_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_COMMENT])

        result = await github.execute_action(
            "get_issue_comments", {"owner": "octocat", "repo": "Hello-World", "issue_number": 42}, mock_context
        )

        assert isinstance(result.result.data, list)
        assert result.result.data[0]["body"] == "A comment"

    @pytest.mark.asyncio
    async def test_url_includes_issue_comments_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await github.execute_action(
            "get_issue_comments", {"owner": "octocat", "repo": "Hello-World", "issue_number": 42}, mock_context
        )

        url = mock_context.fetch.call_args.args[0]
        assert "issues/42/comments" in url
