import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from linkedin_ads import (
    extract_id_from_urn,
    build_urn,
    get_headers,
    make_request,
    API_VERSION,
    API_BASE_URL,
    GetAdAccountsAction,
    GetCampaignsAction,
    GetCampaignAction,
    CreateCampaignAction,
    PauseCampaignAction,
    ActivateCampaignAction,
    GetAdAnalyticsAction,
    GetAdAccountUsersAction,
)


class TestHelperFunctions:
    """Tests for helper/utility functions."""

    def test_extract_id_from_urn_with_valid_urns(self):
        assert extract_id_from_urn("urn:li:sponsoredAccount:123456789") == "123456789"
        assert extract_id_from_urn("urn:li:sponsoredCampaign:987654321") == "987654321"
        assert extract_id_from_urn("urn:li:sponsoredCampaignGroup:555666777") == "555666777"
        assert extract_id_from_urn("urn:li:sponsoredCreative:111222333") == "111222333"

    def test_extract_id_from_urn_with_plain_id(self):
        assert extract_id_from_urn("123456789") == "123456789"
        assert extract_id_from_urn("987654321") == "987654321"

    def test_extract_id_from_urn_with_empty_string(self):
        assert extract_id_from_urn("") == ""

    def test_extract_id_from_urn_with_zero(self):
        assert extract_id_from_urn("0") == "0"

    def test_extract_id_from_urn_rejects_non_numeric(self):
        with pytest.raises(ValueError):
            extract_id_from_urn("abc123")
        with pytest.raises(ValueError):
            extract_id_from_urn("urn:li:sponsoredAccount:abc123")

    def test_extract_id_from_urn_rejects_path_traversal(self):
        with pytest.raises(ValueError):
            extract_id_from_urn("urn:li:sponsoredCampaign:123/../../adAccounts")
        with pytest.raises(ValueError):
            extract_id_from_urn("123/../456")

    def test_build_urn_for_account(self):
        assert build_urn("account", "123456789") == "urn:li:sponsoredAccount:123456789"

    def test_build_urn_for_campaign(self):
        assert build_urn("campaign", "987654321") == "urn:li:sponsoredCampaign:987654321"

    def test_build_urn_for_campaign_group(self):
        assert build_urn("campaign_group", "111222333") == "urn:li:sponsoredCampaignGroup:111222333"

    def test_build_urn_for_creative(self):
        assert build_urn("creative", "444555666") == "urn:li:sponsoredCreative:444555666"

    def test_build_urn_with_unknown_entity_type(self):
        assert build_urn("unknown", "123") == "urn:li:unknown:123"

    def test_build_urn_preserves_existing_urn(self):
        existing_urn = "urn:li:sponsoredAccount:123456789"
        assert build_urn("account", existing_urn) == existing_urn
        assert build_urn("campaign", "urn:li:sponsoredCampaign:987654321") == "urn:li:sponsoredCampaign:987654321"

    def test_get_headers_contains_required_fields(self):
        headers = get_headers()
        assert "LinkedIn-Version" in headers
        assert "X-Restli-Protocol-Version" in headers
        assert "Content-Type" in headers

    def test_get_headers_has_correct_values(self):
        headers = get_headers()
        assert headers["LinkedIn-Version"] == API_VERSION
        assert headers["X-Restli-Protocol-Version"] == "2.0.0"
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_does_not_include_authorization(self):
        headers = get_headers()
        assert "Authorization" not in headers


class TestMakeRequest:
    """Tests for the make_request function."""

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.fetch = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_make_request_get_success(self, mock_context):
        mock_context.fetch.return_value = {"elements": [{"id": "123"}]}
        
        result = await make_request(mock_context, "GET", "/adAccounts")
        
        assert result["success"] is True
        assert result["data"]["elements"][0]["id"] == "123"
        mock_context.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_post_success(self, mock_context):
        mock_context.fetch.return_value = {"id": "new-campaign-123"}
        
        result = await make_request(
            mock_context, 
            "POST", 
            "/adCampaigns",
            json_body={"name": "Test Campaign"}
        )
        
        assert result["success"] is True
        assert result["data"]["id"] == "new-campaign-123"

    @pytest.mark.asyncio
    async def test_make_request_with_params(self, mock_context):
        mock_context.fetch.return_value = {"elements": []}
        
        await make_request(
            mock_context,
            "GET",
            "/adCampaigns",
            params={"q": "search", "count": 25}
        )
        
        call_kwargs = mock_context.fetch.call_args
        assert "params" in call_kwargs.kwargs
        assert call_kwargs.kwargs["params"]["q"] == "search"

    @pytest.mark.asyncio
    async def test_make_request_with_extra_headers(self, mock_context):
        mock_context.fetch.return_value = {}
        
        await make_request(
            mock_context,
            "POST",
            "/adCampaigns/123",
            extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"}
        )
        
        call_kwargs = mock_context.fetch.call_args
        assert "X-RestLi-Method" in call_kwargs.kwargs["headers"]

    @pytest.mark.asyncio
    async def test_make_request_handles_generic_exception(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection timeout")
        
        result = await make_request(mock_context, "GET", "/adAccounts")
        
        assert result["success"] is False
        assert "Connection timeout" in result["error"]
        assert "details" in result

    @pytest.mark.asyncio
    async def test_make_request_handles_exception_with_status_code(self, mock_context):
        error = Exception("API Error")
        error.status_code = 401
        mock_context.fetch.side_effect = error
        
        result = await make_request(mock_context, "GET", "/adAccounts")
        
        assert result["success"] is False
        assert "Unauthorized" in result["error"]

    @pytest.mark.asyncio
    async def test_make_request_unsupported_method(self, mock_context):
        result = await make_request(mock_context, "PUT", "/adAccounts")
        
        assert result["success"] is False
        assert "Unsupported HTTP method" in result["error"]

    @pytest.mark.asyncio
    async def test_make_request_unsupported_patch_method(self, mock_context):
        result = await make_request(mock_context, "PATCH", "/adAccounts")
        
        assert result["success"] is False
        assert "Unsupported HTTP method" in result["error"]


class TestGetAdAccountsAction:
    """Tests for GetAdAccountsAction."""

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.fetch = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_get_ad_accounts_success(self, mock_context):
        mock_context.fetch.side_effect = [
            {"elements": [{"account": "urn:li:sponsoredAccount:123"}]},
            {"id": "123", "name": "Test Account", "status": "ACTIVE"}
        ]
        
        action = GetAdAccountsAction()
        result = await action.execute({}, mock_context)
        
        assert result.data["result"] is True
        assert len(result.data["accounts"]) == 1
        assert result.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_get_ad_accounts_with_page_size(self, mock_context):
        mock_context.fetch.return_value = {"elements": []}
        
        action = GetAdAccountsAction()
        await action.execute({"page_size": 50}, mock_context)
        
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.kwargs["params"]["count"] == 50


class TestGetCampaignsAction:
    """Tests for GetCampaignsAction."""

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.fetch = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_get_campaigns_requires_account_id(self, mock_context):
        action = GetCampaignsAction()
        result = await action.execute({}, mock_context)
        
        assert result.data["result"] is False
        assert "account_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_get_campaigns_success(self, mock_context):
        mock_context.fetch.return_value = {
            "elements": [
                {"id": "campaign1", "name": "Campaign 1", "status": "ACTIVE"},
                {"id": "campaign2", "name": "Campaign 2", "status": "PAUSED"}
            ]
        }
        
        action = GetCampaignsAction()
        result = await action.execute({"account_id": "123456789"}, mock_context)
        
        assert result.data["result"] is True
        assert len(result.data["campaigns"]) == 2
        assert result.data["total"] == 2

    @pytest.mark.asyncio
    async def test_get_campaigns_with_status_filter(self, mock_context):
        mock_context.fetch.return_value = {"elements": []}
        
        action = GetCampaignsAction()
        await action.execute({"account_id": "123", "status": "ACTIVE"}, mock_context)
        
        call_kwargs = mock_context.fetch.call_args
        assert "search.status.values[0]" in call_kwargs.kwargs["params"]


class TestGetCampaignAction:
    """Tests for GetCampaignAction."""

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.fetch = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_get_campaign_requires_campaign_id(self, mock_context):
        action = GetCampaignAction()
        result = await action.execute({}, mock_context)
        
        assert result.data["result"] is False
        assert "campaign_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_get_campaign_success(self, mock_context):
        mock_context.fetch.return_value = {
            "id": "123",
            "name": "Test Campaign",
            "status": "ACTIVE",
            "objectiveType": "WEBSITE_VISITS"
        }
        
        action = GetCampaignAction()
        result = await action.execute({"campaign_id": "123"}, mock_context)
        
        assert result.data["result"] is True
        assert result.data["campaign"]["name"] == "Test Campaign"

    @pytest.mark.asyncio
    async def test_get_campaign_with_urn_input(self, mock_context):
        mock_context.fetch.return_value = {"id": "123", "name": "Test"}
        
        action = GetCampaignAction()
        await action.execute({"campaign_id": "urn:li:sponsoredCampaign:123"}, mock_context)
        
        call_args = mock_context.fetch.call_args
        assert "/adCampaigns/123" in call_args.args[0]


class TestCreateCampaignAction:
    """Tests for CreateCampaignAction."""

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.fetch = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_create_campaign_requires_all_fields(self, mock_context):
        action = CreateCampaignAction()
        result = await action.execute({"account_id": "123"}, mock_context)
        
        assert result.data["result"] is False
        assert "Missing required fields" in result.data["error"]

    @pytest.mark.asyncio
    async def test_create_campaign_success(self, mock_context):
        mock_context.fetch.return_value = {"id": "new-campaign-123"}
        
        action = CreateCampaignAction()
        result = await action.execute({
            "account_id": "123456789",
            "campaign_group_id": "111222333",
            "name": "New Test Campaign",
            "objective_type": "WEBSITE_VISITS",
            "type": "SPONSORED_UPDATES",
            "daily_budget_amount": 100.00
        }, mock_context)
        
        assert result.data["result"] is True
        assert "campaign_id" in result.data


class TestPauseCampaignAction:
    """Tests for PauseCampaignAction."""

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.fetch = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_pause_campaign_requires_campaign_id(self, mock_context):
        action = PauseCampaignAction()
        result = await action.execute({}, mock_context)
        
        assert result.data["result"] is False
        assert "campaign_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_pause_campaign_success(self, mock_context):
        mock_context.fetch.return_value = {}
        
        action = PauseCampaignAction()
        result = await action.execute({"campaign_id": "123"}, mock_context)
        
        assert result.data["result"] is True
        assert "paused successfully" in result.data["message"]

    @pytest.mark.asyncio
    async def test_pause_campaign_sends_correct_payload(self, mock_context):
        mock_context.fetch.return_value = {}
        
        action = PauseCampaignAction()
        await action.execute({"campaign_id": "123"}, mock_context)
        
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.kwargs["json"]["patch"]["$set"]["status"] == "PAUSED"


class TestActivateCampaignAction:
    """Tests for ActivateCampaignAction."""

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.fetch = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_activate_campaign_requires_campaign_id(self, mock_context):
        action = ActivateCampaignAction()
        result = await action.execute({}, mock_context)
        
        assert result.data["result"] is False
        assert "campaign_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_activate_campaign_success(self, mock_context):
        mock_context.fetch.return_value = {}
        
        action = ActivateCampaignAction()
        result = await action.execute({"campaign_id": "123"}, mock_context)
        
        assert result.data["result"] is True
        assert "activated successfully" in result.data["message"]

    @pytest.mark.asyncio
    async def test_activate_campaign_sends_correct_payload(self, mock_context):
        mock_context.fetch.return_value = {}
        
        action = ActivateCampaignAction()
        await action.execute({"campaign_id": "123"}, mock_context)
        
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.kwargs["json"]["patch"]["$set"]["status"] == "ACTIVE"


class TestGetAdAnalyticsAction:
    """Tests for GetAdAnalyticsAction."""

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.fetch = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_get_analytics_requires_all_params(self, mock_context):
        action = GetAdAnalyticsAction()
        result = await action.execute({"account_id": "123"}, mock_context)
        
        assert result.data["result"] is False
        assert "required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_get_analytics_validates_date_format(self, mock_context):
        action = GetAdAnalyticsAction()
        result = await action.execute({
            "account_id": "123",
            "start_date": "invalid-date",
            "end_date": "2025-01-20"
        }, mock_context)
        
        assert result.data["result"] is False
        assert "Invalid date format" in result.data["error"]

    @pytest.mark.asyncio
    async def test_get_analytics_success(self, mock_context):
        mock_context.fetch.return_value = {
            "elements": [
                {"impressions": 1000, "clicks": 50, "costInLocalCurrency": "100.00"}
            ]
        }
        
        action = GetAdAnalyticsAction()
        result = await action.execute({
            "account_id": "123456789",
            "start_date": "2025-01-01",
            "end_date": "2025-01-20"
        }, mock_context)
        
        assert result.data["result"] is True
        assert len(result.data["analytics"]) == 1


class TestGetAdAccountUsersAction:
    """Tests for GetAdAccountUsersAction."""

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.fetch = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_get_users_requires_account_id(self, mock_context):
        action = GetAdAccountUsersAction()
        result = await action.execute({}, mock_context)
        
        assert result.data["result"] is False
        assert "account_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_get_users_success(self, mock_context):
        mock_context.fetch.return_value = {
            "elements": [
                {"user": "urn:li:person:abc123", "role": "ACCOUNT_MANAGER"}
            ]
        }
        
        action = GetAdAccountUsersAction()
        result = await action.execute({"account_id": "123"}, mock_context)
        
        assert result.data["result"] is True
        assert len(result.data["users"]) == 1


class TestAPIConfiguration:
    """Tests for API configuration constants."""

    def test_api_base_url_is_correct(self):
        assert API_BASE_URL == "https://api.linkedin.com/rest"

    def test_api_version_format(self):
        assert API_VERSION == "202601"
        assert len(API_VERSION) == 6
