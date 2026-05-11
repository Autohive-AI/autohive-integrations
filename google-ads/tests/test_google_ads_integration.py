"""
End-to-end integration tests for the Google Ads integration.

These tests call the real Google Ads API and require platform OAuth credentials
and Google Ads account IDs in environment variables (via .env or export).

Token extraction recipe:
1. Connect Google Ads in Autohive using the platform OAuth flow.
2. Copy the short-lived OAuth access token into GOOGLE_ADS_ACCESS_TOKEN.
3. Set ADWORDS_DEVELOPER_TOKEN from the Google Ads API Center.
4. Set GOOGLE_ADS_LOGIN_CUSTOMER_ID and GOOGLE_ADS_CUSTOMER_ID without dashes.
5. Optional destructive tests also need GOOGLE_ADS_TEST_CAMPAIGN_ID and
   GOOGLE_ADS_TEST_AD_GROUP_ID for ad group, keyword, and negative keyword flows.

Run with:
    pytest google-ads/tests/test_google_ads_integration.py -m "integration and not destructive"

Run destructive tests deliberately only when the connected account is safe to mutate:
    pytest google-ads/tests/test_google_ads_integration.py -m "integration and destructive"

Never runs in CI -- the default pytest marker filter (-m unit) excludes these,
and the file naming (test_*_integration.py) is not matched by python_files.
"""

import os
import sys
import importlib.util

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("google_ads_mod", os.path.join(_parent, "google_ads.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

google_ads = _mod.google_ads

pytestmark = pytest.mark.integration

TEST_CAMPAIGN_ID = os.environ.get("GOOGLE_ADS_TEST_CAMPAIGN_ID", "")
TEST_AD_GROUP_ID = os.environ.get("GOOGLE_ADS_TEST_AD_GROUP_ID", "")


def require_campaign_id():
    if not TEST_CAMPAIGN_ID:
        pytest.skip("GOOGLE_ADS_TEST_CAMPAIGN_ID not set")


def require_ad_group_id():
    if not TEST_AD_GROUP_ID:
        pytest.skip("GOOGLE_ADS_TEST_AD_GROUP_ID not set")


@pytest.fixture
def live_credentials(env_credentials):
    access_token = env_credentials("GOOGLE_ADS_ACCESS_TOKEN")
    login_customer_id = env_credentials("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
    customer_id = env_credentials("GOOGLE_ADS_CUSTOMER_ID")
    developer_token = env_credentials("ADWORDS_DEVELOPER_TOKEN")

    if not access_token:
        pytest.skip("GOOGLE_ADS_ACCESS_TOKEN not set — skipping integration tests")
    if not login_customer_id or not customer_id:
        pytest.skip("GOOGLE_ADS_LOGIN_CUSTOMER_ID and GOOGLE_ADS_CUSTOMER_ID must be set")
    if not developer_token:
        pytest.skip("ADWORDS_DEVELOPER_TOKEN not set")

    return {
        "access_token": access_token,
        "login_customer_id": login_customer_id,
        "customer_id": customer_id,
    }


@pytest.fixture
def live_context(live_credentials, make_context):
    return make_context(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": live_credentials["access_token"]},
        }
    )


@pytest.fixture
def base_inputs(live_credentials):
    return {
        "login_customer_id": live_credentials["login_customer_id"],
        "customer_id": live_credentials["customer_id"],
    }


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
            {
                **base_inputs,
                "campaign_id": campaign_id,
                "name": "Integration Test Campaign — Renamed",
            },
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
            {
                **base_inputs,
                "ad_group_id": ad_group_id,
                "name": "Integration Test Ad Group — Renamed",
            },
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
                "keywords": [
                    {
                        "text": "integration test keyword delete me",
                        "match_type": "BROAD",
                    }
                ],
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
            {
                **base_inputs,
                "ad_group_id": TEST_AD_GROUP_ID,
                "criterion_id": criterion_id,
            },
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
