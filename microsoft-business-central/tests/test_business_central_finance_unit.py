"""Finance request contracts and preservation of accounting semantics."""

from urllib.parse import parse_qs, urlsplit

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from businesscentral import base_url, businesscentral

pytestmark = pytest.mark.unit
COMPANY = "22222222-2222-2222-2222-222222222222"
RECORD = "33333333-3333-3333-3333-333333333333"
INPUTS = {
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "environment": "Sandbox",
    "company_id": COMPANY,
}
PERIOD = {"start_date": "2026-10-01", "end_date": "2026-10-31"}
GETS = {"get_customer", "get_sales_invoice", "get_receivables_aging", "get_payables_aging"}
CASES = [
    ("list_customers", {}, "customers"),
    ("get_customer", {"customer_id": RECORD}, f"customers({RECORD})"),
    ("list_sales_invoices", {}, "salesInvoices"),
    ("get_sales_invoice", {"sales_invoice_id": RECORD}, f"salesInvoices({RECORD})"),
    ("list_sales_invoice_lines", {"sales_invoice_id": RECORD}, f"salesInvoices({RECORD})/salesInvoiceLines"),
    ("list_sales_credit_memos", {}, "salesCreditMemos"),
    ("list_accounts", {}, "accounts"),
    ("list_general_ledger_entries", {}, "generalLedgerEntries"),
    ("list_dimensions", {}, "dimensions"),
    ("list_dimension_values", {"dimension_id": RECORD}, f"dimensions({RECORD})/dimensionValues"),
    (
        "list_general_ledger_entry_dimensions",
        {"general_ledger_entry_id": RECORD},
        f"generalLedgerEntries({RECORD})/dimensionSetLines",
    ),
    ("get_receivables_aging", {"customer_id": RECORD}, f"agedAccountsReceivables({RECORD})"),
    ("get_payables_aging", {"vendor_id": RECORD}, f"agedAccountsPayables({RECORD})"),
    ("get_trial_balance", PERIOD, "trialBalances"),
    ("get_income_statement", PERIOD, "incomeStatements"),
]


def response(data):
    return FetchResponse(status=200, headers={}, data=data)


def success(result):
    assert result.type == ResultType.ACTION, result.result
    return result.result.data


@pytest.mark.parametrize("action,extra,path", CASES)
async def test_finance_routes_and_unmodified_response(mock_context, action, extra, path):
    record = {
        "id": RECORD,
        "currencyCode": "AUD",
        "balanceDue": 450.25,
        "remainingAmount": 125.25,
        "status": "Open",
        "totalDebit": "1,250.00",
    }
    mock_context.request.return_value = response(record if action in GETS else {"value": [record]})
    data = success(await businesscentral.execute_action(action, dict(INPUTS, **extra), mock_context))
    assert (data["record"] if action in GETS else data["records"][0]) == record
    call = mock_context.request.await_args
    assert call.args[0].split("?", 1)[0] == f"{base_url(INPUTS)}/{path}"
    assert call.kwargs["method"] == "GET"
    if action in GETS:
        assert call.kwargs["params"] is None


@pytest.mark.parametrize("action,extra,path", CASES)
async def test_finance_permission_failures_are_sanitized(mock_context, action, extra, path):
    mock_context.request.return_value = FetchResponse(status=403, headers={}, data={"error": "private-accounting-data"})
    result = await businesscentral.execute_action(action, dict(INPUTS, **extra), mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "permissions" in result.result.message
    assert "private-accounting-data" not in result.result.message


@pytest.mark.parametrize("action,extra,path", [case for case in CASES if case[0] not in GETS])
async def test_finance_collections_follow_validated_resource_paging(mock_context, action, extra, path):
    link = f"{base_url(INPUTS)}/{path}?$skiptoken=finance%2Bnext"
    mock_context.request.return_value = response({"value": [], "@odata.nextLink": link})
    data = success(await businesscentral.execute_action(action, dict(INPUTS, **extra), mock_context))
    assert data["has_more"] and data["next_link"] == link
    mock_context.request.return_value = response({"value": []})
    data = success(await businesscentral.execute_action(action, dict(INPUTS, **extra, next_link=link), mock_context))
    assert mock_context.request.await_args.args[0] == link
    assert mock_context.request.await_args.kwargs["params"] is None
    assert data["count"] == 0 and not data["has_more"]


@pytest.mark.parametrize(
    "action,extra,expected",
    [
        ("list_customers", {"customer_number": "AC'1"}, "number eq 'AC''1'"),
        ("list_accounts", {"account_number": "4000"}, "number eq '4000'"),
        (
            "list_sales_credit_memos",
            dict(PERIOD, customer_id=RECORD),
            f"customerId eq {RECORD} and creditMemoDate ge 2026-10-01 and creditMemoDate le 2026-10-31",
        ),
        (
            "list_general_ledger_entries",
            dict(PERIOD, account_id=RECORD, document_number="INV'1"),
            f"accountId eq {RECORD} and documentNumber eq 'INV''1' and postingDate ge 2026-10-01 "
            "and postingDate le 2026-10-31",
        ),
        ("get_trial_balance", PERIOD, "dateFilter ge 2026-10-01 and dateFilter le 2026-10-31"),
        ("get_income_statement", PERIOD, "dateFilter ge 2026-10-01 and dateFilter le 2026-10-31"),
        (
            "list_sales_invoices",
            dict(PERIOD, customer_id=RECORD),
            f"customerId eq {RECORD} and postingDate ge 2026-10-01 and postingDate le 2026-10-31",
        ),
        ("list_sales_invoices", {"status": "Draft"}, "status eq 'Draft'"),
        ("list_sales_invoices", {"status": "In Review"}, "status eq 'In Review'"),
        ("list_sales_invoices", {"status": " "}, "status eq ' '"),
        (
            "list_sales_invoices",
            {"outstanding_only": True, "due_before": "2026-11-01"},
            "remainingAmount gt 0 and status eq 'Open' and dueDate lt 2026-11-01",
        ),
        (
            "list_sales_invoices",
            {"outstanding_only": True, "status": "Open"},
            "remainingAmount gt 0 and status eq 'Open'",
        ),
    ],
)
async def test_finance_filters(mock_context, action, extra, expected):
    mock_context.request.return_value = response({"value": []})
    success(await businesscentral.execute_action(action, dict(INPUTS, **extra), mock_context))
    assert parse_qs(urlsplit(mock_context.request.await_args.args[0]).query)["$filter"][0] == expected


@pytest.mark.parametrize(
    "action,extra",
    [
        ("list_sales_invoices", {"outstanding_only": True, "status": "Paid"}),
        ("list_sales_invoices", {"outstanding_only": True, "status": "Draft"}),
        ("list_sales_invoices", {"outstanding_only": True, "status": "In Review"}),
        ("list_sales_invoices", {"due_before": "2026-02-30"}),
        ("list_sales_invoices", {"start_date": "2026-10-31", "end_date": "2026-10-01"}),
        ("list_sales_credit_memos", {"start_date": "2026-10-31", "end_date": "2026-10-01"}),
        ("list_dimension_values", {"dimension_id": "not-a-guid"}),
        ("get_trial_balance", {"start_date": "2026-10-01"}),
        ("get_income_statement", {"start_date": "2026-10-31", "end_date": "2026-10-01"}),
    ],
)
async def test_invalid_finance_inputs_do_not_fetch(mock_context, action, extra):
    result = await businesscentral.execute_action(action, dict(INPUTS, **extra), mock_context)
    assert result.type in (ResultType.VALIDATION_ERROR, ResultType.ACTION_ERROR)
    mock_context.request.assert_not_awaited()


@pytest.mark.parametrize("action", ["get_trial_balance", "get_income_statement"])
@pytest.mark.parametrize("start,end", [("", ""), ("", "2026-10-31"), ("2026-10-01", ""), (" ", "2026-10-31")])
@pytest.mark.parametrize("continuation", [False, True])
async def test_financial_reports_reject_empty_periods_before_fetch(mock_context, action, start, end, continuation):
    inputs = dict(INPUTS, start_date=start, end_date=end)
    if continuation:
        resource = "trialBalances" if action == "get_trial_balance" else "incomeStatements"
        inputs["next_link"] = f"{base_url(INPUTS)}/{resource}?$skiptoken=next"
    result = await businesscentral.execute_action(action, inputs, mock_context)
    assert result.type in (ResultType.VALIDATION_ERROR, ResultType.ACTION_ERROR)
    mock_context.request.assert_not_awaited()


@pytest.mark.parametrize("action,key", [("get_receivables_aging", "customer_id"), ("get_payables_aging", "vendor_id")])
async def test_aging_retains_report_date_periods_currency_and_credits(mock_context, action, key):
    record = {
        key.replace("_id", "Id"): RECORD,
        "currencyCode": "",
        "balanceDue": -20,
        "currentAmount": -50,
        "period1Amount": 30,
        "period2Amount": 0,
        "period3Amount": 0,
        "period1Label": "1-30 days",
        "agedAsOfDate": "2026-11-01",
        "periodLengthFilter": "30D",
    }
    mock_context.request.return_value = response(record)
    data = success(await businesscentral.execute_action(action, dict(INPUTS, **{key: RECORD}), mock_context))
    assert data["record"] == record
    assert mock_context.request.await_args.kwargs["params"] is None


async def test_income_statement_preserves_headers_and_subtotals(mock_context):
    rows = [
        {"lineType": "header", "display": "Revenue", "netChange": 0, "indentation": 0},
        {"lineType": "detail", "display": "Service income", "netChange": 1200, "indentation": 1},
        {"lineType": "total", "display": "Total revenue", "netChange": 1200, "indentation": 0},
    ]
    mock_context.request.return_value = response({"value": rows})
    data = success(await businesscentral.execute_action("get_income_statement", dict(INPUTS, **PERIOD), mock_context))
    assert data["records"] == rows


async def test_dimensions_preserve_configured_mapping_without_assuming_branch_codes(mock_context):
    record = {"parentId": RECORD, "code": "COSTCENTRE", "valueCode": "CC10", "valueDisplayName": "Example centre"}
    mock_context.request.return_value = response({"value": [record]})
    result = await businesscentral.execute_action(
        "list_general_ledger_entry_dimensions", dict(INPUTS, general_ledger_entry_id=RECORD), mock_context
    )
    assert success(result)["records"] == [record]
