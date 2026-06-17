"""
Unit tests for the Canva integration using mocked fetch.

Pure unit tests — no credentials, no network. Safe for CI (default ``-m unit``).
Every ``context.fetch`` is mocked to return a ``FetchResponse`` (SDK 2.0.0),
and error paths are asserted to return ``ActionError`` (ResultType.ACTION_ERROR).
"""

import base64
import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import canva as canva_mod  # noqa: E402
from canva import CanvaConnectedAccountHandler  # noqa: E402

canva_integration = canva_mod.canva

pytestmark = pytest.mark.unit


# =============================================================================
# Helpers
# =============================================================================


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def make_ctx(response_data):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data))
    ctx.auth = {}
    return ctx


def make_ctx_multi(responses):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=[ok(r) for r in responses])
    ctx.auth = {}
    return ctx


def make_failing_ctx(exc=None):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=exc or Exception("API exploded"))
    ctx.auth = {}
    return ctx


def fetch_kwargs(ctx, call_index=-1):
    return ctx.fetch.call_args_list[call_index].kwargs


def fetch_url(ctx, call_index=-1):
    call = ctx.fetch.call_args_list[call_index]
    return call.args[0] if call.args else call.kwargs.get("url", "")


# A 1x1 red-pixel PNG, base64-encoded — valid input for upload/import actions.
PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="


# =============================================================================
# CONNECTED ACCOUNT HANDLER
# =============================================================================


@pytest.mark.asyncio
async def test_connected_account_full_name():
    ctx = make_ctx_multi(
        [
            {"profile": {"display_name": "Jane Doe"}},
            {"team_user": {"user_id": "u-123", "team_id": "t-456"}},
        ]
    )
    result = await CanvaConnectedAccountHandler().get_account_info(ctx)
    assert result.username == "Jane Doe"
    assert result.first_name == "Jane"
    assert result.last_name == "Doe"
    assert result.user_id == "u-123"
    assert result.organization == "t-456"


@pytest.mark.asyncio
async def test_connected_account_single_name():
    ctx = make_ctx_multi(
        [
            {"profile": {"display_name": "Cher"}},
            {"team_user": {"user_id": "u-1", "team_id": "t-1"}},
        ]
    )
    result = await CanvaConnectedAccountHandler().get_account_info(ctx)
    assert result.first_name == "Cher"
    assert result.last_name is None


@pytest.mark.asyncio
async def test_connected_account_multi_word_last_name():
    ctx = make_ctx_multi(
        [
            {"profile": {"display_name": "Jane Van Der Berg"}},
            {"team_user": {"user_id": "u", "team_id": "t"}},
        ]
    )
    result = await CanvaConnectedAccountHandler().get_account_info(ctx)
    assert result.first_name == "Jane"
    assert result.last_name == "Van Der Berg"


@pytest.mark.asyncio
async def test_connected_account_no_name_or_team():
    ctx = make_ctx_multi([{"profile": {}}, {}])
    result = await CanvaConnectedAccountHandler().get_account_info(ctx)
    assert result.username is None
    assert result.first_name is None
    assert result.last_name is None
    assert result.user_id is None
    assert result.organization is None


# =============================================================================
# GET USER CAPABILITIES
# =============================================================================


@pytest.mark.asyncio
async def test_get_user_capabilities_success():
    ctx = make_ctx({"capabilities": ["design:content:write", "folder:write"]})
    result = await canva_integration.execute_action("get_user_capabilities", {}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["capabilities"] == ["design:content:write", "folder:write"]
    assert "/v1/users/me/capabilities" in fetch_url(ctx)


@pytest.mark.asyncio
async def test_get_user_capabilities_missing_key_defaults_empty():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("get_user_capabilities", {}, ctx)
    assert result.result.data["capabilities"] == []


@pytest.mark.asyncio
async def test_get_user_capabilities_error_returns_action_error():
    ctx = make_failing_ctx(Exception("Unauthorized"))
    result = await canva_integration.execute_action("get_user_capabilities", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Unauthorized" in result.result.message


# =============================================================================
# UPLOAD ASSET
# =============================================================================


@pytest.mark.asyncio
async def test_upload_asset_success():
    ctx = make_ctx({"job": {"id": "job-1", "status": "in_progress"}})
    result = await canva_integration.execute_action(
        "upload_asset",
        {"file": {"content": PNG_B64, "name": "pic.png", "contentType": "image/png"}},
        ctx,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["job_id"] == "job-1"
    assert result.result.data["status"] == "in_progress"
    assert "/v1/asset-uploads" in fetch_url(ctx)
    assert fetch_kwargs(ctx)["method"] == "POST"
    # Binary payload is decoded base64
    assert fetch_kwargs(ctx)["data"] == base64.b64decode(PNG_B64)


@pytest.mark.asyncio
async def test_upload_asset_uses_files_array_fallback():
    ctx = make_ctx({"job": {"id": "job-2"}})
    result = await canva_integration.execute_action(
        "upload_asset",
        {"files": [{"content": PNG_B64, "name": "a.png", "contentType": "image/png"}]},
        ctx,
    )
    assert result.result.data["job_id"] == "job-2"


@pytest.mark.asyncio
async def test_upload_asset_name_base64_in_header():
    ctx = make_ctx({"job": {"id": "j"}})
    await canva_integration.execute_action(
        "upload_asset",
        {"file": {"content": PNG_B64, "name": "photo.png", "contentType": "image/png"}},
        ctx,
    )
    header = fetch_kwargs(ctx)["headers"]["Asset-Upload-Metadata"]
    expected = base64.b64encode("photo.png".encode("utf-8")).decode("utf-8")
    assert expected in header


@pytest.mark.asyncio
async def test_upload_asset_no_file_returns_action_error():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("upload_asset", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "No file provided" in result.result.message
    ctx.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_upload_asset_empty_content_returns_action_error():
    ctx = make_ctx({})
    result = await canva_integration.execute_action(
        "upload_asset",
        {"file": {"content": "", "name": "x.png", "contentType": "image/png"}},
        ctx,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "File content is empty" in result.result.message


# =============================================================================
# GET ASSET UPLOAD STATUS
# =============================================================================


@pytest.mark.asyncio
async def test_get_asset_upload_status_success():
    ctx = make_ctx({"job": {"status": "success", "asset": {"id": "asset-9", "name": "pic"}}})
    result = await canva_integration.execute_action("get_asset_upload_status", {"job_id": "job-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data["status"] == "success"
    assert result.result.data["asset"]["id"] == "asset-9"
    assert "/v1/asset-uploads/job-1" in fetch_url(ctx)


@pytest.mark.asyncio
async def test_get_asset_upload_status_in_progress_no_asset():
    ctx = make_ctx({"job": {"status": "in_progress"}})
    result = await canva_integration.execute_action("get_asset_upload_status", {"job_id": "j"}, ctx)
    assert result.result.data["status"] == "in_progress"
    assert "asset" not in result.result.data


@pytest.mark.asyncio
async def test_get_asset_upload_status_missing_job_id_validation_error():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("get_asset_upload_status", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# GET / UPDATE / DELETE ASSET
# =============================================================================


@pytest.mark.asyncio
async def test_get_asset_success():
    ctx = make_ctx({"asset": {"id": "asset-1", "name": "Logo", "tags": ["brand"]}})
    result = await canva_integration.execute_action("get_asset", {"asset_id": "asset-1"}, ctx)
    assert result.result.data["asset"]["name"] == "Logo"
    assert "/v1/assets/asset-1" in fetch_url(ctx)


@pytest.mark.asyncio
async def test_get_asset_missing_id_validation_error():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("get_asset", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_asset_error_returns_action_error():
    ctx = make_failing_ctx(Exception("Not found"))
    result = await canva_integration.execute_action("get_asset", {"asset_id": "missing"}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Not found" in result.result.message


@pytest.mark.asyncio
async def test_update_asset_success_empty_payload_on_success():
    ctx = make_ctx({})
    result = await canva_integration.execute_action(
        "update_asset", {"asset_id": "asset-1", "name": "New Name", "tags": ["a", "b"]}, ctx
    )
    assert result.type == ResultType.ACTION
    assert result.result.data == {}
    assert fetch_kwargs(ctx)["method"] == "PATCH"
    assert fetch_kwargs(ctx)["json"] == {"name": "New Name", "tags": ["a", "b"]}


@pytest.mark.asyncio
async def test_update_asset_only_sends_provided_fields():
    ctx = make_ctx({})
    await canva_integration.execute_action("update_asset", {"asset_id": "a", "name": "only-name"}, ctx)
    assert fetch_kwargs(ctx)["json"] == {"name": "only-name"}


@pytest.mark.asyncio
async def test_delete_asset_success():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("delete_asset", {"asset_id": "asset-1"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data == {}
    assert fetch_kwargs(ctx)["method"] == "DELETE"
    assert "/v1/assets/asset-1" in fetch_url(ctx)


# =============================================================================
# CREATE / LIST / GET DESIGN
# =============================================================================


@pytest.mark.asyncio
async def test_create_design_success():
    ctx = make_ctx({"design": {"id": "design-1", "title": "Deck"}})
    result = await canva_integration.execute_action(
        "create_design", {"preset_type": "presentation", "title": "Deck"}, ctx
    )
    assert result.result.data["design"]["id"] == "design-1"
    body = fetch_kwargs(ctx)["json"]
    assert body["design_type"] == {"type": "preset", "name": "presentation"}
    assert body["title"] == "Deck"


@pytest.mark.asyncio
async def test_create_design_invalid_preset_validation_error():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("create_design", {"preset_type": "banner"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_create_design_missing_preset_validation_error():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("create_design", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_list_designs_success_with_continuation():
    ctx = make_ctx({"items": [{"id": "d1"}, {"id": "d2"}], "continuation": "next-token"})
    result = await canva_integration.execute_action("list_designs", {"sort_by": "modified_descending"}, ctx)
    data = result.result.data
    assert len(data["designs"]) == 2
    assert data["continuation"] == "next-token"
    assert fetch_kwargs(ctx)["params"]["sort_by"] == "modified_descending"


@pytest.mark.asyncio
async def test_list_designs_empty_no_continuation():
    ctx = make_ctx({"items": []})
    result = await canva_integration.execute_action("list_designs", {}, ctx)
    assert result.result.data["designs"] == []
    assert "continuation" not in result.result.data


@pytest.mark.asyncio
async def test_list_designs_error_returns_action_error():
    ctx = make_failing_ctx(Exception("rate limited"))
    result = await canva_integration.execute_action("list_designs", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "rate limited" in result.result.message


@pytest.mark.asyncio
async def test_get_design_success():
    ctx = make_ctx({"design": {"id": "design-1", "title": "My Design"}})
    result = await canva_integration.execute_action("get_design", {"design_id": "design-1"}, ctx)
    assert result.result.data["design"]["title"] == "My Design"
    assert "/v1/designs/design-1" in fetch_url(ctx)


# =============================================================================
# EXPORT DESIGN
# =============================================================================


@pytest.mark.asyncio
async def test_export_design_pdf_success():
    ctx = make_ctx({"job": {"id": "export-1"}})
    result = await canva_integration.execute_action(
        "export_design", {"design_id": "d1", "format": "pdf", "paper_size": "a4"}, ctx
    )
    assert result.result.data["job_id"] == "export-1"
    body = fetch_kwargs(ctx)["json"]
    assert body["design_id"] == "d1"
    assert body["format"]["type"] == "pdf"
    assert body["format"]["size"] == "a4"


@pytest.mark.asyncio
async def test_export_design_jpg_quality_forwarded():
    ctx = make_ctx({"job": {"id": "e"}})
    await canva_integration.execute_action(
        "export_design", {"design_id": "d1", "format": "jpg", "jpg_quality": 50}, ctx
    )
    assert fetch_kwargs(ctx)["json"]["format"]["quality"] == 50


@pytest.mark.asyncio
async def test_export_design_jpg_default_quality():
    ctx = make_ctx({"job": {"id": "e"}})
    await canva_integration.execute_action("export_design", {"design_id": "d1", "format": "jpg"}, ctx)
    assert fetch_kwargs(ctx)["json"]["format"]["quality"] == 85


@pytest.mark.asyncio
async def test_export_design_png_options():
    ctx = make_ctx({"job": {"id": "e"}})
    await canva_integration.execute_action(
        "export_design",
        {"design_id": "d1", "format": "png", "lossless": False, "transparent_background": True},
        ctx,
    )
    fmt = fetch_kwargs(ctx)["json"]["format"]
    assert fmt["lossless"] is False
    assert fmt["transparent_background"] is True


@pytest.mark.asyncio
async def test_export_design_mp4_default_quality():
    ctx = make_ctx({"job": {"id": "e"}})
    await canva_integration.execute_action("export_design", {"design_id": "d1", "format": "mp4"}, ctx)
    assert fetch_kwargs(ctx)["json"]["format"]["quality"] == "horizontal_1080p"


@pytest.mark.asyncio
async def test_export_design_no_job_id_returns_empty():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("export_design", {"design_id": "d1", "format": "pdf"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data == {}


# =============================================================================
# GET EXPORT STATUS
# =============================================================================


@pytest.mark.asyncio
async def test_get_export_status_success():
    ctx = make_ctx({"job": {"status": "success", "urls": ["https://export.canva.com/file.pdf"]}})
    result = await canva_integration.execute_action("get_export_status", {"export_id": "e1"}, ctx)
    assert result.result.data["status"] == "success"
    assert result.result.data["urls"] == ["https://export.canva.com/file.pdf"]
    assert "/v1/exports/e1" in fetch_url(ctx)


# =============================================================================
# IMPORT DESIGN (file + URL) AND STATUS
# =============================================================================


@pytest.mark.asyncio
async def test_import_design_success():
    ctx = make_ctx({"job": {"id": "import-1", "status": "in_progress"}})
    result = await canva_integration.execute_action(
        "import_design",
        {"file": {"content": PNG_B64, "name": "doc.pdf", "contentType": "application/pdf"}},
        ctx,
    )
    assert result.result.data["job_id"] == "import-1"
    assert "/v1/imports" in fetch_url(ctx)


@pytest.mark.asyncio
async def test_import_design_no_file_returns_action_error():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("import_design", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "No file provided" in result.result.message


@pytest.mark.asyncio
async def test_get_design_import_status_success():
    ctx = make_ctx({"job": {"status": "success", "designs": [{"id": "d1"}]}})
    result = await canva_integration.execute_action("get_design_import_status", {"job_id": "j1"}, ctx)
    assert result.result.data["status"] == "success"
    assert result.result.data["designs"] == [{"id": "d1"}]


@pytest.mark.asyncio
async def test_import_design_from_url_success():
    ctx = make_ctx({"job": {"id": "url-import-1", "status": "in_progress"}})
    result = await canva_integration.execute_action(
        "import_design_from_url",
        {"url": "https://example.com/doc.pdf", "title": "Imported"},
        ctx,
    )
    assert result.result.data["job_id"] == "url-import-1"
    body = fetch_kwargs(ctx)["json"]
    assert body["url"] == "https://example.com/doc.pdf"
    assert body["title"] == "Imported"


@pytest.mark.asyncio
async def test_import_design_from_url_missing_url_validation_error():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("import_design_from_url", {"title": "x"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_url_import_status_success():
    ctx = make_ctx({"job": {"status": "success", "designs": [{"id": "d9"}]}})
    result = await canva_integration.execute_action("get_url_import_status", {"job_id": "j9"}, ctx)
    assert result.result.data["status"] == "success"
    assert result.result.data["designs"] == [{"id": "d9"}]


# =============================================================================
# FOLDER ACTIONS
# =============================================================================


@pytest.mark.asyncio
async def test_create_folder_success_defaults_to_root():
    ctx = make_ctx({"folder": {"id": "folder-1", "name": "Campaign"}})
    result = await canva_integration.execute_action("create_folder", {"name": "Campaign"}, ctx)
    assert result.result.data["folder"]["id"] == "folder-1"
    assert fetch_kwargs(ctx)["json"]["parent_folder_id"] == "root"


@pytest.mark.asyncio
async def test_create_folder_respects_parent():
    ctx = make_ctx({"folder": {"id": "f"}})
    await canva_integration.execute_action("create_folder", {"name": "Sub", "parent_folder_id": "parent-1"}, ctx)
    assert fetch_kwargs(ctx)["json"]["parent_folder_id"] == "parent-1"


@pytest.mark.asyncio
async def test_get_folder_success():
    ctx = make_ctx({"folder": {"id": "folder-1", "name": "Brand"}})
    result = await canva_integration.execute_action("get_folder", {"folder_id": "folder-1"}, ctx)
    assert result.result.data["folder"]["name"] == "Brand"
    assert "/v1/folders/folder-1" in fetch_url(ctx)


@pytest.mark.asyncio
async def test_list_folder_items_success_with_continuation():
    ctx = make_ctx({"items": [{"type": "design"}, {"type": "asset"}], "continuation": "tok"})
    result = await canva_integration.execute_action("list_folder_items", {"folder_id": "folder-1"}, ctx)
    data = result.result.data
    assert len(data["items"]) == 2
    assert data["continuation"] == "tok"


@pytest.mark.asyncio
async def test_list_folder_items_empty_no_continuation():
    ctx = make_ctx({"items": []})
    result = await canva_integration.execute_action("list_folder_items", {"folder_id": "f"}, ctx)
    assert result.result.data["items"] == []
    assert "continuation" not in result.result.data


@pytest.mark.asyncio
async def test_update_folder_success():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("update_folder", {"folder_id": "f1", "name": "Renamed"}, ctx)
    assert result.type == ResultType.ACTION
    assert result.result.data == {}
    assert fetch_kwargs(ctx)["method"] == "PATCH"
    assert fetch_kwargs(ctx)["json"] == {"name": "Renamed"}


@pytest.mark.asyncio
async def test_delete_folder_success():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("delete_folder", {"folder_id": "f1"}, ctx)
    assert result.result.data == {}
    assert fetch_kwargs(ctx)["method"] == "DELETE"
    assert "/v1/folders/f1" in fetch_url(ctx)


@pytest.mark.asyncio
async def test_move_item_to_folder_success():
    ctx = make_ctx({})
    result = await canva_integration.execute_action(
        "move_item_to_folder", {"item_id": "item-1", "destination_folder_id": "folder-2"}, ctx
    )
    assert result.type == ResultType.ACTION
    assert result.result.data == {}
    assert "/v1/folders/move" in fetch_url(ctx)
    body = fetch_kwargs(ctx)["json"]
    assert body == {"to_folder_id": "folder-2", "item_id": "item-1"}


@pytest.mark.asyncio
async def test_move_item_to_folder_missing_fields_validation_error():
    ctx = make_ctx({})
    result = await canva_integration.execute_action("move_item_to_folder", {"item_id": "item-1"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# ERROR-PATH SWEEP — every action must convert a fetch failure to ActionError
# (verifies the SDK 2.0.0 migration rewrote every except block, not just some)
# =============================================================================

# (action, minimal valid inputs that reach the fetch call)
ACTION_ERROR_CASES = [
    ("get_user_capabilities", {}),
    ("upload_asset", {"file": {"content": PNG_B64, "name": "a.png", "contentType": "image/png"}}),
    ("get_asset_upload_status", {"job_id": "j"}),
    ("get_asset", {"asset_id": "a"}),
    ("update_asset", {"asset_id": "a", "name": "n"}),
    ("delete_asset", {"asset_id": "a"}),
    ("create_design", {"preset_type": "doc"}),
    ("list_designs", {}),
    ("get_design", {"design_id": "d"}),
    ("export_design", {"design_id": "d", "format": "pdf"}),
    ("get_export_status", {"export_id": "e"}),
    ("import_design", {"file": {"content": PNG_B64, "name": "a.pdf", "contentType": "application/pdf"}}),
    ("get_design_import_status", {"job_id": "j"}),
    ("import_design_from_url", {"url": "https://example.com/y.pdf", "title": "t"}),
    ("get_url_import_status", {"job_id": "j"}),
    ("create_folder", {"name": "n"}),
    ("get_folder", {"folder_id": "f"}),
    ("list_folder_items", {"folder_id": "f"}),
    ("update_folder", {"folder_id": "f", "name": "n"}),
    ("delete_folder", {"folder_id": "f"}),
    ("move_item_to_folder", {"item_id": "i", "destination_folder_id": "f"}),
]


@pytest.mark.parametrize("action,inputs", ACTION_ERROR_CASES, ids=[c[0] for c in ACTION_ERROR_CASES])
@pytest.mark.asyncio
async def test_action_returns_action_error_on_fetch_failure(action, inputs):
    ctx = make_failing_ctx(Exception("upstream 503"))
    result = await canva_integration.execute_action(action, inputs, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "upstream 503" in result.result.message
