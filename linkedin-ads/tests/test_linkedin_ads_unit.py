import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from autohive_integrations_sdk import FetchResponse, HTTPError

from linkedin_ads import (
    extract_id_from_urn,
    build_urn,
    build_query,
    urn_param,
    get_headers,
    make_request,
    API_VERSION,
    API_BASE_URL,
    ANALYTICS_FIELDS,
    GetAdAccountsAction,
    GetCampaignsAction,
    GetCampaignAction,
    CreateCampaignAction,
    UpdateCampaignAction,
    PauseCampaignAction,
    ActivateCampaignAction,
    GetCampaignGroupsAction,
    GetCreativesAction,
    GetAdAnalyticsAction,
    GetAdAccountUsersAction,
)

pytestmark = pytest.mark.unit


def resp(data, status=200):
    """Build a FetchResponse like the SDK returns from context.fetch."""
    return FetchResponse(status=status, headers={}, data=data)


def fetch_url(mock_context, index=0):
    """Return the request URL passed to context.fetch as a string."""
    return str(mock_context.fetch.call_args_list[index].args[0])


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.fetch = AsyncMock()
    return context


# ---- Helper / utility functions ----


class TestHelperFunctions:
    def test_extract_id_from_urn_with_valid_urns(self):
        assert extract_id_from_urn("urn:li:sponsoredAccount:123456789") == "123456789"
        assert extract_id_from_urn("urn:li:sponsoredCampaign:987654321") == "987654321"

    def test_extract_id_from_urn_with_plain_id(self):
        assert extract_id_from_urn("123456789") == "123456789"

    def test_extract_id_from_urn_with_empty_string(self):
        assert extract_id_from_urn("") == ""

    def test_extract_id_from_urn_rejects_non_numeric(self):
        with pytest.raises(ValueError):
            extract_id_from_urn("abc123")
        with pytest.raises(ValueError):
            extract_id_from_urn("urn:li:sponsoredAccount:abc123")

    def test_extract_id_from_urn_rejects_path_traversal(self):
        with pytest.raises(ValueError):
            extract_id_from_urn("urn:li:sponsoredCampaign:123/../../adAccounts")

    def test_build_urn_for_account(self):
        assert build_urn("account", "123456789") == "urn:li:sponsoredAccount:123456789"

    def test_build_urn_for_campaign(self):
        assert build_urn("campaign", "987654321") == "urn:li:sponsoredCampaign:987654321"

    def test_build_urn_preserves_existing_urn(self):
        existing = "urn:li:sponsoredAccount:123456789"
        assert build_urn("account", existing) == existing

    def test_get_headers_has_correct_values(self):
        headers = get_headers()
        assert headers["LinkedIn-Version"] == API_VERSION
        assert headers["X-Restli-Protocol-Version"] == "2.0.0"
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_does_not_include_authorization(self):
        assert "Authorization" not in get_headers()


class TestBuildQuery:
    def test_preserves_restli_structural_chars(self):
        # Parens, colons, and commas must survive un-encoded.
        qs = build_query({"search": "(status:(values:List(ACTIVE)))"})
        assert qs == "search=(status:(values:List(ACTIVE)))"

    def test_preserves_comma_separated_fields(self):
        qs = build_query({"fields": "impressions,clicks,costInLocalCurrency"})
        assert qs == "fields=impressions,clicks,costInLocalCurrency"

    def test_preserves_pre_encoded_urn_percent(self):
        # %3A from urn_param must not be double-encoded.
        qs = build_query({"accounts": "List(urn%3Ali%3AsponsoredAccount%3A123)"})
        assert qs == "accounts=List(urn%3Ali%3AsponsoredAccount%3A123)"

    def test_skips_none_values(self):
        qs = build_query({"q": "search", "status": None, "count": 25})
        assert qs == "q=search&count=25"

    def test_encodes_unsafe_characters(self):
        qs = build_query({"name": "a b"})
        assert qs == "name=a%20b"


class TestUrnParam:
    def test_encodes_colons(self):
        assert urn_param("urn:li:sponsoredAccount:123") == "urn%3Ali%3AsponsoredAccount%3A123"


# ---- make_request ----


class TestMakeRequest:
    @pytest.mark.asyncio
    async def test_get_success_unwraps_data(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": [{"id": "123"}]})

        result = await make_request(mock_context, "GET", "/adAccounts")

        assert result["success"] is True
        assert result["data"]["elements"][0]["id"] == "123"

    @pytest.mark.asyncio
    async def test_get_bakes_query_into_url_not_params(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": []})

        await make_request(mock_context, "GET", "/adCampaigns", params={"q": "search", "count": 25})

        call = mock_context.fetch.call_args
        # Query is part of the URL; the SDK params kwarg is not used.
        assert "params" not in call.kwargs
        assert str(call.args[0]) == f"{API_BASE_URL}/adCampaigns?q=search&count=25"

    @pytest.mark.asyncio
    async def test_get_preserves_encoded_urn_in_url(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": []})

        await make_request(
            mock_context,
            "GET",
            "/adAccountUsers",
            params={"q": "accounts", "accounts": "List(urn%3Ali%3AsponsoredAccount%3A1)"},
        )

        assert "accounts=List(urn%3Ali%3AsponsoredAccount%3A1)" in fetch_url(mock_context)

    @pytest.mark.asyncio
    async def test_post_sends_json(self, mock_context):
        mock_context.fetch.return_value = resp({"id": "new-123"})

        result = await make_request(mock_context, "POST", "/adAccounts/1/adCampaigns", json_body={"name": "x"})

        assert result["success"] is True
        assert mock_context.fetch.call_args.kwargs["json"] == {"name": "x"}
        assert mock_context.fetch.call_args.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_extra_headers_merged(self, mock_context):
        mock_context.fetch.return_value = resp({})

        await make_request(mock_context, "POST", "/x", extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"})

        assert mock_context.fetch.call_args.kwargs["headers"]["X-RestLi-Method"] == "PARTIAL_UPDATE"

    @pytest.mark.asyncio
    async def test_http_error_401_friendly(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(401, "unauth", {"code": "X"})

        result = await make_request(mock_context, "GET", "/adAccounts")

        assert result["success"] is False
        assert "Unauthorized" in result["error"]
        assert result["details"]["status"] == 401

    @pytest.mark.asyncio
    async def test_http_error_404_friendly(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(404, "nope", {"code": "NOT_FOUND"})

        result = await make_request(mock_context, "GET", "/adAccounts/999")

        assert result["success"] is False
        assert "Resource not found" in result["error"]

    @pytest.mark.asyncio
    async def test_http_error_other_status_passthrough(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(400, "bad request", {"code": "ILLEGAL_ARGUMENT"})

        result = await make_request(mock_context, "GET", "/adAccounts")

        assert result["success"] is False
        assert "HTTP 400" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_exception(self, mock_context):
        mock_context.fetch.side_effect = Exception("Connection timeout")

        result = await make_request(mock_context, "GET", "/adAccounts")

        assert result["success"] is False
        assert "Connection timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_unsupported_method(self, mock_context):
        result = await make_request(mock_context, "PUT", "/adAccounts")
        assert result["success"] is False
        assert "Unsupported HTTP method" in result["error"]


# ---- get_ad_accounts ----


class TestGetAdAccountsAction:
    @pytest.mark.asyncio
    async def test_success_fetches_each_account_individually(self, mock_context):
        mock_context.fetch.side_effect = [
            resp({"elements": [{"account": "urn:li:sponsoredAccount:123"}]}),
            resp({"id": "123", "name": "Test Account", "status": "ACTIVE"}),
        ]

        result = await GetAdAccountsAction().execute({}, mock_context)

        assert result.data["result"] is True
        assert len(result.data["accounts"]) == 1
        assert result.data["accounts"][0]["name"] == "Test Account"
        # Second call is the single-account GET (no batch).
        assert fetch_url(mock_context, 1).endswith("/adAccounts/123")

    @pytest.mark.asyncio
    async def test_page_size_in_first_call_url(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": []})

        await GetAdAccountsAction().execute({"page_size": 50}, mock_context)

        assert "count=50" in fetch_url(mock_context, 0)

    @pytest.mark.asyncio
    async def test_no_accounts_returns_empty(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": []})

        result = await GetAdAccountsAction().execute({}, mock_context)

        assert result.data["result"] is True
        assert result.data["accounts"] == []

    @pytest.mark.asyncio
    async def test_first_call_failure_surfaces_error(self, mock_context):
        mock_context.fetch.side_effect = HTTPError(403, "forbidden", {})

        result = await GetAdAccountsAction().execute({}, mock_context)

        assert result.data["result"] is False
        assert "Forbidden" in result.data["error"]


# ---- get_campaigns ----


class TestGetCampaignsAction:
    @pytest.mark.asyncio
    async def test_requires_account_id(self, mock_context):
        result = await GetCampaignsAction().execute({}, mock_context)
        assert result.data["result"] is False
        assert "account_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_success_uses_account_scoped_path(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": [{"id": "c1"}, {"id": "c2"}]})

        result = await GetCampaignsAction().execute({"account_id": "123"}, mock_context)

        assert result.data["result"] is True
        assert result.data["total"] == 2
        url = fetch_url(mock_context)
        assert "/adAccounts/123/adCampaigns" in url
        assert "q=search" in url

    @pytest.mark.asyncio
    async def test_status_filter_uses_compact_syntax(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": []})

        await GetCampaignsAction().execute({"account_id": "123", "status": "ACTIVE"}, mock_context)

        assert "search=(status:(values:List(ACTIVE)))" in fetch_url(mock_context)


# ---- get_campaign ----


class TestGetCampaignAction:
    @pytest.mark.asyncio
    async def test_requires_campaign_id(self, mock_context):
        result = await GetCampaignAction().execute({"account_id": "1"}, mock_context)
        assert result.data["result"] is False
        assert "campaign_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_requires_account_id(self, mock_context):
        result = await GetCampaignAction().execute({"campaign_id": "123"}, mock_context)
        assert result.data["result"] is False
        assert "account_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_success_uses_account_scoped_path(self, mock_context):
        mock_context.fetch.return_value = resp({"id": "123", "name": "Test Campaign"})

        result = await GetCampaignAction().execute(
            {"account_id": "456", "campaign_id": "urn:li:sponsoredCampaign:123"}, mock_context
        )

        assert result.data["result"] is True
        assert result.data["campaign"]["name"] == "Test Campaign"
        assert fetch_url(mock_context).endswith("/adAccounts/456/adCampaigns/123")


# ---- get_campaign_groups ----


class TestGetCampaignGroupsAction:
    @pytest.mark.asyncio
    async def test_requires_account_id(self, mock_context):
        result = await GetCampaignGroupsAction().execute({}, mock_context)
        assert result.data["result"] is False
        assert "account_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_success_uses_account_scoped_path(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": [{"id": "g1"}, {"id": "g2"}]})

        result = await GetCampaignGroupsAction().execute({"account_id": "123"}, mock_context)

        assert result.data["result"] is True
        assert len(result.data["campaign_groups"]) == 2
        assert "/adAccounts/123/adCampaignGroups" in fetch_url(mock_context)

    @pytest.mark.asyncio
    async def test_status_filter_uses_compact_syntax(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": []})

        await GetCampaignGroupsAction().execute({"account_id": "123", "status": "ACTIVE"}, mock_context)

        assert "search=(status:(values:List(ACTIVE)))" in fetch_url(mock_context)


# ---- get_creatives ----


class TestGetCreativesAction:
    @pytest.mark.asyncio
    async def test_requires_account_id(self, mock_context):
        result = await GetCreativesAction().execute({}, mock_context)
        assert result.data["result"] is False
        assert "account_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_success_uses_criteria_finder(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": [{"id": "cr1"}]})

        result = await GetCreativesAction().execute({"account_id": "123"}, mock_context)

        assert result.data["result"] is True
        url = fetch_url(mock_context)
        assert "/adAccounts/123/creatives" in url
        assert "q=criteria" in url

    @pytest.mark.asyncio
    async def test_campaign_filter_encoded_in_list(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": []})

        await GetCreativesAction().execute({"account_id": "123", "campaign_id": "999"}, mock_context)

        assert "campaigns=List(urn%3Ali%3AsponsoredCampaign%3A999)" in fetch_url(mock_context)


# ---- get_ad_analytics ----


class TestGetAdAnalyticsAction:
    @pytest.mark.asyncio
    async def test_requires_all_params(self, mock_context):
        result = await GetAdAnalyticsAction().execute({"account_id": "123"}, mock_context)
        assert result.data["result"] is False
        assert "required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_validates_date_format(self, mock_context):
        result = await GetAdAnalyticsAction().execute(
            {"account_id": "123", "start_date": "invalid", "end_date": "2026-01-20"}, mock_context
        )
        assert result.data["result"] is False
        assert "Invalid date format" in result.data["error"]

    @pytest.mark.asyncio
    async def test_success_builds_compact_query(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": [{"impressions": 1000}]})

        result = await GetAdAnalyticsAction().execute(
            {"account_id": "123", "start_date": "2026-06-01", "end_date": "2026-06-30"}, mock_context
        )

        assert result.data["result"] is True
        url = fetch_url(mock_context)
        assert "dateRange=(start:(year:2026,month:6,day:1),end:(year:2026,month:6,day:30))" in url
        assert "accounts=List(urn%3Ali%3AsponsoredAccount%3A123)" in url
        assert f"fields={ANALYTICS_FIELDS}" in url

    @pytest.mark.asyncio
    async def test_campaign_ids_encoded_in_list(self, mock_context):
        mock_context.fetch.return_value = resp({"elements": []})

        await GetAdAnalyticsAction().execute(
            {
                "account_id": "123",
                "start_date": "2026-06-01",
                "end_date": "2026-06-30",
                "campaign_ids": ["111", "222"],
            },
            mock_context,
        )

        assert "campaigns=List(urn%3Ali%3AsponsoredCampaign%3A111,urn%3Ali%3AsponsoredCampaign%3A222)" in fetch_url(
            mock_context
        )


# ---- get_ad_account_users ----


class TestGetAdAccountUsersAction:
    @pytest.mark.asyncio
    async def test_requires_account_id(self, mock_context):
        result = await GetAdAccountUsersAction().execute({}, mock_context)
        assert result.data["result"] is False
        assert "account_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_success_uses_accounts_finder(self, mock_context):
        mock_context.fetch.return_value = resp(
            {"elements": [{"user": "urn:li:person:abc", "role": "ACCOUNT_BILLING_ADMIN"}]}
        )

        result = await GetAdAccountUsersAction().execute({"account_id": "123"}, mock_context)

        assert result.data["result"] is True
        assert len(result.data["users"]) == 1
        url = fetch_url(mock_context)
        assert "q=accounts" in url
        assert "accounts=List(urn%3Ali%3AsponsoredAccount%3A123)" in url


# ---- create_campaign ----


class TestCreateCampaignAction:
    @pytest.mark.asyncio
    async def test_requires_all_fields(self, mock_context):
        result = await CreateCampaignAction().execute({"account_id": "123"}, mock_context)
        assert result.data["result"] is False
        assert "Missing required fields" in result.data["error"]

    @pytest.mark.asyncio
    async def test_success_posts_to_account_scoped_path(self, mock_context):
        mock_context.fetch.return_value = resp({"id": "new-campaign-123"})

        result = await CreateCampaignAction().execute(
            {
                "account_id": "123456789",
                "campaign_group_id": "111222333",
                "name": "New Test Campaign",
                "objective_type": "WEBSITE_VISITS",
                "type": "SPONSORED_UPDATES",
                "daily_budget_amount": 100.00,
            },
            mock_context,
        )

        assert result.data["result"] is True
        assert result.data["campaign_id"] == "new-campaign-123"
        assert fetch_url(mock_context).endswith("/adAccounts/123456789/adCampaigns")
        assert mock_context.fetch.call_args.kwargs["method"] == "POST"


# ---- update_campaign ----


class TestUpdateCampaignAction:
    @pytest.mark.asyncio
    async def test_requires_campaign_id(self, mock_context):
        result = await UpdateCampaignAction().execute({"account_id": "1"}, mock_context)
        assert result.data["result"] is False
        assert "campaign_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_requires_account_id(self, mock_context):
        result = await UpdateCampaignAction().execute({"campaign_id": "123"}, mock_context)
        assert result.data["result"] is False
        assert "account_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_no_update_fields(self, mock_context):
        result = await UpdateCampaignAction().execute({"account_id": "1", "campaign_id": "123"}, mock_context)
        assert result.data["result"] is False
        assert "No update fields provided" in result.data["error"]

    @pytest.mark.asyncio
    async def test_success_partial_update_on_scoped_path(self, mock_context):
        mock_context.fetch.return_value = resp({})

        result = await UpdateCampaignAction().execute(
            {"account_id": "456", "campaign_id": "123", "name": "Renamed"}, mock_context
        )

        assert result.data["result"] is True
        call = mock_context.fetch.call_args
        assert str(call.args[0]).endswith("/adAccounts/456/adCampaigns/123")
        assert call.kwargs["headers"]["X-RestLi-Method"] == "PARTIAL_UPDATE"
        assert call.kwargs["json"]["patch"]["$set"]["name"] == "Renamed"


# ---- pause_campaign ----


class TestPauseCampaignAction:
    @pytest.mark.asyncio
    async def test_requires_campaign_id(self, mock_context):
        result = await PauseCampaignAction().execute({"account_id": "1"}, mock_context)
        assert result.data["result"] is False
        assert "campaign_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_requires_account_id(self, mock_context):
        result = await PauseCampaignAction().execute({"campaign_id": "123"}, mock_context)
        assert result.data["result"] is False
        assert "account_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_success_sends_paused_status_on_scoped_path(self, mock_context):
        mock_context.fetch.return_value = resp({})

        result = await PauseCampaignAction().execute({"account_id": "456", "campaign_id": "123"}, mock_context)

        assert result.data["result"] is True
        call = mock_context.fetch.call_args
        assert str(call.args[0]).endswith("/adAccounts/456/adCampaigns/123")
        assert call.kwargs["json"]["patch"]["$set"]["status"] == "PAUSED"


# ---- activate_campaign ----


class TestActivateCampaignAction:
    @pytest.mark.asyncio
    async def test_requires_campaign_id(self, mock_context):
        result = await ActivateCampaignAction().execute({"account_id": "1"}, mock_context)
        assert result.data["result"] is False
        assert "campaign_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_requires_account_id(self, mock_context):
        result = await ActivateCampaignAction().execute({"campaign_id": "123"}, mock_context)
        assert result.data["result"] is False
        assert "account_id is required" in result.data["error"]

    @pytest.mark.asyncio
    async def test_success_sends_active_status_on_scoped_path(self, mock_context):
        mock_context.fetch.return_value = resp({})

        result = await ActivateCampaignAction().execute({"account_id": "456", "campaign_id": "123"}, mock_context)

        assert result.data["result"] is True
        call = mock_context.fetch.call_args
        assert str(call.args[0]).endswith("/adAccounts/456/adCampaigns/123")
        assert call.kwargs["json"]["patch"]["$set"]["status"] == "ACTIVE"


# ---- API configuration ----


class TestAPIConfiguration:
    def test_api_base_url_is_correct(self):
        assert API_BASE_URL == "https://api.linkedin.com/rest"

    def test_api_version_format(self):
        assert API_VERSION == "202601"
        assert len(API_VERSION) == 6
