import base64
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from powerbi.powerbi import GetImportStatusAction, ImportPowerBIFileAction

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.fetch = AsyncMock()
    return context


def make_file(content=b"test report bytes", name="Sales.pbix", content_type="application/octet-stream"):
    return {
        "content": base64.b64encode(content).decode("ascii"),
        "name": name,
        "contentType": content_type,
    }


@pytest.mark.asyncio
async def test_import_powerbi_file_uploads_binary_multipart_to_workspace(mock_context):
    mock_context.fetch.return_value = {"id": "import-1"}

    result = await ImportPowerBIFileAction().execute(
        {
            "file": make_file(content=b"PK\x00\xffbinary", name="Quarterly Sales.pbix"),
            "workspace_id": "workspace-1",
            "display_name": "Quarterly Sales",
            "name_conflict": "CreateOrOverwrite",
        },
        mock_context,
    )

    assert result == {
        "import_id": "import-1",
        "import_state": "Publishing",
        "name": "Quarterly Sales.pbix",
        "reports": [],
        "datasets": [],
        "result": True,
    }
    call = mock_context.fetch.await_args
    assert call.args[0].endswith("/groups/workspace-1/imports")
    assert call.kwargs["method"] == "POST"
    assert call.kwargs["params"] == {
        "datasetDisplayName": "Quarterly Sales.pbix",
        "nameConflict": "CreateOrOverwrite",
    }
    assert call.kwargs["timeout"] == 600

    form = call.kwargs["data"]
    assert isinstance(form, aiohttp.FormData)
    disposition, headers, payload = form._fields[0]
    assert disposition["name"] == "file"
    assert disposition["filename"] == "Quarterly Sales.pbix"
    assert headers["Content-Type"] == "application/octet-stream"
    assert payload == b"PK\x00\xffbinary"


@pytest.mark.asyncio
async def test_import_powerbi_file_defaults_rdl_conflict_to_abort(mock_context):
    mock_context.fetch.return_value = {"id": "import-rdl", "importState": "Publishing"}

    result = await ImportPowerBIFileAction().execute(
        {"file": make_file(name="Invoice.rdl", content_type="application/xml")},
        mock_context,
    )

    assert result["result"] is True
    assert mock_context.fetch.await_args.kwargs["params"]["nameConflict"] == "Abort"
    assert mock_context.fetch.await_args.args[0].endswith("/imports")
    assert "/groups/" not in mock_context.fetch.await_args.args[0]


@pytest.mark.asyncio
async def test_import_powerbi_file_rejects_invalid_rdl_conflict_without_api_call(mock_context):
    result = await ImportPowerBIFileAction().execute(
        {
            "file": make_file(name="Invoice.rdl", content_type="application/xml"),
            "name_conflict": "Ignore",
        },
        mock_context,
    )

    assert result["result"] is False
    assert "Abort or Overwrite" in result["error"]
    mock_context.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_powerbi_file_rejects_non_model_json(mock_context):
    result = await ImportPowerBIFileAction().execute(
        {"file": make_file(name="report.json", content_type="application/json")},
        mock_context,
    )

    assert result["result"] is False
    assert "model.json" in result["error"]
    mock_context.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_powerbi_file_rejects_skip_report_for_non_pbix(mock_context):
    result = await ImportPowerBIFileAction().execute(
        {"file": make_file(name="Data.xlsx"), "skip_report": True},
        mock_context,
    )

    assert result["result"] is False
    assert "PBIX" in result["error"]
    mock_context.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_powerbi_file_rejects_label_overrides_for_non_pbix(mock_context):
    result = await ImportPowerBIFileAction().execute(
        {"file": make_file(name="Invoice.rdl"), "override_report_label": True},
        mock_context,
    )

    assert result["result"] is False
    assert "PBIX" in result["error"]
    mock_context.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_powerbi_file_rejects_malformed_base64(mock_context):
    result = await ImportPowerBIFileAction().execute(
        {
            "file": {
                "content": "not valid base64!",
                "name": "Sales.pbix",
                "contentType": "application/octet-stream",
            }
        },
        mock_context,
    )

    assert result["result"] is False
    assert "valid base64" in result["error"]
    mock_context.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_import_status_returns_created_reports_and_datasets(mock_context):
    mock_context.fetch.return_value = {
        "id": "import-1",
        "importState": "Succeeded",
        "name": "Quarterly Sales",
        "createdDateTime": "2026-09-01T00:00:00Z",
        "updatedDateTime": "2026-09-01T00:01:00Z",
        "reports": [{"id": "report-1", "name": "Quarterly Sales"}],
        "datasets": [{"id": "dataset-1", "name": "Quarterly Sales"}],
    }

    result = await GetImportStatusAction().execute(
        {"import_id": "import-1", "workspace_id": "workspace-1"},
        mock_context,
    )

    assert result["result"] is True
    assert result["import_state"] == "Succeeded"
    assert result["reports"][0]["id"] == "report-1"
    assert result["datasets"][0]["id"] == "dataset-1"
    assert mock_context.fetch.await_args.args[0].endswith("/groups/workspace-1/imports/import-1")


@pytest.mark.asyncio
async def test_get_import_status_preserves_provider_failure_details(mock_context):
    mock_context.fetch.return_value = {
        "id": "import-1",
        "importState": "Failed",
        "name": "Quarterly Sales",
        "error": {"code": "ImportFailed", "details": [{"message": "Invalid package"}]},
    }

    result = await GetImportStatusAction().execute({"import_id": "import-1"}, mock_context)

    assert result["result"] is True
    assert result["import_state"] == "Failed"
    assert result["import_error"]["code"] == "ImportFailed"
