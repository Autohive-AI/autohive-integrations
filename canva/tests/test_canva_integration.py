"""
End-to-end integration tests for the Canva integration.

These tests call the real Canva Connect API and require a valid OAuth access
token set in the CANVA_ACCESS_TOKEN environment variable (the token must carry
the scopes declared in config.json).

Run read-only tests:
    pytest canva/tests/test_canva_integration.py -m "integration and not destructive"

Run destructive tests (creates/updates/deletes real resources in the account):
    pytest canva/tests/test_canva_integration.py -m "integration and destructive"

Never runs in CI — the default pytest marker filter (-m unit) excludes these.
"""

import os
import sys

import aiohttp
import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import canva as canva_mod  # noqa: E402
from canva import CanvaConnectedAccountHandler  # noqa: E402

canva_integration = canva_mod.canva

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("CANVA_ACCESS_TOKEN", "")

# A tiny 1x1 red-pixel PNG for upload/asset lifecycle tests.
PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("CANVA_ACCESS_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", params=None, data=None, headers=None, json=None, **kwargs):
        request_headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", **(headers or {})}
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers=request_headers,
            ) as resp:
                try:
                    resp_data = await resp.json(content_type=None)
                except Exception:
                    resp_data = await resp.text()
                if resp.status >= 400:
                    raise Exception(f"Canva API error {resp.status}: {resp_data}")
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=resp_data)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"credentials": {"access_token": ACCESS_TOKEN}}
    return ctx


# =============================================================================
# CONNECTED ACCOUNT
# =============================================================================


class TestConnectedAccount:
    async def test_get_account_info(self, live_context):
        result = await CanvaConnectedAccountHandler().get_account_info(live_context)
        assert result.username is not None
        assert result.user_id is not None


# =============================================================================
# READ-ONLY ACTIONS
# =============================================================================


class TestGetUserCapabilities:
    async def test_returns_capabilities(self, live_context):
        result = await canva_integration.execute_action("get_user_capabilities", {}, live_context)
        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data["capabilities"], list)


class TestListDesigns:
    async def test_returns_designs_list(self, live_context):
        result = await canva_integration.execute_action("list_designs", {}, live_context)
        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data["designs"], list)

    async def test_sort_by_forwarded(self, live_context):
        result = await canva_integration.execute_action(
            "list_designs", {"sort_by": "modified_descending"}, live_context
        )
        assert result.type == ResultType.ACTION
        assert isinstance(result.result.data["designs"], list)

    async def test_get_existing_design(self, live_context):
        list_result = await canva_integration.execute_action("list_designs", {}, live_context)
        designs = list_result.result.data["designs"]
        if not designs:
            pytest.skip("No designs on this account")
        design_id = designs[0]["id"]
        result = await canva_integration.execute_action("get_design", {"design_id": design_id}, live_context)
        assert result.type == ResultType.ACTION
        assert result.result.data["design"]["id"] == design_id


# =============================================================================
# DESTRUCTIVE — design lifecycle (create → get → export → poll status)
# =============================================================================


@pytest.mark.destructive
class TestDesignLifecycle:
    async def test_create_get_export(self, live_context):
        create_result = await canva_integration.execute_action(
            "create_design",
            {"preset_type": "presentation", "title": "Integration Test Deck"},
            live_context,
        )
        assert create_result.type == ResultType.ACTION
        design_id = create_result.result.data["design"]["id"]
        assert design_id

        get_result = await canva_integration.execute_action("get_design", {"design_id": design_id}, live_context)
        assert get_result.result.data["design"]["id"] == design_id

        export_result = await canva_integration.execute_action(
            "export_design", {"design_id": design_id, "format": "pdf"}, live_context
        )
        assert export_result.type == ResultType.ACTION
        export_job_id = export_result.result.data.get("job_id")
        assert export_job_id

        status_result = await canva_integration.execute_action(
            "get_export_status", {"export_id": export_job_id}, live_context
        )
        assert status_result.type == ResultType.ACTION
        assert "status" in status_result.result.data


# =============================================================================
# DESTRUCTIVE — folder lifecycle (create → get → list → update → delete)
# =============================================================================


@pytest.mark.destructive
class TestFolderLifecycle:
    async def test_full_lifecycle(self, live_context):
        create_result = await canva_integration.execute_action(
            "create_folder", {"name": "Integration Test Folder"}, live_context
        )
        assert create_result.type == ResultType.ACTION
        folder_id = create_result.result.data["folder"]["id"]
        assert folder_id

        try:
            get_result = await canva_integration.execute_action("get_folder", {"folder_id": folder_id}, live_context)
            assert get_result.result.data["folder"]["id"] == folder_id

            list_result = await canva_integration.execute_action(
                "list_folder_items", {"folder_id": folder_id}, live_context
            )
            assert isinstance(list_result.result.data["items"], list)

            update_result = await canva_integration.execute_action(
                "update_folder", {"folder_id": folder_id, "name": "Integration Test Folder (renamed)"}, live_context
            )
            assert update_result.type == ResultType.ACTION
        finally:
            delete_result = await canva_integration.execute_action(
                "delete_folder", {"folder_id": folder_id}, live_context
            )
            assert delete_result.type == ResultType.ACTION


# =============================================================================
# DESTRUCTIVE — asset lifecycle (upload → poll → get → update → delete)
# =============================================================================


@pytest.mark.destructive
class TestAssetLifecycle:
    async def test_full_lifecycle(self, live_context):
        import asyncio

        upload_result = await canva_integration.execute_action(
            "upload_asset",
            {"file": {"content": PNG_B64, "name": "integration_test.png", "contentType": "image/png"}},
            live_context,
        )
        assert upload_result.type == ResultType.ACTION
        job_id = upload_result.result.data.get("job_id")
        assert job_id

        # Poll until the upload job completes (asset_id appears on success).
        asset_id = None
        for _ in range(10):
            status_result = await canva_integration.execute_action(
                "get_asset_upload_status", {"job_id": job_id}, live_context
            )
            assert status_result.type == ResultType.ACTION
            asset = status_result.result.data.get("asset")
            if asset and asset.get("id"):
                asset_id = asset["id"]
                break
            await asyncio.sleep(2)

        if not asset_id:
            pytest.skip("Asset upload did not finish in time")

        try:
            get_result = await canva_integration.execute_action("get_asset", {"asset_id": asset_id}, live_context)
            assert get_result.result.data["asset"]["id"] == asset_id

            update_result = await canva_integration.execute_action(
                "update_asset", {"asset_id": asset_id, "tags": ["integration-test"]}, live_context
            )
            assert update_result.type == ResultType.ACTION
        finally:
            delete_result = await canva_integration.execute_action(
                "delete_asset", {"asset_id": asset_id}, live_context
            )
            assert delete_result.type == ResultType.ACTION
