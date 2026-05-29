"""Unit tests for the Dropbox integration (mocked, no network)."""

import base64
import json

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from dropbox import dropbox

pytestmark = pytest.mark.unit

DROPBOX_API_BASE_URL = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT_BASE_URL = "https://content.dropboxapi.com/2"


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

SAMPLE_FILE_ENTRY = {
    ".tag": "file",
    "name": "report.pdf",
    "path_display": "/report.pdf",
    "id": "id:abc123",
    "size": 1024,
}

SAMPLE_FOLDER_ENTRY = {
    ".tag": "folder",
    "name": "Projects",
    "path_display": "/Projects",
    "id": "id:def456",
}

SAMPLE_FOLDER_METADATA = {
    ".tag": "folder",
    "name": "new_folder",
    "path_display": "/new_folder",
    "id": "id:fld1",
}


# ---- list_folder ----


class TestListFolder:
    @pytest.mark.asyncio
    async def test_happy_path_initial_listing(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "entries": [SAMPLE_FILE_ENTRY, SAMPLE_FOLDER_ENTRY],
                "cursor": "cursor-1",
                "has_more": False,
            },
        )

        result = await dropbox.execute_action("list_folder", {"path": ""}, mock_context)

        data = result.result.data
        assert data["entries"] == [SAMPLE_FILE_ENTRY, SAMPLE_FOLDER_ENTRY]
        assert data["cursor"] == "cursor-1"
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_initial_request_payload_defaults(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"entries": [], "cursor": "c1", "has_more": False}
        )

        result = await dropbox.execute_action("list_folder", {}, mock_context)

        assert result.type == ResultType.ACTION
        call = mock_context.fetch.call_args
        assert call.args[0] == f"{DROPBOX_API_BASE_URL}/files/list_folder"
        assert call.kwargs["method"] == "POST"
        payload = call.kwargs["json"]
        assert payload["path"] == ""
        assert payload["recursive"] is False
        assert payload["include_deleted"] is False
        assert payload["include_has_explicit_shared_members"] is False
        assert payload["include_mounted_folders"] is True
        assert "limit" not in payload

    @pytest.mark.asyncio
    async def test_initial_request_payload_with_limit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"entries": [], "cursor": "c1", "has_more": False}
        )

        result = await dropbox.execute_action("list_folder", {"path": "/sub", "limit": 50}, mock_context)

        assert result.type == ResultType.ACTION
        payload = mock_context.fetch.call_args.kwargs["json"]
        assert payload["path"] == "/sub"
        assert payload["limit"] == 50

    @pytest.mark.asyncio
    async def test_cursor_omitted_when_api_returns_null(self, mock_context):
        # Output schema declares cursor as a string; the action must drop it
        # when the API omits it / returns null so output validation still passes.
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"entries": [], "cursor": None, "has_more": False}
        )

        result = await dropbox.execute_action("list_folder", {"path": ""}, mock_context)

        assert result.type == ResultType.ACTION
        assert "cursor" not in result.result.data

    @pytest.mark.asyncio
    async def test_cursor_uses_continue_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"entries": [], "cursor": "next-cursor", "has_more": True},
        )

        result = await dropbox.execute_action("list_folder", {"cursor": "abc"}, mock_context)

        call = mock_context.fetch.call_args
        assert call.args[0] == f"{DROPBOX_API_BASE_URL}/files/list_folder/continue"
        assert call.kwargs["json"] == {"cursor": "abc"}
        assert result.result.data["cursor"] == "next-cursor"
        assert result.result.data["has_more"] is True

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 500: Internal Server Error")

        result = await dropbox.execute_action("list_folder", {"path": ""}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 500" in result.result.message


# ---- get_metadata ----


class TestGetMetadata:
    @pytest.mark.asyncio
    async def test_returns_metadata(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_FILE_ENTRY)

        result = await dropbox.execute_action("get_metadata", {"path": "/report.pdf"}, mock_context)

        assert result.result.data["metadata"] == SAMPLE_FILE_ENTRY

    @pytest.mark.asyncio
    async def test_request_url_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await dropbox.execute_action(
            "get_metadata",
            {"path": "/report.pdf", "include_deleted": True},
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.args[0] == f"{DROPBOX_API_BASE_URL}/files/get_metadata"
        assert call.kwargs["method"] == "POST"
        payload = call.kwargs["json"]
        assert payload["path"] == "/report.pdf"
        assert payload["include_deleted"] is True
        assert payload["include_has_explicit_shared_members"] is False

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("path/not_found")

        result = await dropbox.execute_action("get_metadata", {"path": "/nope"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "path/not_found" in result.result.message


# ---- get_temporary_link ----


class TestGetTemporaryLink:
    @pytest.mark.asyncio
    async def test_returns_link_and_metadata(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"link": "https://dl.dropboxusercontent.com/temp/abc", "metadata": SAMPLE_FILE_ENTRY},
        )

        result = await dropbox.execute_action("get_temporary_link", {"path": "/report.pdf"}, mock_context)

        data = result.result.data
        assert data["link"].startswith("https://")
        assert data["metadata"] == SAMPLE_FILE_ENTRY

    @pytest.mark.asyncio
    async def test_request_url_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"link": "x", "metadata": {}})

        await dropbox.execute_action("get_temporary_link", {"path": "/report.pdf"}, mock_context)

        call = mock_context.fetch.call_args
        assert call.args[0] == f"{DROPBOX_API_BASE_URL}/files/get_temporary_link"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {"path": "/report.pdf"}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("rate limited")

        result = await dropbox.execute_action("get_temporary_link", {"path": "/x"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "rate limited" in result.result.message


# ---- upload_file ----


def _file_input(name: str = "hello.txt", body: bytes = b"hello world") -> dict:
    return {
        "name": name,
        "content": base64.b64encode(body).decode("utf-8"),
        "contentType": "text/plain",
    }


class TestUploadFile:
    @pytest.mark.asyncio
    async def test_happy_path_returns_uploaded_metadata(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_FILE_ENTRY)

        result = await dropbox.execute_action(
            "upload_file",
            {"file": _file_input("report.pdf"), "path": "/"},
            mock_context,
        )

        assert result.result.data["file"] == SAMPLE_FILE_ENTRY

    @pytest.mark.asyncio
    async def test_request_uses_content_endpoint_with_decoded_bytes(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})
        body = b"unit-test body"

        await dropbox.execute_action(
            "upload_file",
            {
                "file": _file_input("notes.txt", body),
                "path": "/folder",
                "mode": "overwrite",
                "autorename": True,
                "mute": True,
            },
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.args[0] == f"{DROPBOX_CONTENT_BASE_URL}/files/upload"
        assert call.kwargs["method"] == "POST"
        # Decoded bytes are sent as the raw body
        assert call.kwargs["data"] == body
        headers = call.kwargs["headers"]
        assert headers["Content-Type"] == "application/octet-stream"
        api_arg = json.loads(headers["Dropbox-API-Arg"])
        assert api_arg["path"] == "/folder/notes.txt"
        assert api_arg["mode"] == "overwrite"
        assert api_arg["autorename"] is True
        assert api_arg["mute"] is True

    @pytest.mark.asyncio
    async def test_default_path_is_root(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await dropbox.execute_action("upload_file", {"file": _file_input("a.txt")}, mock_context)

        api_arg = json.loads(mock_context.fetch.call_args.kwargs["headers"]["Dropbox-API-Arg"])
        assert api_arg["path"] == "/a.txt"
        assert api_arg["mode"] == "add"

    @pytest.mark.asyncio
    async def test_trailing_slash_on_folder_is_normalized(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await dropbox.execute_action(
            "upload_file",
            {"file": _file_input("a.txt"), "path": "/folder/"},
            mock_context,
        )

        api_arg = json.loads(mock_context.fetch.call_args.kwargs["headers"]["Dropbox-API-Arg"])
        assert api_arg["path"] == "/folder/a.txt"

    @pytest.mark.asyncio
    async def test_path_without_leading_slash_is_normalized(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await dropbox.execute_action(
            "upload_file",
            {"file": _file_input("a.txt"), "path": "folder/sub"},
            mock_context,
        )

        api_arg = json.loads(mock_context.fetch.call_args.kwargs["headers"]["Dropbox-API-Arg"])
        assert api_arg["path"] == "/folder/sub/a.txt"

    @pytest.mark.asyncio
    async def test_legacy_full_path_is_not_double_appended(self, mock_context):
        # Backwards compat: pre-2.0 callers passed the full file path in `path`.
        # If the basename matches the file's name, treat it as the destination.
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        await dropbox.execute_action(
            "upload_file",
            {"file": _file_input("a.txt"), "path": "/folder/a.txt"},
            mock_context,
        )

        api_arg = json.loads(mock_context.fetch.call_args.kwargs["headers"]["Dropbox-API-Arg"])
        assert api_arg["path"] == "/folder/a.txt"

    @pytest.mark.asyncio
    async def test_zero_byte_file_uploads_successfully(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        # Empty bytes encodes to "" — a valid (empty) base64 string for a zero-byte file.
        result = await dropbox.execute_action(
            "upload_file",
            {"file": {"name": "empty.txt", "content": "", "contentType": "text/plain"}},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert mock_context.fetch.call_args.kwargs["data"] == b""

    @pytest.mark.asyncio
    async def test_invalid_base64_returns_action_error(self, mock_context):
        result = await dropbox.execute_action(
            "upload_file",
            {
                "file": {
                    "name": "bad.bin",
                    "content": "!!!not-base64!!!",
                    "contentType": "application/octet-stream",
                }
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "valid base64" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_content_is_caught_by_schema(self, mock_context):
        # The input schema marks `content` as required, so the SDK rejects this
        # before the handler runs. (The handler's own ActionError check is a
        # defence-in-depth fallback for direct handler invocation.)
        result = await dropbox.execute_action(
            "upload_file",
            {"file": {"name": "x.txt", "contentType": "text/plain"}},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_flat_input_shape_is_rejected_by_schema(self, mock_context):
        # The pre-fix shape (flat `content` + `path` as full file path, no `file` object)
        # must be caught by SDK schema validation before the handler runs.
        result = await dropbox.execute_action(
            "upload_file",
            {"content": base64.b64encode(b"x").decode("utf-8"), "path": "/a.txt"},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_name_returns_action_error(self, mock_context):
        result = await dropbox.execute_action(
            "upload_file",
            {
                "file": {
                    "name": "",
                    "content": base64.b64encode(b"x").decode("utf-8"),
                    "contentType": "text/plain",
                }
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "File name is required" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 401: Unauthorized")

        result = await dropbox.execute_action("upload_file", {"file": _file_input()}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "HTTP 401" in result.result.message


# ---- create_folder ----


class TestCreateFolder:
    @pytest.mark.asyncio
    async def test_returns_folder_metadata(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"metadata": SAMPLE_FOLDER_METADATA}
        )

        result = await dropbox.execute_action("create_folder", {"path": "/new_folder"}, mock_context)

        assert result.result.data["folder"] == SAMPLE_FOLDER_METADATA

    @pytest.mark.asyncio
    async def test_request_url_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"metadata": {}})

        await dropbox.execute_action("create_folder", {"path": "/new", "autorename": True}, mock_context)

        call = mock_context.fetch.call_args
        assert call.args[0] == f"{DROPBOX_API_BASE_URL}/files/create_folder_v2"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {"path": "/new", "autorename": True}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("path/conflict")

        result = await dropbox.execute_action("create_folder", {"path": "/exists"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "path/conflict" in result.result.message


# ---- delete ----


class TestDelete:
    @pytest.mark.asyncio
    async def test_returns_deleted_metadata(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"metadata": SAMPLE_FILE_ENTRY})

        result = await dropbox.execute_action("delete", {"path": "/report.pdf"}, mock_context)

        assert result.result.data["metadata"] == SAMPLE_FILE_ENTRY

    @pytest.mark.asyncio
    async def test_request_url_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"metadata": {}})

        await dropbox.execute_action("delete", {"path": "/x"}, mock_context)

        call = mock_context.fetch.call_args
        assert call.args[0] == f"{DROPBOX_API_BASE_URL}/files/delete_v2"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {"path": "/x"}

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("path/not_found")

        result = await dropbox.execute_action("delete", {"path": "/nope"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "path/not_found" in result.result.message


# ---- move ----


class TestMove:
    @pytest.mark.asyncio
    async def test_returns_moved_metadata(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"metadata": SAMPLE_FILE_ENTRY})

        result = await dropbox.execute_action("move", {"from_path": "/a.txt", "to_path": "/b.txt"}, mock_context)

        assert result.result.data["metadata"] == SAMPLE_FILE_ENTRY

    @pytest.mark.asyncio
    async def test_request_url_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"metadata": {}})

        await dropbox.execute_action(
            "move",
            {
                "from_path": "/a.txt",
                "to_path": "/folder/a.txt",
                "autorename": True,
                "allow_ownership_transfer": True,
            },
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.args[0] == f"{DROPBOX_API_BASE_URL}/files/move_v2"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {
            "from_path": "/a.txt",
            "to_path": "/folder/a.txt",
            "autorename": True,
            "allow_ownership_transfer": True,
        }

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("to/conflict")

        result = await dropbox.execute_action("move", {"from_path": "/a", "to_path": "/b"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "to/conflict" in result.result.message


# ---- copy ----


class TestCopy:
    @pytest.mark.asyncio
    async def test_returns_copied_metadata(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"metadata": SAMPLE_FILE_ENTRY})

        result = await dropbox.execute_action("copy", {"from_path": "/a.txt", "to_path": "/b.txt"}, mock_context)

        assert result.result.data["metadata"] == SAMPLE_FILE_ENTRY

    @pytest.mark.asyncio
    async def test_request_url_and_payload(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"metadata": {}})

        await dropbox.execute_action(
            "copy",
            {"from_path": "/a.txt", "to_path": "/b.txt", "autorename": True},
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert call.args[0] == f"{DROPBOX_API_BASE_URL}/files/copy_v2"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {
            "from_path": "/a.txt",
            "to_path": "/b.txt",
            "autorename": True,
        }

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("path/not_found")

        result = await dropbox.execute_action("copy", {"from_path": "/missing", "to_path": "/here"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "path/not_found" in result.result.message
