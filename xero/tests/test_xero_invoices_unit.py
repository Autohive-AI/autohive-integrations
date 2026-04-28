import os
import sys
import importlib.util

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


SAMPLE_INVOICE = {
    "InvoiceID": "inv-001",
    "InvoiceNumber": "INV-0001",
    "Type": "ACCREC",
    "Status": "AUTHORISED",
    "Contact": {"ContactID": "c-001", "Name": "Acme Corp"},
    "LineItems": [{"Description": "Services", "Quantity": 1, "UnitAmount": 1000.0, "LineAmount": 1000.0}],
    "Total": 1000.0,
}

SAMPLE_INVOICES_RESPONSE = {"Invoices": [SAMPLE_INVOICE]}


# ---- get_invoices ----


class TestGetInvoices:
    @pytest.mark.asyncio
    async def test_returns_invoices(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_INVOICES_RESPONSE)

            result = await xero.execute_action("get_invoices", {"tenant_id": "t-001"}, mock_context)

        assert "Invoices" in result.result.data
        assert len(result.result.data["Invoices"]) == 1

    @pytest.mark.asyncio
    async def test_calls_invoices_endpoint(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_INVOICES_RESPONSE)

            await xero.execute_action("get_invoices", {"tenant_id": "t-001"}, mock_context)

            call_args = mock_limiter.make_request.call_args
            assert "api.xero.com/api.xro/2.0/Invoices" in call_args.args[1]
            assert call_args.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_specific_invoice_by_id(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_INVOICES_RESPONSE)

            await xero.execute_action("get_invoices", {"tenant_id": "t-001", "invoice_id": "inv-001"}, mock_context)

            call_args = mock_limiter.make_request.call_args
            assert "inv-001" in call_args.args[1]

    @pytest.mark.asyncio
    async def test_where_and_order_filters(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_INVOICES_RESPONSE)

            await xero.execute_action(
                "get_invoices",
                {"tenant_id": "t-001", "where": 'Status=="AUTHORISED"', "order": "Date DESC"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert call_args.kwargs["params"]["where"] == 'Status=="AUTHORISED"'
            assert call_args.kwargs["params"]["order"] == "Date DESC"

    @pytest.mark.asyncio
    async def test_rate_limit_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=XeroRateLimitExceededException(120, 60, "t-001"))

            result = await xero.execute_action("get_invoices", {"tenant_id": "t-001"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "rate limit" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("API error"))

            result = await xero.execute_action("get_invoices", {"tenant_id": "t-001"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message


# ---- get_bank_transactions ----


class TestGetBankTransactions:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={"BankTransactions": [{"BankTransactionID": "bt-001", "Total": 250.0}]}
            )

            result = await xero.execute_action("get_bank_transactions", {"tenant_id": "t-001"}, mock_context)

        assert "BankTransactions" in result.result.data

    @pytest.mark.asyncio
    async def test_where_and_page_params(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value={"BankTransactions": []})

            await xero.execute_action(
                "get_bank_transactions",
                {"tenant_id": "t-001", "where": 'Type="RECEIVE"', "page": 2},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert call_args.kwargs["params"]["where"] == 'Type="RECEIVE"'
            assert call_args.kwargs["params"]["page"] == "2"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Error"))

            result = await xero.execute_action("get_bank_transactions", {"tenant_id": "t-001"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- create_sales_invoice ----


class TestCreateSalesInvoice:
    @pytest.mark.asyncio
    async def test_creates_invoice(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_INVOICES_RESPONSE)

            result = await xero.execute_action(
                "create_sales_invoice",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [{"Description": "Services", "UnitAmount": 100.0, "AccountCode": "200"}],
                },
                mock_context,
            )

        assert "Invoices" in result.result.data

    @pytest.mark.asyncio
    async def test_posts_to_invoices_endpoint(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_INVOICES_RESPONSE)

            await xero.execute_action(
                "create_sales_invoice",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [{"Description": "Services", "UnitAmount": 100.0, "AccountCode": "200"}],
                },
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "api.xero.com/api.xro/2.0/Invoices" in call_args.args[1]
            assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_payload_has_accrec_type(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_INVOICES_RESPONSE)

            await xero.execute_action(
                "create_sales_invoice",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [{"Description": "Services", "UnitAmount": 100.0, "AccountCode": "200"}],
                },
                mock_context,
            )

            payload = mock_limiter.make_request.call_args.kwargs["json"]
            assert payload["Invoices"][0]["Type"] == "ACCREC"

    @pytest.mark.asyncio
    async def test_optional_fields_included(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_INVOICES_RESPONSE)

            await xero.execute_action(
                "create_sales_invoice",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [{"Description": "Services", "UnitAmount": 100.0, "AccountCode": "200"}],
                    "status": "AUTHORISED",
                    "invoice_number": "INV-001",
                    "reference": "REF-001",
                },
                mock_context,
            )

            payload = mock_limiter.make_request.call_args.kwargs["json"]
            inv = payload["Invoices"][0]
            assert inv["Status"] == "AUTHORISED"
            assert inv["InvoiceNumber"] == "INV-001"
            assert inv["Reference"] == "REF-001"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("API error"))

            result = await xero.execute_action(
                "create_sales_invoice",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [{"Description": "Services", "UnitAmount": 100.0, "AccountCode": "200"}],
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_rate_limit_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=XeroRateLimitExceededException(90, 60, "t-001"))

            result = await xero.execute_action(
                "create_sales_invoice",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [{"Description": "Services", "UnitAmount": 100.0, "AccountCode": "200"}],
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- create_purchase_bill ----


class TestCreatePurchaseBill:
    @pytest.mark.asyncio
    async def test_creates_bill(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={"Invoices": [{"InvoiceID": "bill-001", "Type": "ACCPAY", "Status": "DRAFT"}]}
            )

            result = await xero.execute_action(
                "create_purchase_bill",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [{"Description": "Supplies", "UnitAmount": 200.0, "AccountCode": "300"}],
                },
                mock_context,
            )

        assert "Invoices" in result.result.data

    @pytest.mark.asyncio
    async def test_payload_has_accpay_type(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value={"Invoices": [{"InvoiceID": "bill-001"}]})

            await xero.execute_action(
                "create_purchase_bill",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [{"Description": "Supplies", "UnitAmount": 200.0, "AccountCode": "300"}],
                },
                mock_context,
            )

            payload = mock_limiter.make_request.call_args.kwargs["json"]
            assert payload["Invoices"][0]["Type"] == "ACCPAY"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Error"))

            result = await xero.execute_action(
                "create_purchase_bill",
                {
                    "tenant_id": "t-001",
                    "contact": {"ContactID": "c-001"},
                    "line_items": [{"Description": "S", "UnitAmount": 1.0, "AccountCode": "300"}],
                },
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- update_sales_invoice ----


class TestUpdateSalesInvoice:
    @pytest.mark.asyncio
    async def test_updates_invoice(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_INVOICES_RESPONSE)

            result = await xero.execute_action(
                "update_sales_invoice",
                {"tenant_id": "t-001", "invoice_id": "inv-001", "status": "AUTHORISED"},
                mock_context,
            )

        assert "Invoices" in result.result.data

    @pytest.mark.asyncio
    async def test_posts_to_correct_url(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_INVOICES_RESPONSE)

            await xero.execute_action(
                "update_sales_invoice",
                {"tenant_id": "t-001", "invoice_id": "inv-001"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "inv-001" in call_args.args[1]
            assert call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Error"))

            result = await xero.execute_action(
                "update_sales_invoice",
                {"tenant_id": "t-001", "invoice_id": "inv-001"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- update_purchase_bill ----


class TestUpdatePurchaseBill:
    @pytest.mark.asyncio
    async def test_updates_bill(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={"Invoices": [{"InvoiceID": "bill-001", "Status": "AUTHORISED"}]}
            )

            result = await xero.execute_action(
                "update_purchase_bill",
                {"tenant_id": "t-001", "invoice_id": "bill-001", "status": "AUTHORISED"},
                mock_context,
            )

        assert "Invoices" in result.result.data

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Error"))

            result = await xero.execute_action(
                "update_purchase_bill",
                {"tenant_id": "t-001", "invoice_id": "bill-001"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_invoice_pdf ----


class TestGetInvoicePdf:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        import base64

        pdf_bytes = b"%PDF-1.4 test"
        mock_aio_response = MagicMock()
        mock_aio_response.status = 200
        mock_aio_response.headers = {"content-type": "application/pdf"}
        mock_aio_response.read = AsyncMock(return_value=pdf_bytes)
        mock_aio_response.__aenter__ = AsyncMock(return_value=mock_aio_response)
        mock_aio_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_aio_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await xero.execute_action(
                "get_invoice_pdf", {"tenant_id": "t-001", "invoice_id": "inv-001"}, mock_context
            )

        assert "file" in result.result.data
        assert result.result.data["file"]["name"] == "invoice_inv-001.pdf"
        assert result.result.data["file"]["content"] == base64.b64encode(pdf_bytes).decode("utf-8")

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_aio_response = MagicMock()
        mock_aio_response.status = 404
        mock_aio_response.text = AsyncMock(return_value="Not found")
        mock_aio_response.__aenter__ = AsyncMock(return_value=mock_aio_response)
        mock_aio_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_aio_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await xero.execute_action(
                "get_invoice_pdf", {"tenant_id": "t-001", "invoice_id": "inv-001"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "404" in result.result.message

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch("aiohttp.ClientSession", side_effect=Exception("Connection refused")):
            result = await xero.execute_action(
                "get_invoice_pdf", {"tenant_id": "t-001", "invoice_id": "inv-001"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection refused" in result.result.message
