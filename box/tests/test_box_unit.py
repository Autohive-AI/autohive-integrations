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

_spec = importlib.util.spec_from_file_location("box_mod", os.path.join(_parent, "box.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

box = _mod.box  # the Integration instance

pytestmark = pytest.mark.unit

# ---- Sample data ----

SAMPLE_FOLDER = {
    "id": "folder-1",
    "name": "My Folder",
    "type": "folder",
    "description": "A test folder",
    "created_at": "2024-01-01T00:00:00Z",
    "modified_at": "2024-06-01T00:00:00Z",
}

SAMPLE_FILE = {
    "id": "file-1",
    "name": "document.pdf",
    "type": "file",
    "size": 1024,
    "modified_at": "2024-06-01T00:00:00Z",
    "created_at": "2024-01-01T00:00:00Z",
}

SAMPLE_FILE_METADATA = {
    "id": "file-1",
    "name": "document.pdf",
    "size": 1024,
    "content_type": "application/pdf",
    "created_at": "2024-01-01T00:00:00Z",
    "modified_at": "2024-06-01T00:00:00Z",
    "parent": {"id": "0"},
}


# ---- Fixture ----


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


# ---- list_shared_folders ----


class TestListSharedFolders:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"entries": [SAMPLE_FOLDER], "total_count": 1},
        )

        result = await box.execute_action("list_shared_folders", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["folders"][0]["id"] == "folder-1"
        assert result.result.data["folders"][0]["name"] == "My Folder"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entries": [], "total_count": 0})

        await box.execute_action("list_shared_folders", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "https://api.box.com/2.0/folders/0/items" in call_args.args[0]
        assert call_args.kwargs.get("method") == "GET"

    @pytest.mark.asyncio
    async def test_filters_non_folders(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={
                "entries": [SAMPLE_FOLDER, {**SAMPLE_FILE, "type": "file"}],
                "total_count": 2,
            },
        )

        result = await box.execute_action("list_shared_folders", {}, mock_context)

        # Only folder-type entries should appear
        assert len(result.result.data["folders"]) == 1
        assert result.result.data["folders"][0]["type"] == "folder"

    @pytest.mark.asyncio
    async def test_pagination_token_included_when_more_pages(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"entries": [SAMPLE_FOLDER, SAMPLE_FOLDER], "total_count": 10},
        )

        result = await box.execute_action("list_shared_folders", {"pageSize": 2}, mock_context)

        assert "nextPageToken" in result.result.data
        assert result.result.data["nextPageToken"] == "2"

    @pytest.mark.asyncio
    async def test_no_pagination_token_when_all_fit(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"entries": [SAMPLE_FOLDER], "total_count": 1},
        )

        result = await box.execute_action("list_shared_folders", {"pageSize": 100}, mock_context)

        assert "nextPageToken" not in result.result.data

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await box.execute_action("list_shared_folders", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message

    @pytest.mark.asyncio
    async def test_empty_folder_list(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entries": [], "total_count": 0})

        result = await box.execute_action("list_shared_folders", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["folders"] == []


# ---- list_files ----


class TestListFiles:
    @pytest.mark.asyncio
    async def test_happy_path_no_filter(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entries": [SAMPLE_FILE]})

        result = await box.execute_action("list_files", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["files"]) == 1
        assert result.result.data["files"][0]["id"] == "file-1"

    @pytest.mark.asyncio
    async def test_no_filter_uses_root_folder_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entries": []})

        await box.execute_action("list_files", {}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "folders/0/items" in url

    @pytest.mark.asyncio
    async def test_query_uses_search_api(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entries": []})

        await box.execute_action("list_files", {"query": "report"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "/search" in url

    @pytest.mark.asyncio
    async def test_file_extensions_included_in_query(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entries": []})

        await box.execute_action("list_files", {"file_extensions": ["pdf", "docx"]}, mock_context)

        params = mock_context.fetch.call_args.kwargs.get("params", {})
        assert "pdf" in params.get("query", "")
        assert "docx" in params.get("query", "")

    @pytest.mark.asyncio
    async def test_filters_non_file_entries(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"entries": [SAMPLE_FILE, SAMPLE_FOLDER]},
        )

        result = await box.execute_action("list_files", {}, mock_context)

        # Only file-type entries should appear
        assert len(result.result.data["files"]) == 1
        assert result.result.data["files"][0]["type"] == "file"

    @pytest.mark.asyncio
    async def test_next_page_token_included(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"entries": [SAMPLE_FILE], "next_marker": "marker-abc"},
        )

        result = await box.execute_action("list_files", {}, mock_context)

        assert result.result.data["nextPageToken"] == "marker-abc"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await box.execute_action("list_files", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Timeout" in result.result.message

    @pytest.mark.asyncio
    async def test_response_shape(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entries": [SAMPLE_FILE]})

        result = await box.execute_action("list_files", {}, mock_context)

        file_entry = result.result.data["files"][0]
        assert "id" in file_entry
        assert "name" in file_entry
        assert "type" in file_entry
        assert "size" in file_entry


# ---- list_folder_contents ----


class TestListFolderContents:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"entries": [SAMPLE_FILE, SAMPLE_FOLDER]},
        )

        result = await box.execute_action("list_folder_contents", {"folder_id": "folder-1"}, mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["items"]) == 2

    @pytest.mark.asyncio
    async def test_request_url_contains_folder_id(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entries": []})

        await box.execute_action("list_folder_contents", {"folder_id": "folder-42"}, mock_context)

        url = mock_context.fetch.call_args.args[0]
        assert "folder-42" in url

    @pytest.mark.asyncio
    async def test_file_size_included_for_files(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entries": [SAMPLE_FILE]})

        result = await box.execute_action("list_folder_contents", {"folder_id": "0"}, mock_context)

        assert "size" in result.result.data["items"][0]

    @pytest.mark.asyncio
    async def test_folder_size_not_included(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entries": [SAMPLE_FOLDER]})

        result = await box.execute_action("list_folder_contents", {"folder_id": "0"}, mock_context)

        assert "size" not in result.result.data["items"][0]

    @pytest.mark.asyncio
    async def test_recursive_fetches_subfolder(self, mock_context):
        sub_file = {**SAMPLE_FILE, "id": "sub-file-1", "name": "sub_doc.pdf"}
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"entries": [SAMPLE_FOLDER]}),
            FetchResponse(status=200, headers={}, data={"entries": [sub_file]}),
        ]

        result = await box.execute_action("list_folder_contents", {"folder_id": "0", "recursive": True}, mock_context)

        assert result.type == ResultType.ACTION
        # Should have parent folder + sub file prefixed with folder name
        names = [i["name"] for i in result.result.data["items"]]
        assert any("sub_doc.pdf" in n for n in names)

    @pytest.mark.asyncio
    async def test_recursive_subfolder_error_is_skipped(self, mock_context):
        mock_context.fetch.side_effect = [
            FetchResponse(status=200, headers={}, data={"entries": [SAMPLE_FOLDER]}),
            Exception("Permission denied"),
        ]

        result = await box.execute_action("list_folder_contents", {"folder_id": "0", "recursive": True}, mock_context)

        # Should succeed — subfolders that error are skipped
        assert result.type == ResultType.ACTION
        assert len(result.result.data["items"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await box.execute_action("list_folder_contents", {"folder_id": "0"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Server error" in result.result.message

    @pytest.mark.asyncio
    async def test_next_page_token(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data={"entries": [SAMPLE_FILE], "next_marker": "marker-xyz"},
        )

        result = await box.execute_action("list_folder_contents", {"folder_id": "0"}, mock_context)

        assert result.result.data["nextPageToken"] == "marker-xyz"


# ---- get_file ----


class TestGetFile:
    @pytest.mark.asyncio
    async def test_metadata_request_url(self, mock_context):
        """Verify metadata fetch hits the correct URL."""
        # We only test the metadata fetch — the binary download uses aiohttp directly
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_FILE_METADATA)

        # Patch the aiohttp part to avoid real network call
        from unittest.mock import AsyncMock as AM

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AM(return_value=b"PDF content")
        mock_response.__aenter__ = AM(return_value=mock_response)
        mock_response.__aexit__ = AM(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        mock_context._session = mock_session
        mock_context.__aenter__ = AM(return_value=mock_context)
        mock_context.__aexit__ = AM(return_value=None)

        await box.execute_action("get_file", {"file_id": "file-1"}, mock_context)

        # Check metadata URL was fetched
        url = mock_context.fetch.call_args.args[0]
        assert "files/file-1" in url

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection refused")

        result = await box.execute_action("get_file", {"file_id": "file-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message

    @pytest.mark.asyncio
    async def test_happy_path_response_shape(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_FILE_METADATA)

        from unittest.mock import AsyncMock as AM

        file_bytes = b"Hello, Box!"
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AM(return_value=file_bytes)
        mock_response.__aenter__ = AM(return_value=mock_response)
        mock_response.__aexit__ = AM(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        mock_context._session = mock_session
        mock_context.__aenter__ = AM(return_value=mock_context)
        mock_context.__aexit__ = AM(return_value=None)

        result = await box.execute_action("get_file", {"file_id": "file-1"}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "file" in data
        assert "metadata" in data
        assert data["file"]["name"] == "document.pdf"
        assert data["file"]["contentType"] == "application/pdf"
        # Verify content is valid base64
        decoded = base64.b64decode(data["file"]["content"])
        assert decoded == file_bytes

    @pytest.mark.asyncio
    async def test_binary_content_error_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_FILE_METADATA)

        from unittest.mock import AsyncMock as AM

        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.text = AM(return_value="Not Found")
        mock_response.__aenter__ = AM(return_value=mock_response)
        mock_response.__aexit__ = AM(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        mock_context._session = mock_session
        mock_context.__aenter__ = AM(return_value=mock_context)
        mock_context.__aexit__ = AM(return_value=None)

        result = await box.execute_action("get_file", {"file_id": "file-1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "404" in result.result.message


# ---- upload_file ----


class TestUploadFile:
    def _make_file_obj(self, name="test.txt", content=b"hello", content_type="text/plain"):
        return {
            "name": name,
            "content": base64.b64encode(content).decode(),
            "contentType": content_type,
        }

    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        from unittest.mock import AsyncMock as AM

        upload_response = {"entries": [{"id": "new-file-99", "name": "test.txt", "size": 5}]}
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.json = AM(return_value=upload_response)
        mock_response.__aenter__ = AM(return_value=mock_response)
        mock_response.__aexit__ = AM(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        mock_context._session = mock_session
        mock_context.__aenter__ = AM(return_value=mock_context)
        mock_context.__aexit__ = AM(return_value=None)

        result = await box.execute_action(
            "upload_file",
            {"file": self._make_file_obj()},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["file_id"] == "new-file-99"
        assert result.result.data["file_name"] == "test.txt"

    @pytest.mark.asyncio
    async def test_upload_error_returns_action_error(self, mock_context):
        from unittest.mock import AsyncMock as AM

        mock_response = MagicMock()
        mock_response.status = 409
        mock_response.text = AM(return_value="Conflict")
        mock_response.__aenter__ = AM(return_value=mock_response)
        mock_response.__aexit__ = AM(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        mock_context._session = mock_session
        mock_context.__aenter__ = AM(return_value=mock_context)
        mock_context.__aexit__ = AM(return_value=None)

        result = await box.execute_action(
            "upload_file",
            {"file": self._make_file_obj()},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "409" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        from unittest.mock import AsyncMock as AM

        mock_context.__aenter__ = AM(return_value=mock_context)
        mock_context.__aexit__ = AM(return_value=None)
        mock_context._session = None

        # Patch aiohttp.ClientSession to raise
        class BrokenSession:
            def __init__(self):
                raise Exception("Cannot connect")

        import unittest.mock as um

        with um.patch("aiohttp.ClientSession", BrokenSession):
            result = await box.execute_action(
                "upload_file",
                {"file": self._make_file_obj()},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_upload_uses_upload_base_url(self, mock_context):
        from unittest.mock import AsyncMock as AM

        upload_response = {"entries": [{"id": "x", "name": "test.txt", "size": 5}]}
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.json = AM(return_value=upload_response)
        mock_response.__aenter__ = AM(return_value=mock_response)
        mock_response.__aexit__ = AM(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        mock_context._session = mock_session
        mock_context.__aenter__ = AM(return_value=mock_context)
        mock_context.__aexit__ = AM(return_value=None)

        await box.execute_action("upload_file", {"file": self._make_file_obj()}, mock_context)

        call_url = mock_session.post.call_args.args[0]
        assert "upload.box.com" in call_url

    @pytest.mark.asyncio
    async def test_empty_entries_still_succeeds(self, mock_context):
        """Upload that returns no entries still succeeds (success with partial data)."""
        from unittest.mock import AsyncMock as AM

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AM(return_value={"entries": []})
        mock_response.__aenter__ = AM(return_value=mock_response)
        mock_response.__aexit__ = AM(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        mock_context._session = mock_session
        mock_context.__aenter__ = AM(return_value=mock_context)
        mock_context.__aexit__ = AM(return_value=None)

        result = await box.execute_action(
            "upload_file",
            {"file": self._make_file_obj()},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["file_name"] == "test.txt"
