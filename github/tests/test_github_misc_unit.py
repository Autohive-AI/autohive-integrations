import os
import sys
import importlib
import base64

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


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


# ---- Webhook Actions ----


class TestCreateWebhook:
    @pytest.mark.asyncio
    async def test_creates_webhook(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201,
            headers={},
            data={
                "id": 1,
                "name": "web",
                "active": True,
                "events": ["push"],
                "config": {"url": "https://example.com/webhook", "content_type": "json"},
                "created_at": "2021-01-01T00:00:00Z",
                "updated_at": "2021-01-01T00:00:00Z",
                "url": "https://api.github.com/repos/octocat/Hello-World/hooks/1",
            },
        )

        result = await github.execute_action(
            "create_webhook",
            {"owner": "octocat", "repo": "Hello-World", "url": "https://example.com/webhook", "events": ["push"]},
            mock_context,
        )

        assert result.result.data["id"] == 1
        assert result.result.data["active"] is True
        assert result.result.data["events"] == ["push"]

    @pytest.mark.asyncio
    async def test_request_uses_post(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201,
            headers={},
            data={
                "id": 1,
                "name": "web",
                "active": True,
                "events": ["push"],
                "config": {"url": "https://...", "content_type": "json"},
                "created_at": "",
                "updated_at": "",
                "url": "",
            },
        )

        await github.execute_action(
            "create_webhook",
            {"owner": "octocat", "repo": "Hello-World", "url": "https://example.com/webhook", "events": ["push"]},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["method"] == "POST"


class TestDeleteWebhook:
    @pytest.mark.asyncio
    async def test_delete_returns_deleted_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)

        result = await github.execute_action(
            "delete_webhook", {"owner": "octocat", "repo": "Hello-World", "hook_id": 42}, mock_context
        )

        assert result.result.data["deleted"] is True
        assert result.result.data["hook_id"] == 42


class TestListWebhooks:
    @pytest.mark.asyncio
    async def test_returns_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=[
                {
                    "id": 1,
                    "name": "web",
                    "active": True,
                    "events": ["push"],
                    "config": {"url": "https://example.com/webhook", "content_type": "json"},
                    "created_at": "2021-01-01T00:00:00Z",
                    "updated_at": "2021-01-01T00:00:00Z",
                    "url": "https://api.github.com/...",
                }
            ],
        )

        result = await github.execute_action("list_webhooks", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        assert isinstance(result.result.data, list)
        assert result.result.data[0]["id"] == 1


# ---- File Operations ----


class TestGetFileContent:
    @pytest.mark.asyncio
    async def test_returns_decoded_content(self, mock_context):
        raw_content = base64.b64encode(b"Hello, World!").decode("utf-8")
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "content": raw_content + "\n",
                "sha": "file_sha_123",
                "size": 13,
                "name": "README.md",
                "path": "README.md",
            },
        )

        result = await github.execute_action(
            "get_file_content", {"owner": "octocat", "repo": "Hello-World", "path": "README.md"}, mock_context
        )

        assert result.result.data["content"] == "Hello, World!"
        assert result.result.data["sha"] == "file_sha_123"
        assert result.result.data["name"] == "README.md"

    @pytest.mark.asyncio
    async def test_url_includes_contents_path(self, mock_context):
        raw_content = base64.b64encode(b"test").decode("utf-8")
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"content": raw_content, "sha": "x", "size": 4, "name": "test.txt", "path": "test.txt"},
        )

        await github.execute_action(
            "get_file_content", {"owner": "octocat", "repo": "Hello-World", "path": "test.txt"}, mock_context
        )

        url = mock_context.fetch.call_args.args[0]
        assert "contents/test.txt" in url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("File not found")

        result = await github.execute_action(
            "get_file_content", {"owner": "octocat", "repo": "Hello-World", "path": "missing.txt"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestCreateFile:
    @pytest.mark.asyncio
    async def test_creates_file(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201,
            headers={},
            data={
                "content": {"name": "hello.txt", "path": "hello.txt", "sha": "new_sha", "size": 5},
                "commit": {"sha": "commit_sha", "message": "Add hello.txt"},
            },
        )

        result = await github.execute_action(
            "create_file",
            {
                "owner": "octocat",
                "repo": "Hello-World",
                "path": "hello.txt",
                "message": "Add hello.txt",
                "content": "Hello",
            },
            mock_context,
        )

        assert result.result.data["content"]["name"] == "hello.txt"
        assert result.result.data["commit"]["sha"] == "commit_sha"

    @pytest.mark.asyncio
    async def test_content_is_base64_encoded(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=201,
            headers={},
            data={
                "content": {"name": "f.txt", "path": "f.txt", "sha": "s", "size": 4},
                "commit": {"sha": "c", "message": "m"},
            },
        )

        await github.execute_action(
            "create_file",
            {"owner": "octocat", "repo": "Hello-World", "path": "f.txt", "message": "m", "content": "test"},
            mock_context,
        )

        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["content"] == base64.b64encode(b"test").decode("utf-8")


class TestDeleteFile:
    @pytest.mark.asyncio
    async def test_delete_returns_deleted_true(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"commit": {"sha": "del_commit", "message": "Remove file"}},
        )

        result = await github.execute_action(
            "delete_file",
            {"owner": "octocat", "repo": "Hello-World", "path": "old.txt", "message": "Remove file", "sha": "file_sha"},
            mock_context,
        )

        assert result.result.data["deleted"] is True
        assert result.result.data["path"] == "old.txt"
        assert result.result.data["commit"]["sha"] == "del_commit"


# ---- User and Org Actions ----


class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user_data(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "login": "octocat",
                "id": 1,
                "name": "The Octocat",
                "company": "@github",
                "blog": "https://github.blog",
                "location": "San Francisco, CA",
                "email": None,
                "bio": "A GitHub mascot",
                "public_repos": 8,
                "public_gists": 8,
                "followers": 4000,
                "following": 9,
                "created_at": "2011-01-25T18:44:36Z",
                "updated_at": "2021-01-01T00:00:00Z",
                "avatar_url": "https://github.com/images/error/octocat.gif",
                "html_url": "https://github.com/octocat",
            },
        )

        result = await github.execute_action("get_user", {"username": "octocat"}, mock_context)

        assert result.result.data["login"] == "octocat"
        assert result.result.data["public_repos"] == 8

    @pytest.mark.asyncio
    async def test_with_username_uses_users_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "login": "octocat",
                "id": 1,
                "name": None,
                "company": None,
                "blog": None,
                "location": None,
                "email": None,
                "bio": None,
                "public_repos": 0,
                "public_gists": 0,
                "followers": 0,
                "following": 0,
                "created_at": "",
                "updated_at": "",
                "avatar_url": "",
                "html_url": "",
            },
        )

        await github.execute_action("get_user", {"username": "octocat"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "users/octocat" in url


# ---- Workflow Actions ----


class TestListWorkflows:
    @pytest.mark.asyncio
    async def test_returns_workflows(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "total_count": 1,
                "workflows": [
                    {
                        "id": 161335,
                        "name": "CI",
                        "path": ".github/workflows/ci.yml",
                        "state": "active",
                        "created_at": "2021-01-01T00:00:00Z",
                        "updated_at": "2021-01-01T00:00:00Z",
                        "html_url": "https://github.com/octocat/Hello-World/actions/workflows/ci.yml",
                    }
                ],
            },
        )

        result = await github.execute_action(
            "list_workflows", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert isinstance(result.result.data, list)
        assert result.result.data[0]["name"] == "CI"
        assert result.result.data[0]["state"] == "active"


class TestGetRateLimit:
    @pytest.mark.asyncio
    async def test_returns_rate_limit_data(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "resources": {
                    "core": {"limit": 5000, "remaining": 4999, "reset": 1372700873, "used": 1},
                    "search": {"limit": 30, "remaining": 18, "reset": 1372697452, "used": 12},
                    "graphql": {"limit": 5000, "remaining": 4993, "reset": 1372700389, "used": 7},
                }
            },
        )

        result = await github.execute_action("get_rate_limit", {}, mock_context)

        assert result.result.data["core"]["limit"] == 5000
        assert result.result.data["core"]["remaining"] == 4999
        assert result.result.data["search"]["limit"] == 30

    @pytest.mark.asyncio
    async def test_url_is_rate_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "resources": {
                    "core": {"limit": 5000, "remaining": 5000, "reset": 0, "used": 0},
                    "search": {"limit": 30, "remaining": 30, "reset": 0, "used": 0},
                    "graphql": {"limit": 5000, "remaining": 5000, "reset": 0, "used": 0},
                }
            },
        )

        await github.execute_action("get_rate_limit", {}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "rate_limit" in url


# ---- Tags and Releases ----


class TestListTags:
    @pytest.mark.asyncio
    async def test_returns_tags(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=[
                {
                    "name": "v1.0.0",
                    "commit": {"sha": "abc123", "url": "https://..."},
                    "zipball_url": "https://...",
                    "tarball_url": "https://...",
                    "node_id": "MDM6UmVm",
                }
            ],
        )

        result = await github.execute_action("list_tags", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        assert isinstance(result.result.data, list)
        assert result.result.data[0]["name"] == "v1.0.0"


class TestGetLatestRelease:
    @pytest.mark.asyncio
    async def test_returns_latest_release(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": 1,
                "tag_name": "v1.0.0",
                "name": "First release",
                "body": "Release notes",
                "draft": False,
                "prerelease": False,
                "created_at": "2021-01-01T00:00:00Z",
                "published_at": "2021-01-01T00:00:00Z",
                "html_url": "https://github.com/octocat/Hello-World/releases/tag/v1.0.0",
                "assets": [],
            },
        )

        result = await github.execute_action(
            "get_latest_release", {"owner": "octocat", "repo": "Hello-World"}, mock_context
        )

        assert result.result.data["tag_name"] == "v1.0.0"

    @pytest.mark.asyncio
    async def test_url_contains_releases_latest(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": 1,
                "tag_name": "v1.0.0",
                "name": None,
                "body": None,
                "draft": False,
                "prerelease": False,
                "created_at": "",
                "published_at": "",
                "html_url": "",
                "assets": [],
            },
        )

        await github.execute_action("get_latest_release", {"owner": "octocat", "repo": "Hello-World"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "releases/latest" in url


class TestGetReleaseByTag:
    @pytest.mark.asyncio
    async def test_returns_release_for_tag(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": 1,
                "tag_name": "v1.0.0",
                "name": "First release",
                "body": None,
                "draft": False,
                "prerelease": False,
                "created_at": "",
                "published_at": "",
                "html_url": "",
                "assets": [],
            },
        )

        result = await github.execute_action(
            "get_release_by_tag", {"owner": "octocat", "repo": "Hello-World", "tag": "v1.0.0"}, mock_context
        )

        assert result.result.data["tag_name"] == "v1.0.0"

    @pytest.mark.asyncio
    async def test_tag_url_encoded_in_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "id": 1,
                "tag_name": "release/2024-01",
                "name": None,
                "body": None,
                "draft": False,
                "prerelease": False,
                "created_at": "",
                "published_at": "",
                "html_url": "",
                "assets": [],
            },
        )

        await github.execute_action(
            "get_release_by_tag", {"owner": "octocat", "repo": "Hello-World", "tag": "release/2024-01"}, mock_context
        )

        url = mock_context.fetch.call_args.args[0]
        assert "release%2F2024-01" in url
