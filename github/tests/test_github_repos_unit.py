import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from github import github

pytestmark = pytest.mark.unit

SAMPLE_REPO = {
    "id": 1,
    "name": "Hello-World",
    "full_name": "octocat/Hello-World",
    "description": "A test repo",
    "private": False,
    "fork": False,
    "default_branch": "main",
    "created_at": "2020-01-01T00:00:00Z",
    "updated_at": "2021-01-01T00:00:00Z",
    "pushed_at": "2021-01-01T00:00:00Z",
    "clone_url": "https://github.com/octocat/Hello-World.git",
    "ssh_url": "git@github.com:octocat/Hello-World.git",
    "html_url": "https://github.com/octocat/Hello-World",
    "language": "Python",
    "visibility": "public",
    "forks_count": 5,
    "stargazers_count": 10,
    "watchers_count": 10,
    "open_issues_count": 2,
    "has_issues": True,
    "has_wiki": True,
}

# ---- Repository Actions ----


class TestGetRepository:
    @pytest.mark.asyncio
    async def test_returns_repo_data(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_REPO)

        result = await github.execute_action(
            "get_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert result.result.data["name"] == "Hello-World"
        assert result.result.data["full_name"] == "octocat/Hello-World"

    @pytest.mark.asyncio
    async def test_request_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_REPO)

        await github.execute_action("get_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "repos/octocat/Hello-World" in url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("API error")

        result = await github.execute_action(
            "get_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_token_returns_action_error(self, mock_context):
        mock_context.auth = {"credentials": {}}

        result = await github.execute_action(
            "get_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "token" in result.result.message.lower()


class TestListRepositories:
    @pytest.mark.asyncio
    async def test_returns_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_REPO])

        result = await github.execute_action("list_repositories", {}, mock_context)

        assert isinstance(result.result.data, list)
        assert result.result.data[0]["name"] == "Hello-World"

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        result = await github.execute_action("list_repositories", {}, mock_context)

        assert result.result.data == []


class TestCreateRepository:
    @pytest.mark.asyncio
    async def test_creates_repo(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_REPO)

        result = await github.execute_action("create_repository", {"name": "Hello-World"}, mock_context)

        assert result.result.data["name"] == "Hello-World"
        assert result.result.data["clone_url"] == SAMPLE_REPO["clone_url"]

    @pytest.mark.asyncio
    async def test_request_uses_post(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_REPO)

        await github.execute_action("create_repository", {"name": "Hello-World"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_org_repo_uses_org_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_REPO)

        await github.execute_action("create_repository", {"name": "Hello-World", "org": "myorg"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "orgs/myorg/repos" in url

    @pytest.mark.asyncio
    async def test_user_repo_uses_user_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=201, headers={}, data=SAMPLE_REPO)

        await github.execute_action("create_repository", {"name": "Hello-World"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "user/repos" in url


class TestDeleteRepository:
    @pytest.mark.asyncio
    async def test_delete_returns_deleted_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await github.execute_action(
            "delete_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert result.result.data["deleted"] is True
        assert "octocat/Hello-World" in result.result.data["repository"]

    @pytest.mark.asyncio
    async def test_request_uses_delete(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        await github.execute_action("delete_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"


class TestUpdateRepository:
    @pytest.mark.asyncio
    async def test_updates_repo(self, mock_context):
        updated = {**SAMPLE_REPO, "description": "Updated description"}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=updated)

        result = await github.execute_action(
            "update_repository",
            {"owner": "octocat", "repo": "Hello-World", "description": "Updated description"},
            mock_context,
        )

        assert result.result.data["name"] == "Hello-World"

    @pytest.mark.asyncio
    async def test_request_uses_patch(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_REPO)

        await github.execute_action("update_repository", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        assert mock_context.fetch.call_args.kwargs["method"] == "PATCH"


class TestListUserRepositories:
    @pytest.mark.asyncio
    async def test_returns_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_REPO])

        result = await github.execute_action("list_user_repositories", {}, mock_context)

        assert isinstance(result.result.data, list)
        assert result.result.data[0]["name"] == "Hello-World"

    @pytest.mark.asyncio
    async def test_with_username_uses_users_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await github.execute_action("list_user_repositories", {"username": "octocat"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "users/octocat/repos" in url


class TestListOrganizationRepositories:
    @pytest.mark.asyncio
    async def test_returns_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[SAMPLE_REPO])

        result = await github.execute_action("list_organization_repositories", {"org": "myorg"}, mock_context)

        assert isinstance(result.result.data, list)

    @pytest.mark.asyncio
    async def test_uses_org_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await github.execute_action("list_organization_repositories", {"org": "myorg"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "orgs/myorg/repos" in url
