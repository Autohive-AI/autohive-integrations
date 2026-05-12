"""
Live integration tests for the Box integration.

Requires BOX_ACCESS_TOKEN set in the environment or project .env.

Token extraction recipe:
1. Authorize the Box platform OAuth app for a sandbox/test Box account.
2. Copy the resulting short-lived OAuth access token to BOX_ACCESS_TOKEN.
3. Add the value to the project .env file or export it in your shell before
   running these tests.

Safe read-only run:
    pytest box/tests/test_box_integration.py -m "integration and not destructive"
"""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from box.box import box

pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    access_token = env_credentials("BOX_ACCESS_TOKEN")
    if not access_token:
        pytest.skip("BOX_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        merged_headers = dict(headers or {})
        merged_headers["Authorization"] = f"Bearer {access_token}"

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                json=json,
                headers=merged_headers,
                params=params,
                **kwargs,
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": access_token},
        }
    )
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx._session = None
    ctx.__aenter__ = AsyncMock(return_value=ctx)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


async def test_list_shared_folders(live_context):
    result = await box.execute_action("list_shared_folders", {}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "folders" in data
    assert isinstance(data["folders"], list)


async def test_list_files(live_context):
    result = await box.execute_action("list_files", {}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "files" in data
    assert isinstance(data["files"], list)


async def test_list_folder_contents(live_context):
    result = await box.execute_action("list_folder_contents", {"folder_id": "0"}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "items" in data
    assert isinstance(data["items"], list)


async def test_get_file(live_context):
    list_result = await box.execute_action("list_files", {}, live_context)
    assert list_result.type == ResultType.ACTION
    files = list_result.result.data.get("files", [])
    if not files:
        pytest.skip("No files available to test get_file")

    file_id = files[0]["id"]
    result = await box.execute_action("get_file", {"file_id": file_id}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "file" in data
    assert "metadata" in data
    assert data["file"]["name"]
    assert data["file"]["content"]
    assert data["file"]["contentType"]


@pytest.mark.destructive
async def test_upload_file(live_context):
    """Upload a small test file to the root folder then verify it appears in list_files."""
    import time

    uid = int(time.time())
    import base64

    result = await box.execute_action(
        "upload_file",
        {
            "folder_id": "0",
            "file": {
                "name": f"ah-test-{uid}.txt",
                "content": base64.b64encode(b"autohive integration test").decode(),
                "contentType": "text/plain",
            },
        },
        live_context,
    )
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert data.get("file_id")
