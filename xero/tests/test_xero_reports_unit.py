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

_spec = importlib.util.spec_from_file_location(
    "xero_mod", os.path.join(_parent, "xero.py")
)
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


SAMPLE_REPORT = {
    "Reports": [
        {
            "ReportID": "AgedPayablesByContact",
            "ReportName": "Aged Payables",
            "ReportDate": "2024-01-31",
            "Rows": [],
        }
    ]
}


# ---- get_aged_payables ----


class TestGetAgedPayables:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            result = await xero.execute_action(
                "get_aged_payables",
                {"tenant_id": "t-001", "contact_id": "c-001"},
                mock_context,
            )

        assert "Reports" in result.result.data

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            await xero.execute_action(
                "get_aged_payables",
                {"tenant_id": "t-001", "contact_id": "c-001"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "AgedPayablesByContact" in call_args.args[1]
            assert call_args.kwargs["params"]["contactId"] == "c-001"

    @pytest.mark.asyncio
    async def test_optional_date_param(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            await xero.execute_action(
                "get_aged_payables",
                {"tenant_id": "t-001", "contact_id": "c-001", "date": "2024-01-31"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert call_args.kwargs["params"]["date"] == "2024-01-31"

    @pytest.mark.asyncio
    async def test_rate_limit_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(120, 60, "t-001")
            )

            result = await xero.execute_action(
                "get_aged_payables",
                {"tenant_id": "t-001", "contact_id": "c-001"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "rate limit" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("API error"))

            result = await xero.execute_action(
                "get_aged_payables",
                {"tenant_id": "t-001", "contact_id": "c-001"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "API error" in result.result.message


# ---- get_aged_receivables ----


class TestGetAgedReceivables:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            result = await xero.execute_action(
                "get_aged_receivables",
                {"tenant_id": "t-001", "contact_id": "c-001"},
                mock_context,
            )

        assert "Reports" in result.result.data

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            await xero.execute_action(
                "get_aged_receivables",
                {"tenant_id": "t-001", "contact_id": "c-001"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "AgedReceivablesByContact" in call_args.args[1]

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Server error"))

            result = await xero.execute_action(
                "get_aged_receivables",
                {"tenant_id": "t-001", "contact_id": "c-001"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_balance_sheet ----


class TestGetBalanceSheet:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            result = await xero.execute_action(
                "get_balance_sheet", {"tenant_id": "t-001"}, mock_context
            )

        assert "Reports" in result.result.data

    @pytest.mark.asyncio
    async def test_calls_balance_sheet_endpoint(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            await xero.execute_action(
                "get_balance_sheet", {"tenant_id": "t-001"}, mock_context
            )

            call_args = mock_limiter.make_request.call_args
            assert "BalanceSheet" in call_args.args[1]

    @pytest.mark.asyncio
    async def test_optional_periods_param(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            await xero.execute_action(
                "get_balance_sheet", {"tenant_id": "t-001", "periods": 3}, mock_context
            )

            call_args = mock_limiter.make_request.call_args
            assert call_args.kwargs["params"]["periods"] == "3"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Timeout"))

            result = await xero.execute_action(
                "get_balance_sheet", {"tenant_id": "t-001"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_profit_and_loss ----


class TestGetProfitAndLoss:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            result = await xero.execute_action(
                "get_profit_and_loss", {"tenant_id": "t-001"}, mock_context
            )

        assert "Reports" in result.result.data

    @pytest.mark.asyncio
    async def test_calls_profit_loss_endpoint(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            await xero.execute_action(
                "get_profit_and_loss", {"tenant_id": "t-001"}, mock_context
            )

            call_args = mock_limiter.make_request.call_args
            assert "ProfitAndLoss" in call_args.args[1]

    @pytest.mark.asyncio
    async def test_optional_date_range_params(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            await xero.execute_action(
                "get_profit_and_loss",
                {
                    "tenant_id": "t-001",
                    "from_date": "2024-01-01",
                    "to_date": "2024-12-31",
                },
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert call_args.kwargs["params"]["fromDate"] == "2024-01-01"
            assert call_args.kwargs["params"]["toDate"] == "2024-12-31"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Auth error"))

            result = await xero.execute_action(
                "get_profit_and_loss", {"tenant_id": "t-001"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_trial_balance ----


class TestGetTrialBalance:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            result = await xero.execute_action(
                "get_trial_balance", {"tenant_id": "t-001"}, mock_context
            )

        assert "Reports" in result.result.data

    @pytest.mark.asyncio
    async def test_payments_only_param(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value=SAMPLE_REPORT)

            await xero.execute_action(
                "get_trial_balance",
                {"tenant_id": "t-001", "payments_only": True},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert call_args.kwargs["params"]["paymentsOnly"] == "true"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Xero error"))

            result = await xero.execute_action(
                "get_trial_balance", {"tenant_id": "t-001"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_accounts ----


class TestGetAccounts:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Accounts": [{"AccountID": "a-001", "Code": "200", "Name": "Sales"}]
                }
            )

            result = await xero.execute_action(
                "get_accounts", {"tenant_id": "t-001"}, mock_context
            )

        assert "Accounts" in result.result.data

    @pytest.mark.asyncio
    async def test_where_and_order_params(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value={"Accounts": []})

            await xero.execute_action(
                "get_accounts",
                {"tenant_id": "t-001", "where": 'Status="ACTIVE"', "order": "Code ASC"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert call_args.kwargs["params"]["where"] == 'Status="ACTIVE"'
            assert call_args.kwargs["params"]["order"] == "Code ASC"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("API error"))

            result = await xero.execute_action(
                "get_accounts", {"tenant_id": "t-001"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR


# ---- get_payments ----


class TestGetPayments:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={"Payments": [{"PaymentID": "p-001", "Amount": 500.0}]}
            )

            result = await xero.execute_action(
                "get_payments", {"tenant_id": "t-001"}, mock_context
            )

        assert "Payments" in result.result.data

    @pytest.mark.asyncio
    async def test_pagination_params(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value={"Payments": []})

            await xero.execute_action(
                "get_payments",
                {"tenant_id": "t-001", "page": 2, "pageSize": 50},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert call_args.kwargs["params"]["page"] == "2"
            assert call_args.kwargs["params"]["pageSize"] == "50"

    @pytest.mark.asyncio
    async def test_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Timeout"))

            result = await xero.execute_action(
                "get_payments", {"tenant_id": "t-001"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_rate_limit_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(90, 60, "t-001")
            )

            result = await xero.execute_action(
                "get_payments", {"tenant_id": "t-001"}, mock_context
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "rate limit" in result.result.message.lower()
