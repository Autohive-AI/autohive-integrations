"""
Box integration tests.

Usage:
    python test_box.py <access_token>
    BOX_TOKEN=<token> python test_box.py

Tests cover all 5 actions:
  - list_shared_folders  (basic, pagination)
  - list_files           (no filter, query, extension filter, folder_id, pagination)
  - list_folder_contents (root, specific folder, recursive, pagination)
  - get_file             (metadata + base64 content, invalid id)
  - upload_file          (upload text file, then verify via get_file)

Set BOX_TEST_FOLDER_ID to run folder-scoped tests against a specific folder (default: "0" = root).
Set BOX_TEST_FILE_ID to run get_file against a known existing file.
"""

import asyncio
import base64
import os
import sys

from context import box  # noqa: F401
from autohive_integrations_sdk import ExecutionContext, IntegrationResult

# ---------------------------------------------------------------------------
# Auth / config
# ---------------------------------------------------------------------------
TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.getenv("BOX_TOKEN", "")
TEST_FOLDER_ID = os.getenv("BOX_TEST_FOLDER_ID", "0")   # "0" = root folder
TEST_FILE_ID = os.getenv("BOX_TEST_FILE_ID", "")

TEST_AUTH = {"credentials": {"access_token": TOKEN}}

# Set by upload test, used by get_file test
_uploaded_file_id: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ok(label: str, data: dict) -> None:
    print(f"  [OK] {label}")


def assert_result(data: dict, label: str) -> None:
    assert data.get("result") is True, (
        f"{label} failed: result=False, error={data.get('error')}"
    )


# ---------------------------------------------------------------------------
# list_shared_folders
# ---------------------------------------------------------------------------
async def test_list_shared_folders_basic():
    """List root folders with no params."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action("list_shared_folders", {}, ctx)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "list_shared_folders basic")
        assert isinstance(data.get("folders"), list)
        print(f"  folders returned: {len(data['folders'])}")
        if data["folders"]:
            folder = data["folders"][0]
            assert "id" in folder
            assert "name" in folder
            assert "type" in folder
            print(f"  first folder: id={folder['id']} name={folder['name']}")
    ok("list_shared_folders_basic", data)


async def test_list_shared_folders_pagination():
    """List with pageSize=2 and follow nextPageToken if present."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action("list_shared_folders", {"pageSize": 2}, ctx)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "list_shared_folders page1")
        assert len(data.get("folders", [])) <= 2
        print(f"  page 1: {len(data['folders'])} folders")

        if data.get("nextPageToken"):
            result2 = await box.execute_action(
                "list_shared_folders",
                {"pageSize": 2, "pageToken": data["nextPageToken"]},
                ctx,
            )
            data2 = result2.result.data
            assert_result(data2, "list_shared_folders page2")
            print(f"  page 2: {len(data2['folders'])} folders")
        else:
            print("  no nextPageToken (all folders fit in one page)")
    ok("list_shared_folders_pagination", data)


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------
async def test_list_files_no_filter():
    """List files from root with no filter."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action("list_files", {}, ctx)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "list_files no filter")
        assert isinstance(data.get("files"), list)
        print(f"  files returned: {len(data['files'])}")
        if data["files"]:
            f = data["files"][0]
            assert "id" in f
            assert "name" in f
            print(f"  first file: id={f['id']} name={f['name']} size={f.get('size')}")
    ok("list_files_no_filter", data)


async def test_list_files_with_query():
    """List files filtered by search query."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action("list_files", {"query": "test"}, ctx)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "list_files with query")
        assert isinstance(data.get("files"), list)
        print(f"  files matching 'test': {len(data['files'])}")
    ok("list_files_with_query", data)


async def test_list_files_with_extension_filter():
    """List files filtered by extension."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action(
            "list_files", {"file_extensions": ["pdf", "txt"]}, ctx
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "list_files with extension filter")
        assert isinstance(data.get("files"), list)
        print(f"  pdf/txt files: {len(data['files'])}")
    ok("list_files_with_extension_filter", data)


async def test_list_files_with_folder_id():
    """List files scoped to a specific folder."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action(
            "list_files", {"folder_id": TEST_FOLDER_ID}, ctx
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, f"list_files folder_id={TEST_FOLDER_ID}")
        assert isinstance(data.get("files"), list)
        print(f"  files in folder {TEST_FOLDER_ID}: {len(data['files'])}")
    ok("list_files_with_folder_id", data)


async def test_list_files_pagination():
    """List files with pageSize=2."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action("list_files", {"pageSize": 2}, ctx)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "list_files pagination")
        assert len(data.get("files", [])) <= 2
        print(f"  pageSize=2 returned: {len(data['files'])} files")
    ok("list_files_pagination", data)


# ---------------------------------------------------------------------------
# list_folder_contents
# ---------------------------------------------------------------------------
async def test_list_folder_contents_root():
    """List contents of the root folder (id '0')."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action(
            "list_folder_contents", {"folder_id": "0"}, ctx
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "list_folder_contents root")
        assert isinstance(data.get("items"), list)
        print(f"  root items: {len(data['items'])}")
        if data["items"]:
            item = data["items"][0]
            assert "id" in item
            assert "name" in item
            assert "type" in item
            print(f"  first item: id={item['id']} name={item['name']} type={item['type']}")
    ok("list_folder_contents_root", data)


async def test_list_folder_contents_specific():
    """List contents of TEST_FOLDER_ID."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action(
            "list_folder_contents", {"folder_id": TEST_FOLDER_ID}, ctx
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, f"list_folder_contents folder={TEST_FOLDER_ID}")
        assert isinstance(data.get("items"), list)
        print(f"  items in folder {TEST_FOLDER_ID}: {len(data['items'])}")
    ok("list_folder_contents_specific", data)


async def test_list_folder_contents_recursive():
    """List contents recursively."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action(
            "list_folder_contents",
            {"folder_id": TEST_FOLDER_ID, "recursive": True},
            ctx,
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "list_folder_contents recursive")
        assert isinstance(data.get("items"), list)
        print(f"  recursive items: {len(data['items'])}")
    ok("list_folder_contents_recursive", data)


async def test_list_folder_contents_pagination():
    """List folder contents with pageSize=3."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action(
            "list_folder_contents",
            {"folder_id": "0", "pageSize": 3},
            ctx,
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "list_folder_contents pageSize=3")
        assert len(data.get("items", [])) <= 3
        print(f"  pageSize=3 returned: {len(data['items'])} items")
    ok("list_folder_contents_pagination", data)


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------
async def test_upload_file_text():
    """Upload a small text file to the test folder."""
    global _uploaded_file_id

    content = "Hello from Autohive Box integration test.\n"
    encoded = base64.b64encode(content.encode()).decode()
    file_obj = {
        "name": "autohive_test_upload.txt",
        "content": encoded,
        "contentType": "text/plain",
    }

    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action(
            "upload_file",
            {"file": file_obj, "folder_id": TEST_FOLDER_ID},
            ctx,
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "upload_file text")
        assert data.get("file_name") == "autohive_test_upload.txt" or data.get("file_id")
        print(
            f"  uploaded: file_id={data.get('file_id')} "
            f"name={data.get('file_name')} size={data.get('file_size')}"
        )
        if data.get("file_id"):
            _uploaded_file_id = data["file_id"]
    ok("upload_file_text", data)


async def test_upload_file_to_root():
    """Upload a file explicitly to root folder."""
    content = "Root upload test from Autohive.\n"
    encoded = base64.b64encode(content.encode()).decode()
    file_obj = {
        "name": "autohive_root_test.txt",
        "content": encoded,
        "contentType": "text/plain",
    }

    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action(
            "upload_file",
            {"file": file_obj, "folder_id": "0"},
            ctx,
        )
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "upload_file to root")
        print(f"  uploaded to root: file_id={data.get('file_id')}")
    ok("upload_file_to_root", data)


async def test_upload_file_default_folder():
    """Upload a file without specifying folder_id (defaults to root)."""
    content = "Default folder upload test.\n"
    encoded = base64.b64encode(content.encode()).decode()
    file_obj = {
        "name": "autohive_default_folder_test.txt",
        "content": encoded,
        "contentType": "text/plain",
    }

    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action("upload_file", {"file": file_obj}, ctx)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, "upload_file default folder")
        print(f"  uploaded to default folder: file_id={data.get('file_id')}")
    ok("upload_file_default_folder", data)


# ---------------------------------------------------------------------------
# get_file
# ---------------------------------------------------------------------------
async def test_get_file():
    """Download and decode a file — uses uploaded file if available, else TEST_FILE_ID."""
    file_id = _uploaded_file_id or TEST_FILE_ID
    if not file_id:
        print("  [SKIP] no file_id — upload may have failed or BOX_TEST_FILE_ID not set")
        return

    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action("get_file", {"file_id": file_id}, ctx)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert_result(data, f"get_file id={file_id}")

        file_out = data.get("file", {})
        assert file_out.get("name"), "file.name should be present"
        assert file_out.get("content"), "file.content (base64) should be present"
        assert file_out.get("contentType"), "file.contentType should be present"

        # Verify content is valid base64 and decodes without error
        decoded = base64.b64decode(file_out["content"])
        print(
            f"  name={file_out['name']} "
            f"contentType={file_out['contentType']} "
            f"decoded_size={len(decoded)} bytes"
        )

        metadata = data.get("metadata", {})
        assert metadata.get("id") == file_id
        print(
            f"  metadata: id={metadata.get('id')} "
            f"mimeType={metadata.get('mimeType')} "
            f"created={metadata.get('createdTime')}"
        )
    ok("get_file", data)


async def test_get_file_invalid_id():
    """get_file with a bogus ID should return result=False gracefully."""
    async with ExecutionContext(auth=TEST_AUTH) as ctx:
        result = await box.execute_action("get_file", {"file_id": "000000000000"}, ctx)
        assert isinstance(result, IntegrationResult)
        data = result.result.data
        assert data.get("result") is False, "Expected result=False for invalid file_id"
        assert data.get("error"), "Expected an error message"
        print(f"  expected failure: error={data['error']}")
    ok("get_file_invalid_id (expected failure)", data)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
ALL_TESTS = [
    test_list_shared_folders_basic,
    test_list_shared_folders_pagination,
    test_list_files_no_filter,
    test_list_files_with_query,
    test_list_files_with_extension_filter,
    test_list_files_with_folder_id,
    test_list_files_pagination,
    test_list_folder_contents_root,
    test_list_folder_contents_specific,
    test_list_folder_contents_recursive,
    test_list_folder_contents_pagination,
    test_upload_file_text,          # must run before test_get_file
    test_upload_file_to_root,
    test_upload_file_default_folder,
    test_get_file,
    test_get_file_invalid_id,
]


async def main():
    if not TOKEN:
        print("ERROR: No access token. Pass as argv[1] or set BOX_TOKEN env var.")
        sys.exit(1)

    print(f"Running {len(ALL_TESTS)} Box integration tests...\n")
    passed = 0
    failed = 0

    for test_fn in ALL_TESTS:
        name = test_fn.__name__
        print(f"-> {name}")
        try:
            await test_fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1
        print()

    print(f"Results: {passed} passed, {failed} failed out of {len(ALL_TESTS)} tests")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
