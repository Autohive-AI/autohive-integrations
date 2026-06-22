"""End-to-end integration tests for the Dropbox integration.

These tests call the real Dropbox API and require a valid OAuth access token
set in the DROPBOX_ACCESS_TOKEN environment variable (via .env or export).

Destructive tests (upload/create/delete/move/copy) are marked
``@pytest.mark.destructive``. They scope their writes to a unique folder under
``DROPBOX_TEST_FOLDER`` (default ``/autohive_integration_test``) and clean up
after themselves, but they still mutate real data in the connected Dropbox
account.

Run safely (read-only):
    pytest dropbox/tests/test_dropbox_integration.py -m "integration and not destructive"

Run destructive (mutates real data — use deliberately on a test account):
    pytest dropbox/tests/test_dropbox_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import base64
import os
import uuid

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError
from autohive_integrations_sdk.integration import ResultType

from dropbox import dropbox

pytestmark = pytest.mark.integration

TEST_FOLDER_ROOT = os.environ.get("DROPBOX_TEST_FOLDER", "/autohive_integration_test")


@pytest.fixture
def live_context(env_credentials, make_context):
    """Execution context wired to a real HTTP client with Dropbox OAuth token.

    The Dropbox integration relies on context.fetch to auto-inject the OAuth token
    (auth.type = "platform"). In tests we bypass the SDK auth layer and manually
    add the Authorization header to every request.
    """
    access_token = env_credentials("DROPBOX_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("DROPBOX_ACCESS_TOKEN not set — skipping integration tests")

    import aiohttp

    async def real_fetch(
        url,
        *,
        method="GET",
        json=None,
        headers=None,
        data=None,
        params=None,
        **kwargs,
    ):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {access_token}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=json, data=data, headers=merged_headers, params=params
            ) as resp:
                # Dropbox content endpoints may return JSON without a strict Content-Type;
                # fall back to text for non-JSON error bodies.
                try:
                    body = await resp.json(content_type=None)
                except Exception:
                    body = await resp.text()

                # Mimic ExecutionContext.fetch() error semantics so actions reach
                # their except blocks and return ActionError as they would in prod.
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise RateLimitError(retry_after, resp.status, str(body), body)
                if resp.status < 200 or resp.status >= 300:
                    raise HTTPError(resp.status, str(body), body)

                return FetchResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    data=body,
                )

    ctx = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_token},
        }
    )
    ctx.fetch.side_effect = real_fetch
    return ctx


def _file_input(name: str, body: bytes = b"hello from autohive integration test"):
    return {
        "name": name,
        "content": base64.b64encode(body).decode("utf-8"),
        "contentType": "text/plain",
    }


def _unique_folder():
    return f"{TEST_FOLDER_ROOT}/run_{uuid.uuid4().hex[:8]}"


async def _ensure_folder(path: str, live_context):
    """Idempotently create a Dropbox folder; tolerate path/conflict ('already exists')."""
    if not path or path == "/":
        return
    result = await dropbox.execute_action("create_folder", {"path": path}, live_context)
    if result.type == ResultType.ACTION:
        return
    # If it already exists as a folder, that's fine.
    meta = await dropbox.execute_action("get_metadata", {"path": path}, live_context)
    if meta.type == ResultType.ACTION and meta.result.data["metadata"].get(".tag") == "folder":
        return
    pytest.fail(f"Could not ensure Dropbox test folder exists: {path}: {result.result}")


# ---- Read-Only Tests ----


class TestListFolder:
    async def test_lists_root(self, live_context):
        result = await dropbox.execute_action("list_folder", {"path": ""}, live_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "entries" in data
        assert "has_more" in data
        assert isinstance(data["entries"], list)

    async def test_supports_limit(self, live_context):
        result = await dropbox.execute_action("list_folder", {"path": "", "limit": 1}, live_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["entries"]) <= 1

    async def test_nonexistent_path_returns_action_error(self, live_context):
        result = await dropbox.execute_action(
            "list_folder",
            {"path": f"/__autohive_does_not_exist_{uuid.uuid4().hex[:8]}"},
            live_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert result.result.message


# ---- Read-Only Tests: get_metadata ----


class TestGetMetadata:
    async def test_nonexistent_path_returns_action_error(self, live_context):
        result = await dropbox.execute_action(
            "get_metadata",
            {"path": f"/__autohive_does_not_exist_{uuid.uuid4().hex[:8]}"},
            live_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not_found" in result.result.message.lower() or "path" in result.result.message.lower()


class TestGetTemporaryLink:
    async def test_nonexistent_path_returns_action_error(self, live_context):
        result = await dropbox.execute_action(
            "get_temporary_link",
            {"path": f"/__autohive_missing_{uuid.uuid4().hex[:8]}.txt"},
            live_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not_found" in result.result.message.lower() or "path" in result.result.message.lower()


# ---- Destructive Tests (Write Operations) ----
# These create, update, or delete real data inside DROPBOX_TEST_FOLDER.
# Only run with: pytest -m "integration and destructive"


@pytest.mark.destructive
class TestUploadGetDelete:
    """upload_file → get_metadata → get_temporary_link → delete."""

    async def test_full_file_lifecycle(self, live_context):
        folder = _unique_folder()
        file_name = "hello.txt"
        file_path = f"{folder}/{file_name}"

        try:
            # Dropbox requires parent folders to exist before uploading into them.
            await _ensure_folder(TEST_FOLDER_ROOT, live_context)
            await _ensure_folder(folder, live_context)

            upload_result = await dropbox.execute_action(
                "upload_file",
                {
                    "file": _file_input(file_name),
                    "path": folder,
                    "mode": "overwrite",
                },
                live_context,
            )
            assert upload_result.type == ResultType.ACTION, upload_result.result
            uploaded = upload_result.result.data["file"]
            assert uploaded.get("name") == file_name
            assert uploaded.get("path_display", "").lower() == file_path.lower()

            # get_metadata
            meta_result = await dropbox.execute_action("get_metadata", {"path": file_path}, live_context)
            assert meta_result.type == ResultType.ACTION
            assert meta_result.result.data["metadata"].get(".tag") == "file"

            # get_temporary_link
            link_result = await dropbox.execute_action("get_temporary_link", {"path": file_path}, live_context)
            assert link_result.type == ResultType.ACTION
            assert link_result.result.data["link"].startswith("http")
        finally:
            # Cleanup: delete the whole run folder
            await dropbox.execute_action("delete", {"path": folder}, live_context)


@pytest.mark.destructive
class TestFolderLifecycle:
    """create_folder → upload_file → copy → move → delete (cleanup)."""

    async def test_create_copy_move_delete(self, live_context):
        folder = _unique_folder()
        sub_a = f"{folder}/a"
        sub_b = f"{folder}/b"
        file_name = "doc.txt"

        try:
            # The shared parent must exist before the run folder can be nested under it.
            await _ensure_folder(TEST_FOLDER_ROOT, live_context)

            # create_folder for the run root and both subfolders.
            root_result = await dropbox.execute_action("create_folder", {"path": folder}, live_context)
            assert root_result.type == ResultType.ACTION
            assert root_result.result.data["folder"].get("path_display", "").lower() == folder.lower()

            sub_a_result = await dropbox.execute_action("create_folder", {"path": sub_a}, live_context)
            assert sub_a_result.type == ResultType.ACTION
            sub_b_result = await dropbox.execute_action("create_folder", {"path": sub_b}, live_context)
            assert sub_b_result.type == ResultType.ACTION

            # Upload a file into sub_a
            upload_result = await dropbox.execute_action(
                "upload_file",
                {"file": _file_input(file_name), "path": sub_a, "mode": "overwrite"},
                live_context,
            )
            assert upload_result.type == ResultType.ACTION, upload_result.result

            # Copy the file into sub_b
            copy_result = await dropbox.execute_action(
                "copy",
                {"from_path": f"{sub_a}/{file_name}", "to_path": f"{sub_b}/{file_name}"},
                live_context,
            )
            assert copy_result.type == ResultType.ACTION
            assert copy_result.result.data["metadata"].get(".tag") == "file"

            # Move the original file
            moved_path = f"{sub_a}/renamed.txt"
            move_result = await dropbox.execute_action(
                "move",
                {"from_path": f"{sub_a}/{file_name}", "to_path": moved_path},
                live_context,
            )
            assert move_result.type == ResultType.ACTION
            assert move_result.result.data["metadata"].get("name") == "renamed.txt"
        finally:
            await dropbox.execute_action("delete", {"path": folder}, live_context)
