import base64
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from clickup.clickup import clickup  # noqa: E402

pytestmark = pytest.mark.unit

V3_BASE = "https://api.clickup.com/api/v3"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _file_input(
    content_bytes: bytes = b"hello world",
    name: str = "hello.txt",
    content_type: str = "text/plain",
):
    return {"name": name, "content": _b64(content_bytes), "contentType": content_type}


class _FakeResponse:
    """Minimal stand-in for aiohttp response inside `async with`."""

    def __init__(self, status: int, json_body=None, text_body: str = ""):
        self.status = status
        self._json = json_body if json_body is not None else {}
        self._text = text_body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self._json

    async def text(self):
        return self._text


class _FakeSession:
    """Stand-in for aiohttp.ClientSession that records the POST call."""

    def __init__(self, response: _FakeResponse):
        self._response = response
        self.post_url = None
        self.post_headers = None
        self.post_data = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url, data=None, headers=None):
        self.post_url = url
        self.post_data = data
        self.post_headers = headers
        return self._response


class TestCreateTaskAttachment:
    @pytest.mark.asyncio
    async def test_happy_path_posts_v3_url_with_bearer_token(self, mock_context):
        response = _FakeResponse(
            200, json_body={"id": "att_1", "url": "https://cdn/x.txt"}
        )
        session = _FakeSession(response)

        with patch("clickup.clickup.aiohttp.ClientSession", return_value=session):
            result = await clickup.execute_action(
                "create_task_attachment",
                {
                    "workspace_id": "90161390530",
                    "task_id": "86d2nt17n",
                    "file": _file_input(),
                },
                mock_context,
            )

        assert result.result.data["result"] is True
        assert result.result.data["attachment"] == {
            "id": "att_1",
            "url": "https://cdn/x.txt",
        }
        assert (
            session.post_url
            == f"{V3_BASE}/workspaces/90161390530/tasks/86d2nt17n/attachments"
        )
        assert session.post_headers == {"Authorization": "Bearer test_token"}

    @pytest.mark.asyncio
    async def test_missing_content_returns_error(self, mock_context):
        file_obj = {"name": "empty.txt", "content": "", "contentType": "text/plain"}
        response = _FakeResponse(200, json_body={})
        session = _FakeSession(response)

        with patch("clickup.clickup.aiohttp.ClientSession", return_value=session):
            result = await clickup.execute_action(
                "create_task_attachment",
                {"workspace_id": "ws", "task_id": "t", "file": file_obj},
                mock_context,
            )

        assert result.result.data["result"] is False
        assert "no content" in result.result.data["error"].lower()
        # Should short-circuit before calling aiohttp
        assert session.post_url is None

    @pytest.mark.asyncio
    async def test_invalid_base64_returns_error(self, mock_context):
        file_obj = {
            "name": "bad.txt",
            "content": "!!!not-base64!!!",
            "contentType": "text/plain",
        }
        response = _FakeResponse(200, json_body={})
        session = _FakeSession(response)

        with patch("clickup.clickup.aiohttp.ClientSession", return_value=session):
            result = await clickup.execute_action(
                "create_task_attachment",
                {"workspace_id": "ws", "task_id": "t", "file": file_obj},
                mock_context,
            )

        assert result.result.data["result"] is False
        assert "decode" in result.result.data["error"].lower()
        assert session.post_url is None

    @pytest.mark.asyncio
    async def test_http_error_surfaces_status_body_and_url(self, mock_context):
        response = _FakeResponse(
            404, text_body='{"status":404,"message":"Not Found or Authorized"}'
        )
        session = _FakeSession(response)

        with patch("clickup.clickup.aiohttp.ClientSession", return_value=session):
            result = await clickup.execute_action(
                "create_task_attachment",
                {"workspace_id": "ws", "task_id": "t", "file": _file_input()},
                mock_context,
            )

        err = result.result.data["error"]
        assert result.result.data["result"] is False
        assert err.startswith("HTTP 404:")
        assert "Not Found or Authorized" in err
        # URL is appended for debugging the 404 case
        assert "url=" in err
        assert "/workspaces/ws/tasks/t/attachments" in err

    @pytest.mark.asyncio
    async def test_filename_override_passed_as_form_field(self, mock_context):
        """Optional `filename` input should override the uploaded file's own name."""
        response = _FakeResponse(200, json_body={"id": "x"})
        session = _FakeSession(response)

        with patch("clickup.clickup.aiohttp.ClientSession", return_value=session):
            await clickup.execute_action(
                "create_task_attachment",
                {
                    "workspace_id": "ws",
                    "task_id": "t",
                    "file": _file_input(name="original.txt"),
                    "filename": "renamed.txt",
                },
                mock_context,
            )

        filenames = [
            f[2] for f in session.post_data._fields if f[0]["name"] == "filename"
        ]
        assert filenames == ["renamed.txt"]

    @pytest.mark.asyncio
    async def test_missing_auth_token_returns_error(self, mock_context):
        mock_context.auth = {"auth_type": "PlatformOauth2", "credentials": {}}
        response = _FakeResponse(200, json_body={})
        session = _FakeSession(response)

        with patch("clickup.clickup.aiohttp.ClientSession", return_value=session):
            result = await clickup.execute_action(
                "create_task_attachment",
                {"workspace_id": "ws", "task_id": "t", "file": _file_input()},
                mock_context,
            )

        assert result.result.data["result"] is False
        assert "authentication" in result.result.data["error"].lower()
        assert session.post_url is None
