import os
import sys
import importlib.util
import base64

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("xero_mod", os.path.join(_parent, "xero.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

xero = _mod.xero
XeroRateLimitExceededException = _mod.XeroRateLimitExceededException

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


SAMPLE_FILE_CONTENT = b"Test file content"
SAMPLE_BASE64 = base64.b64encode(SAMPLE_FILE_CONTENT).decode("utf-8")

SAMPLE_ATTACHMENT = {
    "AttachmentID": "att-001",
    "FileName": "test.pdf",
    "Url": "https://api.xero.com/test",
    "MimeType": "application/pdf",
    "ContentLength": len(SAMPLE_FILE_CONTENT),
}

SAMPLE_ATTACHMENTS_RESPONSE = {"Attachments": [SAMPLE_ATTACHMENT]}


# ---- attach_file_to_invoice ----


class TestAttachFileToInvoice:
    @pytest.mark.asyncio
    async def test_attaches_file_successfully(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_ATTACHMENTS_RESPONSE)

            result = await xero.execute_action(
                "attach_file_to_invoice",
                {
                    "tenant_id": "t-001",
                    "invoice_id": "inv-001",
                    "file": {
                        "name": "test.pdf",
                        "contentType": "application/pdf",
                        "content": SAMPLE_BASE64,
                    },
                },
                mock_context,
            )

        assert "Attachments" in result.result.data

    @pytest.mark.asyncio
    async def test_posts_with_decoded_bytes(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_ATTACHMENTS_RESPONSE)

            await xero.execute_action(
                "attach_file_to_invoice",
                {
                    "tenant_id": "t-001",
                    "invoice_id": "inv-001",
                    "file": {
                        "name": "test.pdf",
                        "contentType": "application/pdf",
                        "content": SAMPLE_BASE64,
                    },
                },
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert call_args.kwargs["data"] == SAMPLE_FILE_CONTENT
            assert call_args.kwargs["method"] == "POST"
            assert "test.pdf" in call_args.args[1]

    @pytest.mark.asyncio
    async def test_uses_files_array_when_file_absent(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_ATTACHMENTS_RESPONSE)

            result = await xero.execute_action(
                "attach_file_to_invoice",
                {
                    "tenant_id": "t-001",
                    "invoice_id": "inv-001",
                    "files": [
                        {
                            "name": "test.pdf",
                            "contentType": "application/pdf",
                            "content": SAMPLE_BASE64,
                        }
                    ],
                },
                mock_context,
            )

        assert result.result.data is not None

    @pytest.mark.asyncio
    async def test_rate_limit_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=XeroRateLimitExceededException(90, 60, "t-001"))

            result = await xero.execute_action(
                "attach_file_to_invoice",
                {
                    "tenant_id": "t-001",
                    "invoice_id": "inv-001",
                    "file": {
                        "name": "test.pdf",
                        "contentType": "application/pdf",
                        "content": SAMPLE_BASE64,
                    },
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Upload failed"))

            result = await xero.execute_action(
                "attach_file_to_invoice",
                {
                    "tenant_id": "t-001",
                    "invoice_id": "inv-001",
                    "file": {
                        "name": "test.pdf",
                        "contentType": "application/pdf",
                        "content": SAMPLE_BASE64,
                    },
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- attach_file_to_bill ----


class TestAttachFileToBill:
    @pytest.mark.asyncio
    async def test_attaches_file_to_bill(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_ATTACHMENTS_RESPONSE)

            result = await xero.execute_action(
                "attach_file_to_bill",
                {
                    "tenant_id": "t-001",
                    "bill_id": "bill-001",
                    "file": {
                        "name": "invoice.pdf",
                        "contentType": "application/pdf",
                        "content": SAMPLE_BASE64,
                    },
                },
                mock_context,
            )

        assert "Attachments" in result.result.data

    @pytest.mark.asyncio
    async def test_uses_bill_id_in_url(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_ATTACHMENTS_RESPONSE)

            await xero.execute_action(
                "attach_file_to_bill",
                {
                    "tenant_id": "t-001",
                    "bill_id": "bill-001",
                    "file": {
                        "name": "invoice.pdf",
                        "contentType": "application/pdf",
                        "content": SAMPLE_BASE64,
                    },
                },
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "bill-001" in call_args.args[1]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Error"))

            result = await xero.execute_action(
                "attach_file_to_bill",
                {
                    "tenant_id": "t-001",
                    "bill_id": "bill-001",
                    "file": {
                        "name": "invoice.pdf",
                        "contentType": "application/pdf",
                        "content": SAMPLE_BASE64,
                    },
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_attachments ----


class TestGetAttachments:
    @pytest.mark.asyncio
    async def test_returns_attachments(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_ATTACHMENTS_RESPONSE)

            result = await xero.execute_action(
                "get_attachments",
                {"tenant_id": "t-001", "endpoint": "Invoices", "guid": "inv-001"},
                mock_context,
            )

        assert "Attachments" in result.result.data

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_ATTACHMENTS_RESPONSE)

            await xero.execute_action(
                "get_attachments",
                {"tenant_id": "t-001", "endpoint": "Invoices", "guid": "inv-001"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "Invoices/inv-001/Attachments" in call_args.args[1]
            assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_rate_limit_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=XeroRateLimitExceededException(80, 60, "t-001"))

            result = await xero.execute_action(
                "get_attachments",
                {"tenant_id": "t-001", "endpoint": "Invoices", "guid": "inv-001"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Error"))

            result = await xero.execute_action(
                "get_attachments",
                {"tenant_id": "t-001", "endpoint": "Invoices", "guid": "inv-001"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
