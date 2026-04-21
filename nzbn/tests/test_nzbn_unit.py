"""
Unit tests for NZBN integration.

These tests use mocks — no real API credentials or network calls required.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from autohive_integrations_sdk import FetchResponse, ResultType  # noqa: E402

from nzbn.nzbn import (
    nzbn,
    _get_cached_token,
    _cache_token,
    _token_cache,
    make_request,
    get_headers,
)

pytestmark = pytest.mark.unit

TEST_NZBN = "9429041525746"


@pytest.fixture
def mock_context():
    """Create a mock ExecutionContext."""
    context = MagicMock()
    context.auth = {"credentials": {}}
    context.fetch = AsyncMock()
    return context


@pytest.fixture(autouse=True)
def clear_token_cache():
    """Clear the token cache before each test."""
    _token_cache.clear()
    yield
    _token_cache.clear()


# =============================================================================
# Token Cache
# =============================================================================


class TestTokenCache:
    """Test token caching helpers directly."""

    def test_cache_and_retrieve_token(self):
        _cache_token("test_scope", "tok_abc", 3600)
        assert _get_cached_token("test_scope") == "tok_abc"

    def test_get_cached_token_returns_none_when_empty(self):
        assert _get_cached_token("nonexistent") is None

    def test_get_cached_token_returns_none_when_expired(self):
        _cache_token("test_scope", "tok_old", 0)
        assert _get_cached_token("test_scope") is None

    def test_get_cached_token_returns_none_within_buffer(self):
        # Token that expires in 30 seconds — within the 60-second buffer
        _cache_token("test_scope", "tok_buf", 30)
        assert _get_cached_token("test_scope") is None

    def test_cache_overwrites_existing(self):
        _cache_token("scope", "tok_first", 3600)
        _cache_token("scope", "tok_second", 3600)
        assert _get_cached_token("scope") == "tok_second"


# =============================================================================
# Input Validation
# =============================================================================


class TestInputValidation:
    """Missing required fields return error without making API calls.

    The SDK may raise ValidationError or the handler may return an error
    result — either way, the missing field is rejected.
    """

    async def _assert_rejects_missing_field(self, mock_context, action, inputs=None):
        """Assert that calling an action with missing required fields fails."""
        result = await nzbn.execute_action(action, inputs or {}, mock_context)
        assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)

    @pytest.mark.asyncio
    async def test_search_entities_missing_search_term(self, mock_context):
        await self._assert_rejects_missing_field(mock_context, "search_entities")

    @pytest.mark.asyncio
    async def test_get_entity_missing_nzbn(self, mock_context):
        await self._assert_rejects_missing_field(mock_context, "get_entity")

    @pytest.mark.asyncio
    async def test_get_entity_summary_missing_nzbn(self, mock_context):
        await self._assert_rejects_missing_field(mock_context, "get_entity_summary")

    @pytest.mark.asyncio
    async def test_get_entity_addresses_missing_nzbn(self, mock_context):
        await self._assert_rejects_missing_field(mock_context, "get_entity_addresses")

    @pytest.mark.asyncio
    async def test_get_entity_roles_missing_nzbn(self, mock_context):
        await self._assert_rejects_missing_field(mock_context, "get_entity_roles")

    @pytest.mark.asyncio
    async def test_get_entity_trading_names_missing_nzbn(self, mock_context):
        await self._assert_rejects_missing_field(mock_context, "get_entity_trading_names")

    @pytest.mark.asyncio
    async def test_get_company_details_missing_nzbn(self, mock_context):
        await self._assert_rejects_missing_field(mock_context, "get_company_details")

    @pytest.mark.asyncio
    async def test_get_entity_gst_numbers_missing_nzbn(self, mock_context):
        await self._assert_rejects_missing_field(mock_context, "get_entity_gst_numbers")

    @pytest.mark.asyncio
    async def test_get_entity_industry_classifications_missing_nzbn(self, mock_context):
        await self._assert_rejects_missing_field(mock_context, "get_entity_industry_classifications")

    @pytest.mark.asyncio
    async def test_get_changes_missing_event_type(self, mock_context):
        await self._assert_rejects_missing_field(mock_context, "get_changes")


# =============================================================================
# Action Tests (patching make_request)
# =============================================================================


class TestSearchEntities:
    """Test search_entities action."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_basic_search(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {
                "items": [{"entityName": "Xero Limited", "nzbn": TEST_NZBN}],
                "totalItems": 1,
                "page": 0,
                "pageSize": 25,
            },
        }

        result = await nzbn.execute_action("search_entities", {"search_term": "Xero"}, mock_context)
        data = result.result.data

        assert data["result"] is True
        assert data["totalItems"] == 1
        assert data["items"][0]["entityName"] == "Xero Limited"
        mock_make_request.assert_called_once_with(mock_context, "GET", "/entities", {"search-term": "Xero"})

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_search_with_filters(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {"items": [], "totalItems": 0, "page": 0, "pageSize": 3},
        }

        inputs = {
            "search_term": "Limited",
            "entity_type": "LTD",
            "entity_status": "Registered",
            "page_size": 3,
            "page": 1,
        }
        result = await nzbn.execute_action("search_entities", inputs, mock_context)
        data = result.result.data

        assert data["result"] is True
        call_args = mock_make_request.call_args
        params = call_args[0][3]
        assert params["search-term"] == "Limited"
        assert params["entity-type"] == "LTD"
        assert params["entity-status"] == "Registered"
        assert params["page-size"] == 3
        assert params["page"] == 1

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_search_api_error(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": False,
            "error": "Bad request - validation failed",
        }

        result = await nzbn.execute_action("search_entities", {"search_term": "test"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Bad request" in result.result.message


class TestGetEntity:
    """Test get_entity action."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_get_entity_success(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {
                "nzbn": TEST_NZBN,
                "entityName": "Xero Limited",
                "entityStatusCode": "50",
            },
        }

        result = await nzbn.execute_action("get_entity", {"nzbn": TEST_NZBN}, mock_context)
        data = result.result.data

        assert data["result"] is True
        assert data["entity"]["entityName"] == "Xero Limited"
        mock_make_request.assert_called_once_with(mock_context, "GET", f"/entities/{TEST_NZBN}")

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_get_entity_not_found(self, mock_make_request, mock_context):
        mock_make_request.return_value = {"success": False, "error": "Entity not found"}

        result = await nzbn.execute_action("get_entity", {"nzbn": "0000000000000"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message.lower()


class TestGetEntitySummary:
    """Test get_entity_summary action."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_summary_returns_three_fields(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {
                "nzbn": TEST_NZBN,
                "entityName": "Xero Limited",
                "entityStatusCode": "50",
                "addresses": {
                    "addressList": [
                        {
                            "addressType": "REGISTERED",
                            "address1": "19-23 Taranaki Street",
                            "address3": "Wellington",
                            "postCode": "6011",
                        }
                    ]
                },
                "roles": {"roleList": [{"roleName": "Director"}]},
            },
        }

        result = await nzbn.execute_action("get_entity_summary", {"nzbn": TEST_NZBN}, mock_context)
        data = result.result.data

        assert data["result"] is True
        summary = data["summary"]
        assert len(summary) == 3
        assert summary["nzbn"] == TEST_NZBN
        assert summary["entityName"] == "Xero Limited"
        assert "19-23 Taranaki Street" in summary["registeredOffice"]
        assert "6011" in summary["registeredOffice"]

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_summary_no_registered_address(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {
                "nzbn": TEST_NZBN,
                "entityName": "Test Co",
                "addresses": {"addressList": []},
            },
        }

        result = await nzbn.execute_action("get_entity_summary", {"nzbn": TEST_NZBN}, mock_context)
        data = result.result.data

        assert data["result"] is True
        assert data["summary"]["registeredOffice"] == ""


class TestGetEntityAddresses:
    """Test get_entity_addresses action."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_addresses_success(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {
                "items": [
                    {"addressType": "REGISTERED", "address1": "123 Main St"},
                    {"addressType": "POSTAL", "address1": "PO Box 100"},
                ]
            },
        }

        result = await nzbn.execute_action("get_entity_addresses", {"nzbn": TEST_NZBN}, mock_context)
        data = result.result.data

        assert data["result"] is True
        assert len(data["addresses"]) == 2

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_addresses_with_type_filter(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {"items": [{"addressType": "REGISTERED", "address1": "123 Main St"}]},
        }

        await nzbn.execute_action(
            "get_entity_addresses",
            {"nzbn": TEST_NZBN, "address_type": "RegisteredOffice"},
            mock_context,
        )

        call_args = mock_make_request.call_args
        params = call_args[0][3]
        assert params["address-type"] == "RegisteredOffice"


class TestGetEntityRoles:
    """Test get_entity_roles action."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_roles_success(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {"items": [{"roleName": "Director", "firstName": "Jane"}]},
        }

        result = await nzbn.execute_action("get_entity_roles", {"nzbn": TEST_NZBN}, mock_context)
        data = result.result.data

        assert data["result"] is True
        assert len(data["roles"]) == 1
        assert data["roles"][0]["roleName"] == "Director"


class TestGetEntityTradingNames:
    """Test get_entity_trading_names action."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_trading_names_success(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {"items": [{"name": "Xero NZ"}]},
        }

        result = await nzbn.execute_action("get_entity_trading_names", {"nzbn": TEST_NZBN}, mock_context)
        data = result.result.data

        assert data["result"] is True
        assert len(data["tradingNames"]) == 1


class TestGetCompanyDetails:
    """Test get_company_details action."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_company_details_success(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {"companyNumber": "1234567", "annualReturnFilingMonth": 3},
        }

        result = await nzbn.execute_action("get_company_details", {"nzbn": TEST_NZBN}, mock_context)
        data = result.result.data

        assert data["result"] is True
        assert data["companyDetails"]["companyNumber"] == "1234567"


class TestGetEntityGstNumbers:
    """Test get_entity_gst_numbers action."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_gst_numbers_success(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {"items": [{"gstNumber": "123-456-789"}]},
        }

        result = await nzbn.execute_action("get_entity_gst_numbers", {"nzbn": TEST_NZBN}, mock_context)
        data = result.result.data

        assert data["result"] is True
        assert len(data["gstNumbers"]) == 1


class TestGetEntityIndustryClassifications:
    """Test get_entity_industry_classifications action."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_industry_classifications_success(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {
                "items": [
                    {
                        "classificationCode": "L631",
                        "classificationDescription": "Software",
                    }
                ]
            },
        }

        result = await nzbn.execute_action("get_entity_industry_classifications", {"nzbn": TEST_NZBN}, mock_context)
        data = result.result.data

        assert data["result"] is True
        assert len(data["industryClassifications"]) == 1
        assert data["industryClassifications"][0]["classificationCode"] == "L631"


class TestGetChanges:
    """Test get_changes action."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_get_changes_success(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {
                "items": [{"nzbn": TEST_NZBN, "changeEventType": "NewRegistration"}],
                "totalItems": 1,
            },
        }

        result = await nzbn.execute_action("get_changes", {"change_event_type": "NewRegistration"}, mock_context)
        data = result.result.data

        assert data["result"] is True
        assert len(data["changes"]) == 1
        assert data["totalItems"] == 1

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_get_changes_with_date_filters(self, mock_make_request, mock_context):
        mock_make_request.return_value = {
            "success": True,
            "data": {"items": [], "totalItems": 0},
        }

        inputs = {
            "change_event_type": "NameChange",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "page_size": 10,
            "page": 0,
        }
        await nzbn.execute_action("get_changes", inputs, mock_context)

        call_args = mock_make_request.call_args
        params = call_args[0][3]
        assert params["change-event-type"] == "NameChange"
        assert params["start-date"] == "2024-01-01"
        assert params["end-date"] == "2024-01-31"
        assert params["page-size"] == 10
        assert params["page"] == 0


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestMakeRequest:
    """Test make_request helper."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.get_headers")
    async def test_make_request_success_dict_response(self, mock_get_headers, mock_context):
        mock_get_headers.return_value = {
            "Authorization": "Bearer tok",
            "Accept": "application/json",
        }
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"nzbn": TEST_NZBN, "entityName": "Test"}
        )

        result = await make_request(mock_context, "GET", f"/entities/{TEST_NZBN}")

        assert result["success"] is True
        assert result["data"]["entityName"] == "Test"

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.get_headers")
    async def test_make_request_http_404(self, mock_get_headers, mock_context):
        mock_get_headers.return_value = {"Authorization": "Bearer tok"}
        mock_context.fetch.return_value = FetchResponse(status=404, headers={}, data=None)

        result = await make_request(mock_context, "GET", "/entities/0000000000000")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.get_headers")
    async def test_make_request_http_401(self, mock_get_headers, mock_context):
        mock_get_headers.return_value = {}
        mock_context.fetch.return_value = FetchResponse(status=401, headers={}, data=None)

        result = await make_request(mock_context, "GET", "/entities/test")

        assert result["success"] is False
        assert "Unauthorized" in result["error"]

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.get_headers")
    async def test_make_request_http_200(self, mock_get_headers, mock_context):
        mock_get_headers.return_value = {}
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"entityName": "OK Corp"})

        result = await make_request(mock_context, "GET", "/entities/test")

        assert result["success"] is True
        assert result["data"]["entityName"] == "OK Corp"

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.get_headers")
    async def test_make_request_http_304(self, mock_get_headers, mock_context):
        mock_get_headers.return_value = {}
        mock_context.fetch.return_value = FetchResponse(status=304, headers={}, data=None)

        result = await make_request(mock_context, "GET", "/entities/test")

        assert result["success"] is True
        assert result["not_modified"] is True


class TestGetHeaders:
    """Test get_headers helper."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.get_oauth_token")
    @patch("nzbn.nzbn.SUBSCRIPTION_KEY", "test-sub-key")
    async def test_headers_include_subscription_key(self, mock_get_oauth_token, mock_context):
        mock_get_oauth_token.return_value = "tok_abc"

        headers = await get_headers(mock_context)

        assert headers["Ocp-Apim-Subscription-Key"] == "test-sub-key"
        assert headers["Authorization"] == "Bearer tok_abc"
        assert headers["Accept"] == "application/json"

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.get_oauth_token")
    async def test_headers_without_token(self, mock_get_oauth_token, mock_context):
        mock_get_oauth_token.return_value = None

        headers = await get_headers(mock_context)

        assert "Authorization" not in headers


# =============================================================================
# Error Handling
# =============================================================================


class TestErrorHandling:
    """Verify actions handle exceptions gracefully."""

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_search_entities_exception(self, mock_make_request, mock_context):
        mock_make_request.side_effect = RuntimeError("connection refused")

        result = await nzbn.execute_action("search_entities", {"search_term": "test"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "connection refused" in result.result.message

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_get_entity_exception(self, mock_make_request, mock_context):
        mock_make_request.side_effect = RuntimeError("timeout")

        result = await nzbn.execute_action("get_entity", {"nzbn": TEST_NZBN}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "timeout" in result.result.message

    @pytest.mark.asyncio
    @patch("nzbn.nzbn.make_request")
    async def test_get_changes_exception(self, mock_make_request, mock_context):
        mock_make_request.side_effect = RuntimeError("server error")

        result = await nzbn.execute_action("get_changes", {"change_event_type": "NewRegistration"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "server error" in result.result.message
