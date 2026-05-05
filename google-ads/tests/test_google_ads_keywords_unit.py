import os
import sys
import importlib

os.environ.setdefault("ADWORDS_DEVELOPER_TOKEN", "test_developer_token")  # nosec B105
os.environ.setdefault("ADWORDS_CLIENT_ID", "test_client_id")  # nosec B105
os.environ.setdefault("ADWORDS_CLIENT_SECRET", "test_client_secret")  # nosec B105

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_deps = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies"))
sys.path.insert(0, _parent)
sys.path.insert(0, _deps)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402
from autohive_integrations_sdk.integration import ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "google_ads_mod", os.path.join(_parent, "google_ads.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

google_ads = _mod.google_ads

pytestmark = pytest.mark.unit

BASE_INPUTS = {"login_customer_id": "1234567890", "customer_id": "9876543210"}


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"credentials": {"refresh_token": "test_refresh_token"}}  # nosec B105
    return ctx


@pytest.fixture
def mock_context_no_token():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"credentials": {}}
    return ctx


@pytest.fixture
def mock_gads_client():
    with patch.object(_mod, "_get_google_ads_client") as mock_factory:
        client = MagicMock(name="GoogleAdsClient")
        mock_factory.return_value = client
        yield client


_KEYWORD_PROTO_ROW = {
    "campaign": {"id": "123", "name": "Test Campaign"},
    "ad_group": {"id": "456", "name": "Test Ad Group"},
    "ad_group_criterion": {
        "criterion_id": "789",
        "status": "ENABLED",
        "keyword": {"text": "test keyword", "match_type": "BROAD"},
        "quality_info": {"quality_score": 7},
    },
    "metrics": {
        "impressions": 500,
        "clicks": 25,
        "cost_micros": 12500000,
        "all_conversions": 2.0,
        "conversion_rate": 0.08,
        "interaction_rate": 0.05,
        "average_cpc": 500000,
    },
}


# ===========================================================================
# 1. retrieve_keyword_metrics
# ===========================================================================


_KW_METRICS_INPUTS = {**BASE_INPUTS, "ad_group_ids": ["456"], "campaign_ids": ["123"]}


class TestRetrieveKeywordMetrics:
    @pytest.mark.asyncio
    async def test_missing_date_ranges(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action(
            "retrieve_keyword_metrics", {**_KW_METRICS_INPUTS}, mock_context
        )
        assert result.type != ResultType.ACTION
        assert "date_ranges" in str(result.result)

    @pytest.mark.asyncio
    async def test_returns_empty_results(self, mock_context, mock_gads_client):
        mock_gads_client.get_service.return_value.search.return_value = []

        result = await google_ads.execute_action(
            "retrieve_keyword_metrics",
            {**_KW_METRICS_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "results" in result.result.data
        assert len(result.result.data["results"]) == 1
        assert result.result.data["results"][0]["data"] == []

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        result = await google_ads.execute_action(
            "retrieve_keyword_metrics",
            {**_KW_METRICS_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context_no_token,
        )
        assert result.type != ResultType.ACTION

    @pytest.mark.asyncio
    async def test_returns_keyword_data_from_proto_rows(
        self, mock_context, mock_gads_client
    ):
        mock_row = MagicMock()
        mock_gads_client.get_service.return_value.search.return_value = [mock_row]

        with patch("proto.Message.to_dict") as mock_to_dict:
            mock_to_dict.return_value = _KEYWORD_PROTO_ROW

            result = await google_ads.execute_action(
                "retrieve_keyword_metrics",
                {**_KW_METRICS_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
                mock_context,
            )

        assert result.type == ResultType.ACTION
        assert len(result.result.data["results"]) == 1
        kw_entry = result.result.data["results"][0]["data"][0]
        assert kw_entry["Keyword"] == "test keyword"
        assert kw_entry["Keyword ID"] == "789"
        assert kw_entry["Cost"] == 12.5


# ===========================================================================
# 2. add_keywords
# ===========================================================================


def _setup_add_keywords_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    result_mock = MagicMock()
    result_mock.resource_name = "customers/123/adGroupCriteria/456~789"
    mock_service.mutate_ad_group_criteria.return_value.results = [result_mock]

    mock_gads_client.get_type.return_value = MagicMock()
    mock_gads_client.enums.AdGroupCriterionStatusEnum.ENABLED = "ENABLED"
    mock_gads_client.enums.KeywordMatchTypeEnum.BROAD = "BROAD"
    mock_gads_client.enums.KeywordMatchTypeEnum.EXACT = "EXACT"
    mock_gads_client.enums.KeywordMatchTypeEnum.PHRASE = "PHRASE"

    return mock_service


class TestAddKeywords:
    @pytest.mark.asyncio
    async def test_missing_ad_group_id_and_keywords(
        self, mock_context, mock_gads_client
    ):
        result = await google_ads.execute_action(
            "add_keywords", {**BASE_INPUTS}, mock_context
        )
        assert result.type != ResultType.ACTION

    @pytest.mark.asyncio
    async def test_adds_keywords_successfully(self, mock_context, mock_gads_client):
        _setup_add_keywords_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "add_keywords",
            {
                **BASE_INPUTS,
                "ad_group_id": "456",
                "keywords": [{"text": "test keyword", "match_type": "BROAD"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "added_keywords" in result.result.data
        assert len(result.result.data["added_keywords"]) == 1
        kw = result.result.data["added_keywords"][0]
        assert kw["keyword_text"] == "test keyword"
        assert "resource_name" in kw

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        _setup_add_keywords_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_ad_group_criteria.side_effect = Exception(
            "mutate failed"
        )

        result = await google_ads.execute_action(
            "add_keywords",
            {
                **BASE_INPUTS,
                "ad_group_id": "456",
                "keywords": [{"text": "test", "match_type": "BROAD"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        result = await google_ads.execute_action(
            "add_keywords",
            {
                **BASE_INPUTS,
                "ad_group_id": "456",
                "keywords": [{"text": "test", "match_type": "BROAD"}],
            },
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR


# ===========================================================================
# 3. add_negative_keywords_to_campaign
# ===========================================================================


def _setup_add_neg_campaign_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    result_mock = MagicMock()
    result_mock.resource_name = "customers/123/campaignCriteria/456~789"
    mock_service.mutate_campaign_criteria.return_value.results = [result_mock]
    mock_service.campaign_path.return_value = "customers/9876543210/campaigns/456"

    mock_gads_client.get_type.return_value = MagicMock()
    mock_gads_client.enums.KeywordMatchTypeEnum.BROAD = "BROAD"
    mock_gads_client.enums.KeywordMatchTypeEnum.EXACT = "EXACT"
    mock_gads_client.enums.KeywordMatchTypeEnum.PHRASE = "PHRASE"

    return mock_service


class TestAddNegativeKeywordsToCampaign:
    @pytest.mark.asyncio
    async def test_missing_required_ids(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action(
            "add_negative_keywords_to_campaign", {**BASE_INPUTS}, mock_context
        )
        assert result.type != ResultType.ACTION

    @pytest.mark.asyncio
    async def test_adds_negative_keywords_successfully(
        self, mock_context, mock_gads_client
    ):
        _setup_add_neg_campaign_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "add_negative_keywords_to_campaign",
            {
                **BASE_INPUTS,
                "campaign_id": "456",
                "keywords": [{"text": "free", "match_type": "BROAD"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "added_negative_keywords" in result.result.data
        assert result.result.data["campaign_id"] == "456"
        assert result.result.data["status"] == "success"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        _setup_add_neg_campaign_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_campaign_criteria.side_effect = Exception(
            "mutate failed"
        )

        result = await google_ads.execute_action(
            "add_negative_keywords_to_campaign",
            {
                **BASE_INPUTS,
                "campaign_id": "456",
                "keywords": [{"text": "free", "match_type": "BROAD"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        result = await google_ads.execute_action(
            "add_negative_keywords_to_campaign",
            {**BASE_INPUTS, "campaign_id": "456", "keywords": [{"text": "free"}]},
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR


# ===========================================================================
# 4. add_negative_keywords_to_ad_group
# ===========================================================================


def _setup_add_neg_ad_group_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    result_mock = MagicMock()
    result_mock.resource_name = "customers/123/adGroupCriteria/456~789"
    mock_service.mutate_ad_group_criteria.return_value.results = [result_mock]
    mock_service.ad_group_path.return_value = "customers/9876543210/adGroups/456"

    mock_gads_client.get_type.return_value = MagicMock()
    mock_gads_client.enums.KeywordMatchTypeEnum.BROAD = "BROAD"
    mock_gads_client.enums.KeywordMatchTypeEnum.EXACT = "EXACT"
    mock_gads_client.enums.KeywordMatchTypeEnum.PHRASE = "PHRASE"

    return mock_service


class TestAddNegativeKeywordsToAdGroup:
    @pytest.mark.asyncio
    async def test_missing_required_ids(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action(
            "add_negative_keywords_to_ad_group", {**BASE_INPUTS}, mock_context
        )
        assert result.type != ResultType.ACTION

    @pytest.mark.asyncio
    async def test_adds_negative_keywords_successfully(
        self, mock_context, mock_gads_client
    ):
        _setup_add_neg_ad_group_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "add_negative_keywords_to_ad_group",
            {
                **BASE_INPUTS,
                "ad_group_id": "456",
                "keywords": [{"text": "cheap", "match_type": "EXACT"}],
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "added_negative_keywords" in result.result.data
        assert result.result.data["ad_group_id"] == "456"
        assert result.result.data["status"] == "success"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        _setup_add_neg_ad_group_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_ad_group_criteria.side_effect = Exception(
            "mutate failed"
        )

        result = await google_ads.execute_action(
            "add_negative_keywords_to_ad_group",
            {**BASE_INPUTS, "ad_group_id": "456", "keywords": [{"text": "cheap"}]},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        result = await google_ads.execute_action(
            "add_negative_keywords_to_ad_group",
            {**BASE_INPUTS, "ad_group_id": "456", "keywords": [{"text": "cheap"}]},
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR


# ===========================================================================
# 5. update_keyword
# ===========================================================================


def _setup_update_keyword_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    update_result = MagicMock()
    update_result.resource_name = "customers/9876543210/adGroupCriteria/456~789"
    mock_service.mutate_ad_group_criteria.return_value.results = [update_result]
    mock_service.ad_group_criterion_path.return_value = (
        "customers/9876543210/adGroupCriteria/456~789"
    )

    mock_gads_client.get_type.return_value = MagicMock()
    mock_gads_client.enums.AdGroupCriterionStatusEnum.ENABLED = "ENABLED"
    mock_gads_client.enums.AdGroupCriterionStatusEnum.PAUSED = "PAUSED"

    return mock_service


class TestUpdateKeyword:
    @pytest.mark.asyncio
    async def test_missing_ad_group_and_criterion(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action(
            "update_keyword", {**BASE_INPUTS, "status": "PAUSED"}, mock_context
        )
        assert result.type != ResultType.ACTION

    @pytest.mark.asyncio
    async def test_updates_keyword_successfully(self, mock_context, mock_gads_client):
        _setup_update_keyword_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "update_keyword",
            {
                **BASE_INPUTS,
                "ad_group_id": "456",
                "criterion_id": "789",
                "status": "PAUSED",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "criterion_id" in result.result.data
        assert result.result.data["criterion_id"] == "789"
        assert result.result.data["status"] == "PAUSED"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        _setup_update_keyword_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_ad_group_criteria.side_effect = Exception(
            "update failed"
        )

        result = await google_ads.execute_action(
            "update_keyword",
            {
                **BASE_INPUTS,
                "ad_group_id": "456",
                "criterion_id": "789",
                "status": "ENABLED",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        result = await google_ads.execute_action(
            "update_keyword",
            {
                **BASE_INPUTS,
                "ad_group_id": "456",
                "criterion_id": "789",
                "status": "PAUSED",
            },
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR


# ===========================================================================
# 6. remove_keyword
# ===========================================================================


def _setup_remove_keyword_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    remove_result = MagicMock()
    remove_result.resource_name = "customers/9876543210/adGroupCriteria/456~789"
    mock_service.mutate_ad_group_criteria.return_value.results = [remove_result]
    mock_service.ad_group_criterion_path.return_value = (
        "customers/9876543210/adGroupCriteria/456~789"
    )

    mock_gads_client.get_type.return_value = MagicMock()

    return mock_service


class TestRemoveKeyword:
    @pytest.mark.asyncio
    async def test_missing_ids(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action(
            "remove_keyword", {**BASE_INPUTS}, mock_context
        )
        assert result.type != ResultType.ACTION

    @pytest.mark.asyncio
    async def test_removes_keyword_successfully(self, mock_context, mock_gads_client):
        _setup_remove_keyword_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "remove_keyword",
            {**BASE_INPUTS, "ad_group_id": "456", "criterion_id": "789"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["status"] == "REMOVED"
        assert "removed_keyword_resource_name" in result.result.data
        assert result.result.data["criterion_id"] == "789"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        _setup_remove_keyword_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_ad_group_criteria.side_effect = Exception(
            "remove failed"
        )

        result = await google_ads.execute_action(
            "remove_keyword",
            {**BASE_INPUTS, "ad_group_id": "456", "criterion_id": "789"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "remove failed" in result.result.message

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        result = await google_ads.execute_action(
            "remove_keyword",
            {**BASE_INPUTS, "ad_group_id": "456", "criterion_id": "789"},
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR
