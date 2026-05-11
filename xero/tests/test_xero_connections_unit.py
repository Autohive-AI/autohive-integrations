import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402
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


SAMPLE_CONNECTIONS = [
    {"tenantId": "tenant-001", "tenantName": "Acme Corp", "tenantType": "ORGANISATION"},
    {"tenantId": "tenant-002", "tenantName": "Beta Ltd", "tenantType": "ORGANISATION"},
]


# ---- get_available_connections ----


class TestGetAvailableConnections:
    @pytest.mark.asyncio
    async def test_returns_companies(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CONNECTIONS)

        result = await xero.execute_action("get_available_connections", {}, mock_context)

        assert result.result.data["companies"][0]["tenant_id"] == "tenant-001"
        assert result.result.data["companies"][0]["company_name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_returns_all_companies(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CONNECTIONS)

        result = await xero.execute_action("get_available_connections", {}, mock_context)

        assert len(result.result.data["companies"]) == 2

    @pytest.mark.asyncio
    async def test_calls_connections_endpoint(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=SAMPLE_CONNECTIONS)

        await xero.execute_action("get_available_connections", {}, mock_context)

        call_args = mock_context.fetch.call_args
        assert "api.xero.com/connections" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_empty_connections_returns_action_error(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        result = await xero.execute_action("get_available_connections", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_fetch_exception_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection failed")

        result = await xero.execute_action("get_available_connections", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Connection failed" in result.result.message

    @pytest.mark.asyncio
    async def test_filters_connections_missing_name_or_id(self, mock_context):
        connections = [
            {"tenantId": "tenant-001", "tenantName": "Acme Corp"},
            {"tenantId": None, "tenantName": "Missing ID"},
            {"tenantId": "tenant-003", "tenantName": None},
        ]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=connections)

        result = await xero.execute_action("get_available_connections", {}, mock_context)

        assert len(result.result.data["companies"]) == 1
        assert result.result.data["companies"][0]["tenant_id"] == "tenant-001"


# ---- find_contact_by_name ----


class TestFindContactByName:
    @pytest.mark.asyncio
    async def test_returns_contacts(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Contacts": [
                        {
                            "ContactID": "c-001",
                            "Name": "Acme Corp",
                            "EmailAddress": "info@acme.com",
                            "ContactStatus": "ACTIVE",
                        }
                    ]
                }
            )

            result = await xero.execute_action(
                "find_contact_by_name",
                {"tenant_id": "t-001", "contact_name": "Acme"},
                mock_context,
            )

        assert result.result.data["contacts"][0]["contact_id"] == "c-001"
        assert result.result.data["contacts"][0]["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_calls_correct_url_with_filter(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value={"Contacts": []})

            await xero.execute_action(
                "find_contact_by_name",
                {"tenant_id": "t-001", "contact_name": "Acme"},
                mock_context,
            )

            call_args = mock_limiter.make_request.call_args
            assert "api.xero.com/api.xro/2.0/Contacts" in call_args.args[1]
            assert "Acme" in call_args.kwargs["params"]["where"]

    @pytest.mark.asyncio
    async def test_empty_contacts_returns_empty_list(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(return_value={"Contacts": None})

            result = await xero.execute_action(
                "find_contact_by_name",
                {"tenant_id": "t-001", "contact_name": "Acme"},
                mock_context,
            )

        assert result.result.data["contacts"] == []

    @pytest.mark.asyncio
    async def test_rate_limit_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                side_effect=XeroRateLimitExceededException(requested_delay=120, max_wait_time=60, tenant_id="t-001")
            )

            result = await xero.execute_action(
                "find_contact_by_name",
                {"tenant_id": "t-001", "contact_name": "Acme"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "rate limit" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_general_exception_returns_action_error(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(side_effect=Exception("Network error"))

            result = await xero.execute_action(
                "find_contact_by_name",
                {"tenant_id": "t-001", "contact_name": "Acme"},
                mock_context,
            )

        assert result.type == ResultType.ACTION_ERROR
        assert "Network error" in result.result.message

    @pytest.mark.asyncio
    async def test_response_shape_includes_contact_fields(self, mock_context):
        with patch.object(_mod, "rate_limiter") as mock_limiter:
            mock_limiter.make_request = AsyncMock(
                return_value={
                    "Contacts": [
                        {
                            "ContactID": "c-001",
                            "Name": "Acme Corp",
                            "EmailAddress": "info@acme.com",
                            "FirstName": "John",
                            "LastName": "Doe",
                            "ContactStatus": "ACTIVE",
                        }
                    ]
                }
            )

            result = await xero.execute_action(
                "find_contact_by_name",
                {"tenant_id": "t-001", "contact_name": "Acme"},
                mock_context,
            )

        contact = result.result.data["contacts"][0]
        assert "contact_id" in contact
        assert "name" in contact
        assert "email_address" in contact
        assert "first_name" in contact
        assert "last_name" in contact
