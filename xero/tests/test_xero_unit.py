import os
import sys
import importlib
import base64

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk import ResultType, FetchResponse  # noqa: E402

os.chdir(_parent)
_spec = importlib.util.spec_from_file_location(
    "xero_mod", os.path.join(_parent, "xero.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
sys.modules["xero_mod"] = _mod

xero = _mod.xero
XeroRateLimitExceededException = _mod.XeroRateLimitExceededException

pytestmark = pytest.mark.unit

XERO_API_BASE = "https://api.xero.com/api.xro/2.0"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "credentials": {"access_token": "test_token", "tenant_id": "test_tenant"}  # nosec B105
    }
    return ctx


def _aiohttp_session_mock(*, status: int, body: bytes = b"", text: str = ""):
    """Build a MagicMock that mimics aiohttp.ClientSession() as an async context manager."""
    resp = MagicMock()
    resp.status = status
    resp.read = AsyncMock(return_value=body)
    resp.text = AsyncMock(return_value=text)
    resp.headers = {"content-type": "application/pdf"}

    request_cm = MagicMock()
    request_cm.__aenter__ = AsyncMock(return_value=resp)
    request_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=request_cm)
    session.post = MagicMock(return_value=request_cm)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    session_cls = MagicMock(return_value=session_cm)
    return session_cls, session, resp


# ---- get_available_connections ----


class TestGetAvailableConnections:
    async def test_returns_companies(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200,
            headers={},
            data=[
                {"tenantId": "tid1", "tenantName": "Acme Corp"},
                {"tenantId": "tid2", "tenantName": "Beta Ltd"},
            ],
        )

        result = await xero.execute_action(
            "get_available_connections", {}, mock_context
        )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert len(data["companies"]) == 2
        assert data["companies"][0]["tenant_id"] == "tid1"
        assert data["companies"][0]["company_name"] == "Acme Corp"

    async def test_fetch_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Network error")

        result = await xero.execute_action(
            "get_available_connections", {}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message


# ---- find_contact_by_name ----


class TestFindContactByName:
    async def test_returns_contacts(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Contacts": [
                        {
                            "ContactID": "c1",
                            "Name": "John Smith",
                            "EmailAddress": "john@example.com",
                            "ContactStatus": "ACTIVE",
                        }
                    ]
                }
            )
            inputs = {"tenant_id": "test_tenant", "contact_name": "John"}

            result = await xero.execute_action(
                "find_contact_by_name", inputs, mock_context
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert len(data["contacts"]) == 1
        assert data["contacts"][0]["contact_id"] == "c1"
        assert data["contacts"][0]["name"] == "John Smith"

    async def test_no_contacts_found(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value={"Contacts": []})
            inputs = {"tenant_id": "test_tenant", "contact_name": "Nobody"}

            result = await xero.execute_action(
                "find_contact_by_name", inputs, mock_context
            )

        assert result.type == ResultType.ACTION
        assert result.result.data["contacts"] == []

    async def test_rate_limit_exception_returns_action_error(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(
                    requested_delay=120, max_wait_time=60, tenant_id="test_tenant"
                )
            )
            inputs = {"tenant_id": "test_tenant", "contact_name": "Test"}

            result = await xero.execute_action(
                "find_contact_by_name", inputs, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "120" in result.result.message


# ---- get_accounts ----


class TestGetAccounts:
    async def test_returns_accounts(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Accounts": [
                        {
                            "AccountID": "a1",
                            "Code": "200",
                            "Name": "Sales",
                            "Type": "REVENUE",
                        },
                        {
                            "AccountID": "a2",
                            "Code": "400",
                            "Name": "Advertising",
                            "Type": "EXPENSE",
                        },
                    ]
                }
            )
            inputs = {"tenant_id": "test_tenant"}

            result = await xero.execute_action("get_accounts", inputs, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "Accounts" in data
        assert len(data["Accounts"]) == 2
        assert data["Accounts"][0]["Code"] == "200"

    async def test_rate_limit_exception_returns_action_error(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(
                    requested_delay=90, max_wait_time=60, tenant_id="test_tenant"
                )
            )

            result = await xero.execute_action(
                "get_accounts", {"tenant_id": "test_tenant"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "90" in result.result.message


# ---- get_invoices ----


class TestGetInvoices:
    async def test_returns_invoices(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Invoices": [
                        {
                            "InvoiceID": "inv1",
                            "InvoiceNumber": "INV-001",
                            "Status": "AUTHORISED",
                        }
                    ]
                }
            )
            inputs = {"tenant_id": "test_tenant", "where": 'Status=="AUTHORISED"'}

            result = await xero.execute_action("get_invoices", inputs, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "Invoices" in data
        assert data["Invoices"][0]["InvoiceNumber"] == "INV-001"

    async def test_rate_limit_exception_returns_action_error(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(
                    requested_delay=180, max_wait_time=60, tenant_id="test_tenant"
                )
            )

            result = await xero.execute_action(
                "get_invoices", {"tenant_id": "test_tenant"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "180" in result.result.message


# ---- get_invoice_pdf ----


class TestGetInvoicePdf:
    async def test_returns_base64_pdf(self, mock_context):
        pdf_bytes = b"%PDF-1.4 mock pdf content"
        session_cls, _session, _resp = _aiohttp_session_mock(status=200, body=pdf_bytes)

        inputs = {"tenant_id": "test_tenant", "invoice_id": "inv1"}
        with patch("xero_mod.aiohttp.ClientSession", session_cls):
            result = await xero.execute_action("get_invoice_pdf", inputs, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["file"]["name"] == "invoice_inv1.pdf"
        assert data["file"]["contentType"] == "application/pdf"
        assert data["file"]["content"] == base64.b64encode(pdf_bytes).decode("utf-8")

    async def test_http_error_returns_action_error(self, mock_context):
        session_cls, _session, resp = _aiohttp_session_mock(
            status=404, text="Not found"
        )
        resp.text = AsyncMock(return_value="Not found")

        inputs = {"tenant_id": "test_tenant", "invoice_id": "missing"}
        with patch("xero_mod.aiohttp.ClientSession", session_cls):
            result = await xero.execute_action("get_invoice_pdf", inputs, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "404" in result.result.message


# ---- get_payments ----


class TestGetPayments:
    async def test_returns_payments(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Payments": [
                        {
                            "PaymentID": "pay1",
                            "Amount": 500.0,
                            "PaymentType": "ACCRECPAYMENT",
                            "Status": "AUTHORISED",
                        }
                    ]
                }
            )
            inputs = {"tenant_id": "test_tenant"}

            result = await xero.execute_action("get_payments", inputs, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "Payments" in data
        assert data["Payments"][0]["PaymentID"] == "pay1"

    async def test_rate_limit_exception_returns_action_error(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(
                    requested_delay=75, max_wait_time=60, tenant_id="test_tenant"
                )
            )

            result = await xero.execute_action(
                "get_payments", {"tenant_id": "test_tenant"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_bank_transactions ----


class TestGetBankTransactions:
    async def test_returns_transactions(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "BankTransactions": [
                        {
                            "BankTransactionID": "bt1",
                            "Type": "SPEND",
                            "Total": 250.0,
                            "Status": "AUTHORISED",
                        }
                    ]
                }
            )
            inputs = {"tenant_id": "test_tenant"}

            result = await xero.execute_action(
                "get_bank_transactions", inputs, mock_context
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "BankTransactions" in data
        assert data["BankTransactions"][0]["BankTransactionID"] == "bt1"


# ---- get_balance_sheet ----


class TestGetBalanceSheet:
    async def test_returns_report(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Reports": [
                        {"ReportID": "BalanceSheet", "ReportName": "Balance Sheet"}
                    ]
                }
            )
            inputs = {"tenant_id": "test_tenant"}

            result = await xero.execute_action(
                "get_balance_sheet", inputs, mock_context
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "Reports" in data

    async def test_rate_limit_exception_returns_action_error(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(
                    requested_delay=90, max_wait_time=60, tenant_id="test_tenant"
                )
            )

            result = await xero.execute_action(
                "get_balance_sheet", {"tenant_id": "test_tenant"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_aged_payables ----


class TestGetAgedPayables:
    async def test_returns_report(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Reports": [
                        {
                            "ReportID": "AgedPayablesByContact",
                            "ReportName": "Aged Payables",
                        }
                    ]
                }
            )
            inputs = {"tenant_id": "test_tenant", "contact_id": "c1"}

            result = await xero.execute_action(
                "get_aged_payables", inputs, mock_context
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "Reports" in data


# ---- create_sales_invoice ----


class TestCreateSalesInvoice:
    async def test_creates_invoice(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Invoices": [
                        {
                            "InvoiceID": "new-inv-1",
                            "InvoiceNumber": "INV-NEW-001",
                            "Status": "DRAFT",
                            "Type": "ACCREC",
                        }
                    ]
                }
            )
            inputs = {
                "tenant_id": "test_tenant",
                "contact": {"ContactID": "c1"},
                "line_items": [
                    {
                        "Description": "Consulting",
                        "Quantity": 5,
                        "UnitAmount": 100.0,
                        "AccountCode": "200",
                    }
                ],
            }

            result = await xero.execute_action(
                "create_sales_invoice", inputs, mock_context
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "Invoices" in data
        assert data["Invoices"][0]["InvoiceNumber"] == "INV-NEW-001"
        assert data["Invoices"][0]["Status"] == "DRAFT"


# ---- get_purchase_orders ----


class TestGetPurchaseOrders:
    async def test_returns_purchase_orders(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "PurchaseOrders": [
                        {
                            "PurchaseOrderID": "po1",
                            "PurchaseOrderNumber": "PO-001",
                            "Status": "AUTHORISED",
                        }
                    ]
                }
            )
            inputs = {"tenant_id": "test_tenant"}

            result = await xero.execute_action(
                "get_purchase_orders", inputs, mock_context
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "PurchaseOrders" in data
        assert data["PurchaseOrders"][0]["PurchaseOrderNumber"] == "PO-001"

    async def test_rate_limit_exception_returns_action_error(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(
                    requested_delay=150, max_wait_time=60, tenant_id="test_tenant"
                )
            )

            result = await xero.execute_action(
                "get_purchase_orders", {"tenant_id": "test_tenant"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "150" in result.result.message


# ---- create_purchase_order ----


class TestCreatePurchaseOrder:
    async def test_creates_purchase_order(self, mock_context):
        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "PurchaseOrders": [
                        {
                            "PurchaseOrderID": "new-po-1",
                            "PurchaseOrderNumber": "PO-NEW-001",
                            "Status": "DRAFT",
                        }
                    ]
                }
            )
            inputs = {
                "tenant_id": "test_tenant",
                "contact": {"ContactID": "c1"},
                "line_items": [
                    {
                        "Description": "Office Supplies",
                        "Quantity": 5,
                        "UnitAmount": 50.0,
                        "AccountCode": "200",
                    }
                ],
            }

            result = await xero.execute_action(
                "create_purchase_order", inputs, mock_context
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "PurchaseOrders" in data
        assert data["PurchaseOrders"][0]["PurchaseOrderNumber"] == "PO-NEW-001"


# ---- attach_file_to_invoice ----


class TestAttachFileToInvoice:
    async def test_attaches_file(self, mock_context):
        test_content = b"Mock PDF content"
        base64_content = base64.b64encode(test_content).decode("utf-8")

        with patch("xero_mod.rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Attachments": [
                        {
                            "AttachmentID": "att1",
                            "FileName": "test.pdf",
                            "MimeType": "application/pdf",
                        }
                    ]
                }
            )
            # The action expects a 'file' object (standard SDK file format)
            inputs = {
                "tenant_id": "test_tenant",
                "invoice_id": "inv1",
                "file": {
                    "name": "test.pdf",
                    "contentType": "application/pdf",
                    "content": base64_content,
                },
            }

            result = await xero.execute_action(
                "attach_file_to_invoice", inputs, mock_context
            )

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert "Attachments" in data
        assert data["Attachments"][0]["FileName"] == "test.pdf"
