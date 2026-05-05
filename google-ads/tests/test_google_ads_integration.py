"""
End-to-end integration tests for the Google Ads integration.

These tests call the real Google Ads API and require a valid OAuth access token
set in the GOOGLE_ADS_ACCESS_TOKEN environment variable (via .env or export).

Run with:
    pytest google-ads/tests/test_google_ads_integration.py -m integration

Never runs in CI -- the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib
import importlib.util

os.environ.setdefault("ADWORDS_DEVELOPER_TOKEN", "placeholder")  # nosec B105
os.environ.setdefault("ADWORDS_CLIENT_ID", "placeholder")  # nosec B105
os.environ.setdefault("ADWORDS_CLIENT_SECRET", "placeholder")  # nosec B105

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock, patch  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("google_ads_mod", os.path.join(_parent, "google_ads.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

google_ads = _mod.google_ads

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("GOOGLE_ADS_ACCESS_TOKEN", "")
LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
CUSTOMER_ID = os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "")
DEVELOPER_TOKEN = os.environ.get("ADWORDS_DEVELOPER_TOKEN", "")
TEST_CAMPAIGN_ID = os.environ.get("GOOGLE_ADS_TEST_CAMPAIGN_ID", "")
TEST_AD_GROUP_ID = os.environ.get("GOOGLE_ADS_TEST_AD_GROUP_ID", "")


def require_campaign_id():
    if not TEST_CAMPAIGN_ID:
        pytest.skip("GOOGLE_ADS_TEST_CAMPAIGN_ID not set")


def require_ad_group_id():
    if not TEST_AD_GROUP_ID:
        pytest.skip("GOOGLE_ADS_TEST_AD_GROUP_ID not set")


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("GOOGLE_ADS_ACCESS_TOKEN not set — skipping integration tests")
    if not LOGIN_CUSTOMER_ID or not CUSTOMER_ID:
        pytest.skip("GOOGLE_ADS_LOGIN_CUSTOMER_ID and GOOGLE_ADS_CUSTOMER_ID must be set")
    if not DEVELOPER_TOKEN or DEVELOPER_TOKEN == "placeholder":
        pytest.skip("ADWORDS_DEVELOPER_TOKEN not set")

    from google.ads.googleads.client import GoogleAdsClient
    from google.oauth2.credentials import Credentials

    def _client_from_access_token(refresh_token: str, login_customer_id=None):
        credentials = Credentials(token=ACCESS_TOKEN)
        kwargs = {
            "credentials": credentials,
            "developer_token": DEVELOPER_TOKEN,
            "use_proto_plus": True,
        }
        if login_customer_id:
            kwargs["login_customer_id"] = login_customer_id
        return GoogleAdsClient(**kwargs)

    _mod._get_google_ads_client = _client_from_access_token

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock()
    ctx.auth = {"credentials": {"refresh_token": "access-token-flow"}}  # nosec B105
    return ctx


@pytest.fixture
def base_inputs():
    return {"login_customer_id": LOGIN_CUSTOMER_ID, "customer_id": CUSTOMER_ID}


# ===========================================================================
# Read-Only Tests
# ===========================================================================


class TestGetAccessibleAccounts:
    @pytest.mark.asyncio
    async def test_returns_accounts_list(self, live_context):
        result = await google_ads.execute_action("get_accessible_accounts", {}, live_context)
        assert result.type == ResultType.ACTION
        assert "accounts" in result.result.data
        assert isinstance(result.result.data["accounts"], list)

    @pytest.mark.asyncio
    async def test_accounts_have_expected_fields(self, live_context):
        result = await google_ads.execute_action("get_accessible_accounts", {}, live_context)
        assert result.type == ResultType.ACTION
        if not result.result.data.get("accounts"):
            pytest.skip("No accounts returned")
        for account in result.result.data["accounts"]:
            assert "customer_id" in account
            assert "resource_name" in account
            assert "descriptive_name" in account
            assert "currency_code" in account


class TestRetrieveCampaignMetrics:
    @pytest.mark.asyncio
    async def test_with_last_7_days_range(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "retrieve_campaign_metrics",
            {**base_inputs, "date_ranges": ["last 7 days"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "results" in result.result.data

    @pytest.mark.asyncio
    async def test_results_have_date_range_and_data_keys(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "retrieve_campaign_metrics",
            {**base_inputs, "date_ranges": ["last 7 days"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        for entry in result.result.data["results"]:
            assert "date_range" in entry
            assert "data" in entry
            assert isinstance(entry["data"], list)


class TestRetrieveKeywordMetrics:
    @pytest.mark.asyncio
    async def test_with_date_range_and_campaign_id(self, live_context, base_inputs):
        require_campaign_id()
        result = await google_ads.execute_action(
            "retrieve_keyword_metrics",
            {
                **base_inputs,
                "date_ranges": ["last 7 days"],
                "ad_group_ids": [],
                "campaign_ids": [TEST_CAMPAIGN_ID],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "results" in result.result.data

    @pytest.mark.asyncio
    async def test_results_structure(self, live_context, base_inputs):
        require_campaign_id()
        result = await google_ads.execute_action(
            "retrieve_keyword_metrics",
            {
                **base_inputs,
                "date_ranges": ["last 7 days"],
                "ad_group_ids": [],
                "campaign_ids": [TEST_CAMPAIGN_ID],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        for entry in result.result.data["results"]:
            assert "date_range" in entry
            assert "data" in entry


class TestRetrieveAdGroupMetrics:
    @pytest.mark.asyncio
    async def test_returns_results(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "retrieve_ad_group_metrics",
            {**base_inputs, "date_ranges": ["last 7 days"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "results" in result.result.data

    @pytest.mark.asyncio
    async def test_result_entries_have_correct_structure(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "retrieve_ad_group_metrics",
            {**base_inputs, "date_ranges": ["last 7 days"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        for entry in result.result.data["results"]:
            assert "date_range" in entry
            assert "data" in entry
            assert isinstance(entry["data"], list)


class TestRetrieveAdMetrics:
    @pytest.mark.asyncio
    async def test_returns_results(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "retrieve_ad_metrics",
            {**base_inputs, "date_ranges": ["last 7 days"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "results" in result.result.data

    @pytest.mark.asyncio
    async def test_result_entries_have_correct_structure(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "retrieve_ad_metrics",
            {**base_inputs, "date_ranges": ["last 7 days"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        for entry in result.result.data["results"]:
            assert "date_range" in entry
            assert "data" in entry
            assert isinstance(entry["data"], list)


class TestRetrieveSearchTerms:
    @pytest.mark.asyncio
    async def test_with_date_range(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "retrieve_search_terms",
            {**base_inputs, "date_ranges": ["last 7 days"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "results" in result.result.data

    @pytest.mark.asyncio
    async def test_result_entries_have_correct_structure(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "retrieve_search_terms",
            {**base_inputs, "date_ranges": ["last 7 days"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        for entry in result.result.data["results"]:
            assert "date_range" in entry
            assert "data" in entry


class TestGetActiveAdUrls:
    @pytest.mark.asyncio
    async def test_returns_active_ads_and_total_count(self, live_context, base_inputs):
        result = await google_ads.execute_action("get_active_ad_urls", base_inputs, live_context)
        assert result.type == ResultType.ACTION
        assert "active_ads" in result.result.data
        assert "total_count" in result.result.data
        assert isinstance(result.result.data["active_ads"], list)
        assert isinstance(result.result.data["total_count"], int)
        assert result.result.data["total_count"] == len(result.result.data["active_ads"])


class TestGenerateKeywordIdeas:
    @pytest.mark.asyncio
    async def test_with_seed_keywords_returns_keyword_ideas(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "generate_keyword_ideas",
            {**base_inputs, "seed_keywords": ["digital marketing", "seo tools"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "keyword_ideas" in result.result.data
        assert isinstance(result.result.data["keyword_ideas"], list)

    @pytest.mark.asyncio
    async def test_keyword_idea_entries_have_correct_fields(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "generate_keyword_ideas",
            {**base_inputs, "seed_keywords": ["digital marketing"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        if not result.result.data.get("keyword_ideas"):
            pytest.skip("No keyword ideas returned")
        for idea in result.result.data["keyword_ideas"]:
            assert "keyword" in idea
            assert "avg_monthly_searches" in idea
            assert "competition" in idea


class TestGenerateKeywordHistoricalMetrics:
    @pytest.mark.asyncio
    async def test_with_keywords_list_returns_keyword_metrics(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "generate_keyword_historical_metrics",
            {**base_inputs, "keywords": ["digital marketing", "online advertising"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "keyword_metrics" in result.result.data
        assert isinstance(result.result.data["keyword_metrics"], list)

    @pytest.mark.asyncio
    async def test_keyword_metric_entries_have_correct_fields(self, live_context, base_inputs):
        result = await google_ads.execute_action(
            "generate_keyword_historical_metrics",
            {**base_inputs, "keywords": ["digital marketing"]},
            live_context,
        )
        assert result.type == ResultType.ACTION
        if not result.result.data.get("keyword_metrics"):
            pytest.skip("No keyword metrics returned")
        for metric in result.result.data["keyword_metrics"]:
            assert "keyword" in metric
            assert "avg_monthly_searches" in metric
            assert "competition" in metric
            assert "monthly_search_volumes" in metric


# ===========================================================================
# Destructive Tests
# ===========================================================================


class TestCampaignLifecycle:
    @pytest.mark.asyncio
    @pytest.mark.destructive
    async def test_create_update_remove_campaign(self, live_context, base_inputs):
        create_result = await google_ads.execute_action(
            "create_campaign",
            {
                **base_inputs,
                "campaign_name": "Integration Test Campaign — Delete Me",
                "budget_amount_micros": 10_000_000,
                "bidding_strategy": "MANUAL_CPC",
            },
            live_context,
        )
        assert create_result.type == ResultType.ACTION
        assert "campaign_id" in create_result.result.data
        campaign_id = create_result.result.data["campaign_id"]

        update_result = await google_ads.execute_action(
            "update_campaign",
            {**base_inputs, "campaign_id": campaign_id, "name": "Integration Test Campaign — Renamed"},
            live_context,
        )
        assert update_result.type == ResultType.ACTION
        assert "campaign_resource_name" in update_result.result.data

        remove_result = await google_ads.execute_action(
            "remove_campaign",
            {**base_inputs, "campaign_id": campaign_id},
            live_context,
        )
        assert remove_result.type == ResultType.ACTION
        assert remove_result.result.data["status"] == "REMOVED"


class TestAdGroupLifecycle:
    @pytest.mark.asyncio
    @pytest.mark.destructive
    async def test_create_update_remove_ad_group(self, live_context, base_inputs):
        require_campaign_id()

        create_result = await google_ads.execute_action(
            "create_ad_group",
            {
                **base_inputs,
                "campaign_id": TEST_CAMPAIGN_ID,
                "ad_group_name": "Integration Test Ad Group — Delete Me",
                "cpc_bid_micros": 1_000_000,
                "status": "PAUSED",
            },
            live_context,
        )
        assert create_result.type == ResultType.ACTION
        assert "ad_group_id" in create_result.result.data
        ad_group_id = create_result.result.data["ad_group_id"]

        update_result = await google_ads.execute_action(
            "update_ad_group",
            {**base_inputs, "ad_group_id": ad_group_id, "name": "Integration Test Ad Group — Renamed"},
            live_context,
        )
        assert update_result.type == ResultType.ACTION
        assert "ad_group_resource_name" in update_result.result.data

        remove_result = await google_ads.execute_action(
            "remove_ad_group",
            {**base_inputs, "ad_group_id": ad_group_id},
            live_context,
        )
        assert remove_result.type == ResultType.ACTION
        assert remove_result.result.data["status"] == "REMOVED"


class TestKeywordLifecycle:
    @pytest.mark.asyncio
    @pytest.mark.destructive
    async def test_add_and_remove_keywords(self, live_context, base_inputs):
        require_ad_group_id()

        add_result = await google_ads.execute_action(
            "add_keywords",
            {
                **base_inputs,
                "ad_group_id": TEST_AD_GROUP_ID,
                "keywords": [{"text": "integration test keyword delete me", "match_type": "BROAD"}],
            },
            live_context,
        )
        assert add_result.type == ResultType.ACTION
        assert "added_keywords" in add_result.result.data
        kw = add_result.result.data["added_keywords"][0]
        assert "resource_name" in kw

        resource_name = kw["resource_name"]
        criterion_id = resource_name.split("~")[-1] if "~" in resource_name else None
        if not criterion_id:
            pytest.skip("Could not extract criterion_id from resource_name")

        remove_result = await google_ads.execute_action(
            "remove_keyword",
            {**base_inputs, "ad_group_id": TEST_AD_GROUP_ID, "criterion_id": criterion_id},
            live_context,
        )
        assert remove_result.type == ResultType.ACTION
        assert remove_result.result.data["status"] == "REMOVED"


class TestNegativeKeywords:
    @pytest.mark.asyncio
    @pytest.mark.destructive
    async def test_add_negative_keywords_to_campaign(self, live_context, base_inputs):
        require_campaign_id()

        result = await google_ads.execute_action(
            "add_negative_keywords_to_campaign",
            {
                **base_inputs,
                "campaign_id": TEST_CAMPAIGN_ID,
                "keywords": [{"text": "integration test negative kw", "match_type": "BROAD"}],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "added_negative_keywords" in result.result.data
        assert result.result.data["campaign_id"] == TEST_CAMPAIGN_ID
        assert result.result.data["status"] == "success"

    @pytest.mark.asyncio
    @pytest.mark.destructive
    async def test_add_negative_keywords_to_ad_group(self, live_context, base_inputs):
        require_ad_group_id()

        result = await google_ads.execute_action(
            "add_negative_keywords_to_ad_group",
            {
                **base_inputs,
                "ad_group_id": TEST_AD_GROUP_ID,
                "keywords": [{"text": "integration test neg kw ad group", "match_type": "PHRASE"}],
            },
            live_context,
        )
        assert result.type == ResultType.ACTION
        assert "added_negative_keywords" in result.result.data
        assert result.result.data["ad_group_id"] == TEST_AD_GROUP_ID
        assert result.result.data["status"] == "success"
