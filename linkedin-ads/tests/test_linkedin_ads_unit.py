import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import AsyncMock, MagicMock

from autohive_integrations_sdk import FetchResponse, ResultType

from linkedin_ads import (
    linkedin_ads,
    extract_id_from_urn,
    build_urn,
    build_query,
    urn_param,
    get_headers,
    API_VERSION,
    API_BASE_URL,
    ANALYTICS_FIELDS,
)

pytestmark = pytest.mark.unit


def ok(data, status=200):
    """Build a FetchResponse like the SDK returns from context.fetch."""
    return FetchResponse(status=status, headers={}, data=data)


def fetch_url(mock_context, index=0):
    """The request URL passed to context.fetch, as a string."""
    return str(mock_context.fetch.call_args_list[index].args[0])


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


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
        assert build_query({"search": "(status:(values:List(ACTIVE)))"}) == "search=(status:(values:List(ACTIVE)))"

    def test_preserves_comma_separated_fields(self):
        assert build_query({"fields": "impressions,clicks"}) == "fields=impressions,clicks"

    def test_preserves_pre_encoded_urn_percent(self):
        assert (
            build_query({"accounts": "List(urn%3Ali%3AsponsoredAccount%3A1)"})
            == "accounts=List(urn%3Ali%3AsponsoredAccount%3A1)"
        )

    def test_skips_none_values(self):
        assert build_query({"q": "search", "status": None, "count": 25}) == "q=search&count=25"

    def test_encodes_unsafe_characters(self):
        assert build_query({"name": "a b"}) == "name=a%20b"


class TestUrnParam:
    def test_encodes_colons(self):
        assert urn_param("urn:li:sponsoredAccount:123") == "urn%3Ali%3AsponsoredAccount%3A123"


class TestApiConfiguration:
    def test_api_base_url(self):
        assert API_BASE_URL == "https://api.linkedin.com/rest"

    def test_api_version(self):
        assert API_VERSION == "202601"

    def test_analytics_fields_exclude_derived_metrics(self):
        assert "costPerClick" not in ANALYTICS_FIELDS
        assert "clickThroughRate" not in ANALYTICS_FIELDS
        assert "impressions" in ANALYTICS_FIELDS


# ---- get_ad_accounts ----


class TestGetAdAccounts:
    @pytest.mark.asyncio
    async def test_success_fetches_each_account(self, mock_context):
        mock_context.fetch.side_effect = [
            ok({"elements": [{"account": "urn:li:sponsoredAccount:123"}]}),
            ok({"id": "123", "name": "Test Account", "status": "ACTIVE"}),
        ]

        result = await linkedin_ads.execute_action("get_ad_accounts", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["accounts"]) == 1
        assert result.result.data["accounts"][0]["name"] == "Test Account"
        assert fetch_url(mock_context, 1).endswith("/adAccounts/123")

    @pytest.mark.asyncio
    async def test_page_size_in_url(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": []})

        await linkedin_ads.execute_action("get_ad_accounts", {"page_size": 50}, mock_context)

        assert "count=50" in fetch_url(mock_context, 0)

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 403: forbidden")

        result = await linkedin_ads.execute_action("get_ad_accounts", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "forbidden" in result.result.message


# ---- get_campaigns ----


class TestGetCampaigns:
    @pytest.mark.asyncio
    async def test_success_account_scoped(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": [{"id": "c1"}, {"id": "c2"}]})

        result = await linkedin_ads.execute_action("get_campaigns", {"account_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["campaigns"]) == 2
        url = fetch_url(mock_context)
        assert "/adAccounts/123/adCampaigns" in url
        assert "pageSize=25" in url
        assert "count=" not in url
        assert result.result.data["next_page_token"] is None

    @pytest.mark.asyncio
    async def test_cursor_pagination(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": [], "metadata": {"nextPageToken": "TOK2"}})

        result = await linkedin_ads.execute_action(
            "get_campaigns", {"account_id": "123", "page_size": 50, "page_token": "TOK1"}, mock_context
        )

        assert result.type == ResultType.ACTION
        url = fetch_url(mock_context)
        assert "pageSize=50" in url
        assert "pageToken=TOK1" in url
        assert result.result.data["next_page_token"] == "TOK2"

    @pytest.mark.asyncio
    async def test_status_filter_compact_syntax(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": []})

        await linkedin_ads.execute_action("get_campaigns", {"account_id": "123", "status": "ACTIVE"}, mock_context)

        assert "search=(status:(values:List(ACTIVE)))" in fetch_url(mock_context)

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await linkedin_ads.execute_action("get_campaigns", {"account_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "boom" in result.result.message


# ---- get_campaign ----


class TestGetCampaign:
    @pytest.mark.asyncio
    async def test_success_account_scoped_path(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "123", "name": "Test Campaign"})

        result = await linkedin_ads.execute_action(
            "get_campaign", {"account_id": "456", "campaign_id": "urn:li:sponsoredCampaign:123"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["campaign"]["name"] == "Test Campaign"
        assert fetch_url(mock_context).endswith("/adAccounts/456/adCampaigns/123")

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 404: not found")

        result = await linkedin_ads.execute_action(
            "get_campaign", {"account_id": "456", "campaign_id": "123"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message


# ---- get_campaign_groups ----


class TestGetCampaignGroups:
    @pytest.mark.asyncio
    async def test_success_account_scoped(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": [{"id": "g1"}, {"id": "g2"}]})

        result = await linkedin_ads.execute_action("get_campaign_groups", {"account_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["campaign_groups"]) == 2
        url = fetch_url(mock_context)
        assert "/adAccounts/123/adCampaignGroups" in url
        assert "pageSize=25" in url
        assert "count=" not in url
        assert result.result.data["next_page_token"] is None

    @pytest.mark.asyncio
    async def test_cursor_pagination(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": [], "metadata": {"nextPageToken": "TOK2"}})

        result = await linkedin_ads.execute_action(
            "get_campaign_groups", {"account_id": "123", "page_size": 50, "page_token": "TOK1"}, mock_context
        )

        assert result.type == ResultType.ACTION
        url = fetch_url(mock_context)
        assert "pageSize=50" in url
        assert "pageToken=TOK1" in url
        assert result.result.data["next_page_token"] == "TOK2"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await linkedin_ads.execute_action("get_campaign_groups", {"account_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- get_creatives ----


class TestGetCreatives:
    @pytest.mark.asyncio
    async def test_success_criteria_finder(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": [{"id": "cr1"}]})

        result = await linkedin_ads.execute_action("get_creatives", {"account_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION
        url = fetch_url(mock_context)
        assert "/adAccounts/123/creatives" in url
        assert "q=criteria" in url
        assert "pageSize=25" in url
        assert "count=" not in url
        assert result.result.data["next_page_token"] is None
        # The criteria finder requires the Rest.li FINDER method header.
        assert mock_context.fetch.call_args.kwargs["headers"]["X-RestLi-Method"] == "FINDER"

    @pytest.mark.asyncio
    async def test_cursor_pagination(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": [], "metadata": {"nextPageToken": "TOK2"}})

        result = await linkedin_ads.execute_action(
            "get_creatives", {"account_id": "123", "page_size": 50, "page_token": "TOK1"}, mock_context
        )

        assert result.type == ResultType.ACTION
        url = fetch_url(mock_context)
        assert "pageSize=50" in url
        assert "pageToken=TOK1" in url
        assert result.result.data["next_page_token"] == "TOK2"

    @pytest.mark.asyncio
    async def test_campaign_filter_encoded(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": []})

        await linkedin_ads.execute_action("get_creatives", {"account_id": "123", "campaign_id": "999"}, mock_context)

        assert "campaigns=List(urn%3Ali%3AsponsoredCampaign%3A999)" in fetch_url(mock_context)

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await linkedin_ads.execute_action("get_creatives", {"account_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- get_ad_analytics ----


class TestGetAdAnalytics:
    @pytest.mark.asyncio
    async def test_success_compact_query(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": [{"impressions": 1000}]})

        result = await linkedin_ads.execute_action(
            "get_ad_analytics",
            {"account_id": "123", "start_date": "2026-06-01", "end_date": "2026-06-30"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        url = fetch_url(mock_context)
        assert "dateRange=(start:(year:2026,month:6,day:1),end:(year:2026,month:6,day:30))" in url
        assert "accounts=List(urn%3Ali%3AsponsoredAccount%3A123)" in url
        assert f"fields={ANALYTICS_FIELDS}" in url

    @pytest.mark.asyncio
    async def test_invalid_date_returns_action_error(self, mock_context):
        result = await linkedin_ads.execute_action(
            "get_ad_analytics",
            {"account_id": "123", "start_date": "nope", "end_date": "2026-06-30"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Invalid date format" in result.result.message

    @pytest.mark.asyncio
    async def test_campaign_ids_encoded(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": []})

        await linkedin_ads.execute_action(
            "get_ad_analytics",
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


class TestGetAdAccountUsers:
    @pytest.mark.asyncio
    async def test_success_accounts_finder(self, mock_context):
        mock_context.fetch.return_value = ok({"elements": [{"user": "urn:li:person:abc", "role": "ADMIN"}]})

        result = await linkedin_ads.execute_action("get_ad_account_users", {"account_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION
        assert len(result.result.data["users"]) == 1
        url = fetch_url(mock_context)
        assert "q=accounts" in url
        assert "accounts=List(urn%3Ali%3AsponsoredAccount%3A123)" in url

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await linkedin_ads.execute_action("get_ad_account_users", {"account_id": "123"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- create_campaign ----


CREATE_INPUTS = {
    "account_id": "123456789",
    "campaign_group_id": "111222333",
    "name": "New Campaign",
    "objective_type": "WEBSITE_VISIT",
    "type": "SPONSORED_UPDATES",
    "daily_budget_amount": 100,
}


class TestCreateCampaign:
    @pytest.mark.asyncio
    async def test_success_account_scoped_post(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "new-123"})

        result = await linkedin_ads.execute_action("create_campaign", CREATE_INPUTS, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["campaign_id"] == "new-123"
        call = mock_context.fetch.call_args
        assert str(call.args[0]).endswith("/adAccounts/123456789/adCampaigns")
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"]["account"] == "urn:li:sponsoredAccount:123456789"

    @pytest.mark.asyncio
    async def test_campaign_id_read_from_restli_header(self, mock_context):
        # LinkedIn returns the new campaign id in the x-restli-id header, not the body.
        mock_context.fetch.return_value = FetchResponse(status=201, headers={"x-restli-id": "999888"}, data=None)

        result = await linkedin_ads.execute_action("create_campaign", CREATE_INPUTS, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["campaign_id"] == "999888"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("bad request")

        result = await linkedin_ads.execute_action("create_campaign", CREATE_INPUTS, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "bad request" in result.result.message


# ---- update_campaign ----


class TestUpdateCampaign:
    @pytest.mark.asyncio
    async def test_success_partial_update(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)

        result = await linkedin_ads.execute_action(
            "update_campaign", {"account_id": "456", "campaign_id": "123", "name": "Renamed"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert "updated" in result.result.data["message"]
        call = mock_context.fetch.call_args
        assert str(call.args[0]).endswith("/adAccounts/456/adCampaigns/123")
        assert call.kwargs["headers"]["X-RestLi-Method"] == "PARTIAL_UPDATE"
        assert call.kwargs["json"]["patch"]["$set"]["name"] == "Renamed"

    @pytest.mark.asyncio
    async def test_no_fields_returns_action_error(self, mock_context):
        result = await linkedin_ads.execute_action(
            "update_campaign", {"account_id": "456", "campaign_id": "123"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "No update fields" in result.result.message


# ---- pause_campaign ----


class TestPauseCampaign:
    @pytest.mark.asyncio
    async def test_success_sends_paused(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)

        result = await linkedin_ads.execute_action(
            "pause_campaign", {"account_id": "456", "campaign_id": "123"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert "paused" in result.result.data["message"]
        call = mock_context.fetch.call_args
        assert str(call.args[0]).endswith("/adAccounts/456/adCampaigns/123")
        assert call.kwargs["json"]["patch"]["$set"]["status"] == "PAUSED"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await linkedin_ads.execute_action(
            "pause_campaign", {"account_id": "456", "campaign_id": "123"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- activate_campaign ----


class TestActivateCampaign:
    @pytest.mark.asyncio
    async def test_success_sends_active(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)

        result = await linkedin_ads.execute_action(
            "activate_campaign", {"account_id": "456", "campaign_id": "123"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert "activated" in result.result.data["message"]
        call = mock_context.fetch.call_args
        assert call.kwargs["json"]["patch"]["$set"]["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await linkedin_ads.execute_action(
            "activate_campaign", {"account_id": "456", "campaign_id": "123"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
