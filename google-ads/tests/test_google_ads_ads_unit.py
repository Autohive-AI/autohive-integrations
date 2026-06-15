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

_spec = importlib.util.spec_from_file_location("google_ads_mod", os.path.join(_parent, "google_ads.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

google_ads = _mod.google_ads

pytestmark = pytest.mark.unit

BASE_INPUTS = {"login_customer_id": "1234567890", "customer_id": "9876543210"}


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "test_access_token"}}  # nosec B105
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


_AD_PROTO_ROW = {
    "ad_group_ad": {
        "status": "ENABLED",
        "ad": {
            "id": "789",
            "name": "Test Ad",
            "type": "RESPONSIVE_SEARCH_AD",
            "final_urls": ["https://example.com"],
            "responsive_search_ad": {
                "headlines": [{"text": "Headline 1"}, {"text": "Headline 2"}],
                "descriptions": [{"text": "Description 1"}],
            },
        },
    },
    "ad_group": {"id": "456", "name": "Test Ad Group"},
    "campaign": {"id": "123", "name": "Test Campaign"},
    "metrics": {
        "impressions": 1000,
        "clicks": 50,
        "ctr": 0.05,
        "average_cpc": 500000,
        "cost_micros": 25000000,
        "conversions": 5.0,
        "conversions_value": 100.0,
        "cost_per_conversion": 5000000,
    },
}


# ===========================================================================
# 1. retrieve_ad_metrics
# ===========================================================================


class TestRetrieveAdMetrics:
    @pytest.mark.asyncio
    async def test_missing_date_ranges(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action("retrieve_ad_metrics", {**BASE_INPUTS}, mock_context)
        assert result.type != ResultType.ACTION
        assert "date_ranges" in str(result.result)

    @pytest.mark.asyncio
    async def test_returns_empty_results(self, mock_context, mock_gads_client):
        mock_gads_client.get_service.return_value.search.return_value = []

        result = await google_ads.execute_action(
            "retrieve_ad_metrics",
            {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "results" in result.result.data
        assert len(result.result.data["results"]) == 1
        assert result.result.data["results"][0]["data"] == []

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        result = await google_ads.execute_action(
            "retrieve_ad_metrics",
            {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        mock_gads_client.get_service.return_value.search.side_effect = Exception("API failure")

        result = await google_ads.execute_action(
            "retrieve_ad_metrics",
            {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context,
        )
        assert result.type != ResultType.ACTION
        assert "API failure" in str(result.result)

    @pytest.mark.asyncio
    async def test_returns_ad_data_from_proto_rows(self, mock_context, mock_gads_client):
        mock_row = MagicMock()
        mock_gads_client.get_service.return_value.search.return_value = [mock_row]

        with patch("proto.Message.to_dict") as mock_to_dict:
            mock_to_dict.return_value = _AD_PROTO_ROW

            result = await google_ads.execute_action(
                "retrieve_ad_metrics",
                {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
                mock_context,
            )

        assert result.type == ResultType.ACTION
        assert len(result.result.data["results"]) == 1
        assert len(result.result.data["results"][0]["data"]) == 1
        ad_entry = result.result.data["results"][0]["data"][0]
        assert ad_entry["ad_id"] == "789"
        assert ad_entry["ad_name"] == "Test Ad"
        assert ad_entry["cost"] == 25.0


# ===========================================================================
# 2. create_responsive_search_ad
# ===========================================================================


def _setup_create_rsa_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    result_mock = MagicMock()
    result_mock.resource_name = "customers/123/adGroupAds/456~789"
    mock_service.mutate_ad_group_ads.return_value.results = [result_mock]

    mock_gads_client.get_type.return_value = MagicMock()
    mock_gads_client.enums.AdGroupAdStatusEnum.PAUSED = "PAUSED"

    return mock_service


_RSA_BASE_INPUTS = {
    **BASE_INPUTS,
    "ad_group_id": "456",
    "headlines": ["Headline One", "Headline Two", "Headline Three"],
    "descriptions": ["Description one here.", "Description two here."],
    "final_url": "https://example.com",
}


class TestCreateResponsiveSearchAd:
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action(
            "create_responsive_search_ad",
            {
                **BASE_INPUTS,
                "headlines": ["H1", "H2", "H3"],
                "descriptions": ["D1", "D2"],
                "final_url": "https://example.com",
            },
            mock_context,
        )
        assert result.type != ResultType.ACTION

    @pytest.mark.asyncio
    async def test_too_few_headlines(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action(
            "create_responsive_search_ad",
            {
                **BASE_INPUTS,
                "ad_group_id": "456",
                "headlines": ["Only One", "Only Two"],
                "descriptions": ["Desc one.", "Desc two."],
                "final_url": "https://example.com",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "3" in result.result.message or "headlines" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_too_few_descriptions(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action(
            "create_responsive_search_ad",
            {
                **BASE_INPUTS,
                "ad_group_id": "456",
                "headlines": ["Headline One", "Headline Two", "Headline Three"],
                "descriptions": ["Only one description."],
                "final_url": "https://example.com",
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "2" in result.result.message or "descriptions" in result.result.message.lower()

    @pytest.mark.asyncio
    async def test_creates_ad_successfully(self, mock_context, mock_gads_client):
        _setup_create_rsa_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "create_responsive_search_ad",
            _RSA_BASE_INPUTS,
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "ad_id" in result.result.data
        assert result.result.data["ad_id"] == "789"

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        result = await google_ads.execute_action(
            "create_responsive_search_ad",
            _RSA_BASE_INPUTS,
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        _setup_create_rsa_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_ad_group_ads.side_effect = Exception("mutate failed")

        result = await google_ads.execute_action(
            "create_responsive_search_ad",
            _RSA_BASE_INPUTS,
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR


# ===========================================================================
# 3. update_ad
# ===========================================================================


def _setup_update_ad_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    update_result = MagicMock()
    update_result.resource_name = "customers/9876543210/adGroupAds/456~789"
    mock_service.mutate_ad_group_ads.return_value.results = [update_result]
    mock_service.ad_group_ad_path.return_value = "customers/9876543210/adGroupAds/456~789"

    mock_gads_client.get_type.return_value = MagicMock()
    mock_gads_client.enums.AdGroupAdStatusEnum.ENABLED = "ENABLED"
    mock_gads_client.enums.AdGroupAdStatusEnum.PAUSED = "PAUSED"

    return mock_service


class TestUpdateAd:
    @pytest.mark.asyncio
    async def test_missing_ad_group_id(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action(
            "update_ad",
            {**BASE_INPUTS, "ad_id": "789", "status": "ENABLED"},
            mock_context,
        )
        assert result.type != ResultType.ACTION

    @pytest.mark.asyncio
    async def test_missing_ad_id(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action(
            "update_ad",
            {**BASE_INPUTS, "ad_group_id": "456", "status": "ENABLED"},
            mock_context,
        )
        assert result.type != ResultType.ACTION

    @pytest.mark.asyncio
    async def test_updates_ad_successfully(self, mock_context, mock_gads_client):
        _setup_update_ad_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "update_ad",
            {**BASE_INPUTS, "ad_group_id": "456", "ad_id": "789", "status": "ENABLED"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "ad_resource_name" in result.result.data
        assert result.result.data["ad_id"] == "789"
        assert result.result.data["status"] == "ENABLED"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        _setup_update_ad_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_ad_group_ads.side_effect = Exception("update failed")

        result = await google_ads.execute_action(
            "update_ad",
            {**BASE_INPUTS, "ad_group_id": "456", "ad_id": "789", "status": "PAUSED"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        result = await google_ads.execute_action(
            "update_ad",
            {**BASE_INPUTS, "ad_group_id": "456", "ad_id": "789", "status": "ENABLED"},
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR


# ===========================================================================
# 4. remove_ad
# ===========================================================================


def _setup_remove_ad_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    remove_result = MagicMock()
    remove_result.resource_name = "customers/9876543210/adGroupAds/456~789"
    mock_service.mutate_ad_group_ads.return_value.results = [remove_result]
    mock_service.ad_group_ad_path.return_value = "customers/9876543210/adGroupAds/456~789"

    mock_gads_client.get_type.return_value = MagicMock()

    return mock_service


class TestRemoveAd:
    @pytest.mark.asyncio
    async def test_missing_ids(self, mock_context, mock_gads_client):
        result = await google_ads.execute_action("remove_ad", {**BASE_INPUTS}, mock_context)
        assert result.type != ResultType.ACTION

    @pytest.mark.asyncio
    async def test_removes_ad_successfully(self, mock_context, mock_gads_client):
        _setup_remove_ad_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "remove_ad",
            {**BASE_INPUTS, "ad_group_id": "456", "ad_id": "789"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["status"] == "REMOVED"
        assert "removed_ad_resource_name" in result.result.data
        assert result.result.data["ad_id"] == "789"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        _setup_remove_ad_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_ad_group_ads.side_effect = Exception("remove failed")

        result = await google_ads.execute_action(
            "remove_ad",
            {**BASE_INPUTS, "ad_group_id": "456", "ad_id": "789"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "remove failed" in result.result.message
