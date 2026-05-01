import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(_parent)
sys.path.insert(0, _parent)
_spec = importlib.util.spec_from_file_location("box_mod", os.path.join(_parent, "box.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
box = _mod.box

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse, ResultType  # noqa: E402

pytestmark = pytest.mark.integration
ACCESS_TOKEN = os.environ.get("BOX_ACCESS_TOKEN", "")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("BOX_ACCESS_TOKEN not set")
    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers or {}, params=params) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.text()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = MagicMock()
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


@pytest.mark.asyncio
async def test_list_shared_folders(live_context):
    result = await box.execute_action("list_shared_folders", {}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "folders" in data
    assert isinstance(data["folders"], list)


@pytest.mark.asyncio
async def test_list_files(live_context):
    result = await box.execute_action("list_files", {}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "files" in data
    assert isinstance(data["files"], list)


@pytest.mark.asyncio
async def test_list_folder_contents(live_context):
    result = await box.execute_action("list_folder_contents", {"folder_id": "0"}, live_context)
    assert result.type == ResultType.ACTION
    data = result.result.data
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_get_file(live_context):
    # First find a file to test with
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
