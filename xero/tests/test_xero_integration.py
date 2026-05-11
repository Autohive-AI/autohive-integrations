"""
Live integration tests for the Xero integration.

Requires XERO_ACCESS_TOKEN and XERO_TENANT_ID set in environment.

Safe read-only run:
    pytest xero/tests/test_xero_integration.py -m "integration and not destructive"

Write/mutating tests (create, update, delete, attach) are marked destructive and
skipped by default — they create real data in the Xero test org.

    pytest xero/tests/test_xero_integration.py -m "integration and destructive"
"""

from unittest.mock import AsyncMock

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from xero import xero


def assert_action_success(result):
    """Assert result is a successful ActionResult, not an ActionError."""
    if result.type == ResultType.ACTION_ERROR:
        raise AssertionError(f"Action returned error: {result.result.message}")
    assert result.type == ResultType.ACTION, f"Unexpected result type: {result.type}"
    return result.result.data


pytestmark = pytest.mark.integration


@pytest.fixture
def live_context(env_credentials, make_context):
    access_token = env_credentials("XERO_ACCESS_TOKEN")
    tenant_id = env_credentials("XERO_TENANT_ID")
    if not access_token:
        pytest.skip("XERO_ACCESS_TOKEN not set — skipping integration tests")
    if not tenant_id:
        pytest.skip("XERO_TENANT_ID not set — skipping integration tests")

    async def real_fetch(
        url, *, method="GET", json=None, headers=None, params=None, **kwargs
    ):
        merged_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        if headers:
            merged_headers.update(headers)
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
                    data = await resp.json()
                except aiohttp.ContentTypeError:
                    data = {}
                return FetchResponse(
                    status=resp.status, headers=dict(resp.headers), data=data
                )

    ctx = make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {
                "access_token": access_token,
                "tenant_id": tenant_id,
            },
        }
    )
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.tenant_id = tenant_id
    return ctx


@pytest.fixture
def tenant_id(env_credentials):
    tid = env_credentials("XERO_TENANT_ID")
    if not tid:
        pytest.skip("XERO_TENANT_ID not set — skipping integration tests")
    return tid


@pytest.fixture
async def first_contact_id(live_context, tenant_id):
    """Returns the first available contact ID, or skips if none exist."""
    result = await xero.execute_action(
        "find_contact_by_name",
        {"tenant_id": tenant_id, "contact_name": "Test"},
        live_context,
    )
    contacts = result.result.data.get("contacts", [])
    if not contacts:
        pytest.skip(
            "No contacts matching 'Test' in Xero org — skipping contact-dependent tests"
        )
    return contacts[0]["contact_id"]


@pytest.fixture
async def first_invoice_id(live_context, tenant_id):
    """Returns the first available invoice ID, or skips if none exist."""
    result = await xero.execute_action(
        "get_invoices", {"tenant_id": tenant_id, "page": 1}, live_context
    )
    invoices = result.result.data.get("Invoices", [])
    if not invoices:
        pytest.skip("No invoices in Xero org — skipping invoice-dependent tests")
    return invoices[0]["InvoiceID"]


@pytest.fixture
async def first_purchase_order_id(live_context, tenant_id):
    """Returns the first available purchase order ID, or skips if none exist."""
    result = await xero.execute_action(
        "get_purchase_orders", {"tenant_id": tenant_id}, live_context
    )
    pos = result.result.data.get("PurchaseOrders", [])
    if not pos:
        pytest.skip("No purchase orders in Xero org — skipping PO-dependent tests")
    return pos[0]["PurchaseOrderID"]


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


class TestGetAvailableConnections:
    async def test_returns_companies(self, live_context):
        result = await xero.execute_action(
            "get_available_connections", {}, live_context
        )

        data = result.result.data
        assert "companies" in data
        assert isinstance(data["companies"], list)

    async def test_companies_have_required_fields(self, live_context):
        result = await xero.execute_action(
            "get_available_connections", {}, live_context
        )

        companies = result.result.data.get("companies", [])
        if not companies:
            pytest.skip("No companies returned")
        for company in companies:
            assert "tenant_id" in company
            assert "company_name" in company


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


class TestFindContactByName:
    async def test_returns_contacts_list(self, live_context, tenant_id):
        result = await xero.execute_action(
            "find_contact_by_name",
            {"tenant_id": tenant_id, "contact_name": "a"},
            live_context,
        )

        data = result.result.data
        assert "contacts" in data
        assert isinstance(data["contacts"], list)

    async def test_filter_by_name(self, live_context, tenant_id, first_contact_id):
        result = await xero.execute_action(
            "find_contact_by_name",
            {"tenant_id": tenant_id, "contact_name": "Test"},
            live_context,
        )

        data = result.result.data
        assert "contacts" in data

    async def test_contact_has_required_fields(
        self, live_context, tenant_id, first_contact_id
    ):
        result = await xero.execute_action(
            "find_contact_by_name",
            {"tenant_id": tenant_id, "contact_name": "Test"},
            live_context,
        )

        contacts = result.result.data.get("contacts", [])
        if not contacts:
            pytest.skip("No contacts returned")
        contact = contacts[0]
        assert "contact_id" in contact
        assert "name" in contact


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class TestGetBalanceSheet:
    async def test_returns_report(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_balance_sheet", {"tenant_id": tenant_id}, live_context
        )

        data = result.result.data
        assert "Reports" in data
        assert isinstance(data["Reports"], list)
        assert len(data["Reports"]) > 0

    async def test_report_has_report_name(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_balance_sheet", {"tenant_id": tenant_id}, live_context
        )

        report = result.result.data["Reports"][0]
        assert report.get("ReportName") == "Balance Sheet"


class TestGetProfitAndLoss:
    async def test_returns_report(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_profit_and_loss", {"tenant_id": tenant_id}, live_context
        )

        data = result.result.data
        assert "Reports" in data
        assert isinstance(data["Reports"], list)
        assert len(data["Reports"]) > 0

    async def test_report_has_report_name(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_profit_and_loss", {"tenant_id": tenant_id}, live_context
        )

        report = result.result.data["Reports"][0]
        assert report.get("ReportName") == "Profit and Loss"


class TestGetTrialBalance:
    async def test_returns_report(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_trial_balance", {"tenant_id": tenant_id}, live_context
        )

        data = result.result.data
        assert "Reports" in data
        assert isinstance(data["Reports"], list)
        assert len(data["Reports"]) > 0

    async def test_report_has_report_name(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_trial_balance", {"tenant_id": tenant_id}, live_context
        )

        report = result.result.data["Reports"][0]
        assert report.get("ReportName") == "Trial Balance"


class TestGetAgedPayables:
    async def test_returns_report(self, live_context, tenant_id, first_contact_id):
        inputs = {"tenant_id": tenant_id, "contact_id": first_contact_id}
        result = await xero.execute_action("get_aged_payables", inputs, live_context)

        data = result.result.data
        assert "Reports" in data
        assert isinstance(data["Reports"], list)


class TestGetAgedReceivables:
    async def test_returns_report(self, live_context, tenant_id, first_contact_id):
        inputs = {"tenant_id": tenant_id, "contact_id": first_contact_id}
        result = await xero.execute_action("get_aged_receivables", inputs, live_context)

        data = result.result.data
        assert "Reports" in data
        assert isinstance(data["Reports"], list)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


class TestGetAccounts:
    async def test_returns_accounts(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_accounts", {"tenant_id": tenant_id}, live_context
        )

        data = result.result.data
        assert "Accounts" in data
        assert isinstance(data["Accounts"], list)

    async def test_accounts_have_required_fields(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_accounts", {"tenant_id": tenant_id}, live_context
        )

        accounts = result.result.data.get("Accounts", [])
        if not accounts:
            pytest.skip("No accounts in Xero org")

        account = accounts[0]
        assert "AccountID" in account
        assert "Name" in account
        assert "Type" in account


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


class TestGetInvoices:
    async def test_returns_invoices(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_invoices", {"tenant_id": tenant_id, "page": 1}, live_context
        )

        data = result.result.data
        assert "Invoices" in data
        assert isinstance(data["Invoices"], list)

    async def test_filter_by_status(self, live_context, tenant_id):
        inputs = {"tenant_id": tenant_id, "where": 'Status=="AUTHORISED"'}
        result = await xero.execute_action("get_invoices", inputs, live_context)

        data = result.result.data
        assert "Invoices" in data
        for invoice in data["Invoices"]:
            assert invoice["Status"] == "AUTHORISED"

    async def test_fetch_specific_invoice(
        self, live_context, tenant_id, first_invoice_id
    ):
        inputs = {"tenant_id": tenant_id, "invoice_id": first_invoice_id}
        result = await xero.execute_action("get_invoices", inputs, live_context)

        data = result.result.data
        assert "Invoices" in data
        assert data["Invoices"][0]["InvoiceID"] == first_invoice_id


class TestGetInvoicePdf:
    async def test_returns_pdf_file(self, live_context, tenant_id, first_invoice_id):
        inputs = {"tenant_id": tenant_id, "invoice_id": first_invoice_id}
        result = await xero.execute_action("get_invoice_pdf", inputs, live_context)

        data = result.result.data
        assert "file" in data
        file_obj = data["file"]
        assert "content" in file_obj
        assert "contentType" in file_obj
        assert "name" in file_obj
        assert file_obj["name"] == f"invoice_{first_invoice_id}.pdf"


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


class TestGetPayments:
    async def test_returns_payments(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_payments", {"tenant_id": tenant_id}, live_context
        )

        data = result.result.data
        assert "Payments" in data
        assert isinstance(data["Payments"], list)


# ---------------------------------------------------------------------------
# Bank Transactions
# ---------------------------------------------------------------------------


class TestGetBankTransactions:
    async def test_returns_bank_transactions(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_bank_transactions", {"tenant_id": tenant_id}, live_context
        )

        data = result.result.data
        assert "BankTransactions" in data
        assert isinstance(data["BankTransactions"], list)


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------


class TestGetAttachments:
    async def test_returns_attachments_for_invoice(
        self, live_context, tenant_id, first_invoice_id
    ):
        inputs = {
            "tenant_id": tenant_id,
            "endpoint": "Invoices",
            "guid": first_invoice_id,
        }
        result = await xero.execute_action("get_attachments", inputs, live_context)

        data = result.result.data
        assert "Attachments" in data
        assert isinstance(data["Attachments"], list)


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------


class TestGetPurchaseOrders:
    async def test_returns_purchase_orders(self, live_context, tenant_id):
        result = await xero.execute_action(
            "get_purchase_orders", {"tenant_id": tenant_id}, live_context
        )

        data = result.result.data
        assert "PurchaseOrders" in data
        assert isinstance(data["PurchaseOrders"], list)

    async def test_fetch_specific_purchase_order(
        self, live_context, tenant_id, first_purchase_order_id
    ):
        inputs = {"tenant_id": tenant_id, "purchase_order_id": first_purchase_order_id}
        result = await xero.execute_action("get_purchase_orders", inputs, live_context)

        data = result.result.data
        assert "PurchaseOrders" in data
        assert data["PurchaseOrders"][0]["PurchaseOrderID"] == first_purchase_order_id


class TestGetPurchaseOrderHistory:
    async def test_returns_history(
        self, live_context, tenant_id, first_purchase_order_id
    ):
        inputs = {"tenant_id": tenant_id, "purchase_order_id": first_purchase_order_id}
        result = await xero.execute_action(
            "get_purchase_order_history", inputs, live_context
        )

        data = result.result.data
        assert "HistoryRecords" in data
        assert isinstance(data["HistoryRecords"], list)


# ---------------------------------------------------------------------------
# Write / destructive tests — skipped by default
# ---------------------------------------------------------------------------


class TestCreateUpdateDeletePurchaseOrder:
    @pytest.mark.destructive
    async def test_full_purchase_order_lifecycle(
        self, live_context, tenant_id, first_contact_id
    ):
        contact = {"ContactID": first_contact_id}
        line_items = [
            {
                "Description": "Integration test item",
                "Quantity": 1,
                "UnitAmount": 10.00,
                "AccountCode": "200",
            }
        ]

        # Create
        create_result = await xero.execute_action(
            "create_purchase_order",
            {
                "tenant_id": tenant_id,
                "contact": contact,
                "line_items": line_items,
                "status": "DRAFT",
            },
            live_context,
        )
        data = assert_action_success(create_result)
        pos = data.get("PurchaseOrders", [])
        assert pos, "Expected PurchaseOrders in create response"
        po_id = pos[0]["PurchaseOrderID"]

        # Update
        update_result = await xero.execute_action(
            "update_purchase_order",
            {
                "tenant_id": tenant_id,
                "purchase_order_id": po_id,
                "reference": "integration-test",
            },
            live_context,
        )
        assert assert_action_success(update_result).get("PurchaseOrders")

        # Add note
        note_result = await xero.execute_action(
            "add_note_to_purchase_order",
            {
                "tenant_id": tenant_id,
                "purchase_order_id": po_id,
                "note": "Integration test note",
            },
            live_context,
        )
        assert "HistoryRecords" in assert_action_success(note_result)

        # History
        history_result = await xero.execute_action(
            "get_purchase_order_history",
            {"tenant_id": tenant_id, "purchase_order_id": po_id},
            live_context,
        )
        assert "HistoryRecords" in assert_action_success(history_result)

        # Delete
        delete_result = await xero.execute_action(
            "delete_purchase_order",
            {"tenant_id": tenant_id, "purchase_order_id": po_id},
            live_context,
        )
        deleted_data = assert_action_success(delete_result)
        assert deleted_data.get("PurchaseOrders", [])[0]["Status"] == "DELETED"


class TestCreateUpdateSalesInvoice:
    @pytest.mark.destructive
    async def test_create_and_update_draft_invoice(
        self, live_context, tenant_id, first_contact_id
    ):
        contact = {"ContactID": first_contact_id}
        line_items = [
            {
                "Description": "Integration test service",
                "Quantity": 1,
                "UnitAmount": 50.00,
                "AccountCode": "200",
            }
        ]

        create_result = await xero.execute_action(
            "create_sales_invoice",
            {
                "tenant_id": tenant_id,
                "contact": contact,
                "line_items": line_items,
                "status": "DRAFT",
            },
            live_context,
        )
        create_data = assert_action_success(create_result)
        invoices = create_data.get("Invoices", [])
        assert invoices
        invoice_id = invoices[0]["InvoiceID"]
        assert invoices[0]["Type"] == "ACCREC"

        update_result = await xero.execute_action(
            "update_sales_invoice",
            {
                "tenant_id": tenant_id,
                "invoice_id": invoice_id,
                "reference": "integration-test",
            },
            live_context,
        )
        assert assert_action_success(update_result).get("Invoices")


class TestCreateUpdatePurchaseBill:
    @pytest.mark.destructive
    async def test_create_and_update_draft_bill(
        self, live_context, tenant_id, first_contact_id
    ):
        contact = {"ContactID": first_contact_id}
        line_items = [
            {
                "Description": "Integration test expense",
                "Quantity": 1,
                "UnitAmount": 25.00,
                "AccountCode": "300",
            }
        ]

        create_result = await xero.execute_action(
            "create_purchase_bill",
            {
                "tenant_id": tenant_id,
                "contact": contact,
                "line_items": line_items,
                "status": "DRAFT",
            },
            live_context,
        )
        create_data = assert_action_success(create_result)
        invoices = create_data.get("Invoices", [])
        assert invoices
        bill_id = invoices[0]["InvoiceID"]
        assert invoices[0]["Type"] == "ACCPAY"

        update_result = await xero.execute_action(
            "update_purchase_bill",
            {
                "tenant_id": tenant_id,
                "invoice_id": bill_id,
                "reference": "integration-test",
            },
            live_context,
        )
        assert assert_action_success(update_result).get("Invoices")
