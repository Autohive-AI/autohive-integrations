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


_PROTO_TO_DICT_RETURN = {
    "campaign": {
        "id": "123",
        "name": "Test",
        "status": "ENABLED",
        "advertising_channel_type": "SEARCH",
        "bidding_strategy_type": "TARGET_SPEND",
        "optimization_score": 0.9,
    },
    "metrics": {
        "interactions": "100",
        "interaction_rate": 0.1,
        "average_cost": 1000000,
        "cost_micros": 5000000,
        "impressions": "1000",
        "clicks": "100",
        "conversions_value": 10.0,
        "all_conversions": 5.0,
        "average_cpc": 50000,
        "cost_per_conversion": 1000000,
    },
    "customer": {"currency_code": "USD", "descriptive_name": "Test Account"},
    "campaign_budget": {"amount_micros": 10000000},
}


# ===========================================================================
# 1. retrieve_campaign_metrics
# ===========================================================================


class TestRetrieveCampaignMetrics:
    @pytest.mark.asyncio
    async def test_missing_date_ranges(self, mock_context, mock_gads_client):
        """Omitting date_ranges must return an ActionError mentioning date_ranges."""
        result = await google_ads.execute_action(
            "retrieve_campaign_metrics",
            {**BASE_INPUTS},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "date_ranges" in result.result.message

    @pytest.mark.asyncio
    async def test_returns_empty_results_for_no_campaigns(self, mock_context, mock_gads_client):
        """When the API returns no rows the results list should contain an entry with empty data."""
        mock_gads_client.get_service.return_value.search.return_value = []

        result = await google_ads.execute_action(
            "retrieve_campaign_metrics",
            {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "results" in result.result.data
        assert len(result.result.data["results"]) == 1
        assert result.result.data["results"][0]["data"] == []

    @pytest.mark.asyncio
    async def test_returns_campaign_data(self, mock_context, mock_gads_client):
        """A single API row should surface as a campaign entry in the results."""
        mock_row = MagicMock()
        mock_gads_client.get_service.return_value.search.return_value = [mock_row]

        with patch("proto.Message.to_dict") as mock_to_dict:
            mock_to_dict.return_value = _PROTO_TO_DICT_RETURN

            result = await google_ads.execute_action(
                "retrieve_campaign_metrics",
                {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
                mock_context,
            )

        assert result.type == ResultType.ACTION
        assert len(result.result.data["results"]) == 1
        assert len(result.result.data["results"][0]["data"]) == 1
        campaign_entry = result.result.data["results"][0]["data"][0]
        assert campaign_entry["Campaign ID"] == "123"
        assert campaign_entry["Campaign"] == "Test"

    @pytest.mark.asyncio
    async def test_campaign_metrics_cost_conversion(self, mock_context, mock_gads_client):
        """cost_micros of 5_000_000 should convert to Cost == 5.0."""
        mock_row = MagicMock()
        mock_gads_client.get_service.return_value.search.return_value = [mock_row]

        with patch("proto.Message.to_dict") as mock_to_dict:
            mock_to_dict.return_value = _PROTO_TO_DICT_RETURN

            result = await google_ads.execute_action(
                "retrieve_campaign_metrics",
                {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
                mock_context,
            )

        assert result.type == ResultType.ACTION
        entry = result.result.data["results"][0]["data"][0]
        assert entry["Cost"] == 5.0

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        """Missing refresh_token must return an ActionError."""
        result = await google_ads.execute_action(
            "retrieve_campaign_metrics",
            {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        """An exception raised by the API search is caught per-date-range; the action
        still returns ActionResult, but the date-range entry includes an 'error' key."""
        mock_gads_client.get_service.return_value.search.side_effect = Exception("API failure")

        result = await google_ads.execute_action(
            "retrieve_campaign_metrics",
            {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "error" in result.result.data["results"][0]

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, mock_context, mock_gads_client):
        """Omitting login_customer_id must return a validation error."""
        result = await google_ads.execute_action(
            "retrieve_campaign_metrics",
            {"customer_id": "9876543210", "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context,
        )
        assert result.type != ResultType.ACTION


# ===========================================================================
# 2. create_campaign
# ===========================================================================


def _setup_create_campaign_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    budget_result = MagicMock()
    budget_result.resource_name = "customers/123/campaignBudgets/456"
    mock_service.mutate_campaign_budgets.return_value.results = [budget_result]

    campaign_result = MagicMock()
    campaign_result.resource_name = "customers/123/campaigns/789"
    mock_service.mutate_campaigns.return_value.results = [campaign_result]

    mock_gads_client.get_type.return_value = MagicMock()
    mock_gads_client.enums.BudgetDeliveryMethodEnum.STANDARD = "STANDARD"
    mock_gads_client.enums.AdvertisingChannelTypeEnum.SEARCH = "SEARCH"
    mock_gads_client.enums.CampaignStatusEnum.PAUSED = "PAUSED"
    mock_gads_client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING = "NO"

    return mock_service


class TestCreateCampaign:
    @pytest.mark.asyncio
    async def test_missing_campaign_name(self, mock_context, mock_gads_client):
        """Omitting campaign_name must return an error."""
        result = await google_ads.execute_action(
            "create_campaign",
            {**BASE_INPUTS, "budget_amount_micros": 1000000},
            mock_context,
        )
        assert result.type != ResultType.ACTION
        assert "campaign_name" in str(result.result)

    @pytest.mark.asyncio
    async def test_missing_budget_amount_micros(self, mock_context, mock_gads_client):
        """Omitting budget_amount_micros must return an error."""
        result = await google_ads.execute_action(
            "create_campaign",
            {**BASE_INPUTS, "campaign_name": "My Campaign"},
            mock_context,
        )
        assert result.type != ResultType.ACTION
        assert "budget_amount_micros" in str(result.result)

    @pytest.mark.asyncio
    async def test_creates_campaign_successfully(self, mock_context, mock_gads_client):
        """Happy path: creates budget + campaign and returns resource names."""
        _setup_create_campaign_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "create_campaign",
            {
                **BASE_INPUTS,
                "campaign_name": "My Campaign",
                "budget_amount_micros": 1000000,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "campaign_resource_name" in result.result.data
        assert "budget_resource_name" in result.result.data
        assert "campaign_id" in result.result.data
        assert result.result.data["status"] == "PAUSED"

    @pytest.mark.asyncio
    async def test_campaign_id_extracted_from_resource_name(self, mock_context, mock_gads_client):
        """campaign_id must be the last path segment of the campaign resource name."""
        _setup_create_campaign_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "create_campaign",
            {
                **BASE_INPUTS,
                "campaign_name": "My Campaign",
                "budget_amount_micros": 1000000,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["campaign_id"] == "789"

    @pytest.mark.asyncio
    async def test_api_error_returns_action_error(self, mock_context, mock_gads_client):
        """An exception from mutate_campaigns must propagate as an ActionError."""
        _setup_create_campaign_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_campaigns.side_effect = Exception("mutate failed")

        result = await google_ads.execute_action(
            "create_campaign",
            {
                **BASE_INPUTS,
                "campaign_name": "My Campaign",
                "budget_amount_micros": 1000000,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "mutate failed" in result.result.message

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        """Missing refresh_token must return an ActionError."""
        result = await google_ads.execute_action(
            "create_campaign",
            {
                **BASE_INPUTS,
                "campaign_name": "My Campaign",
                "budget_amount_micros": 1000000,
            },
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_budget_api_error_returns_action_error(self, mock_context, mock_gads_client):
        """An exception from mutate_campaign_budgets must also surface as ActionError."""
        _setup_create_campaign_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_campaign_budgets.side_effect = Exception("budget failed")

        result = await google_ads.execute_action(
            "create_campaign",
            {
                **BASE_INPUTS,
                "campaign_name": "My Campaign",
                "budget_amount_micros": 1000000,
            },
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "budget failed" in result.result.message


# ===========================================================================
# 3. update_campaign
# ===========================================================================


def _setup_update_campaign_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    update_result = MagicMock()
    update_result.resource_name = "customers/123/campaigns/789"
    mock_service.mutate_campaigns.return_value.results = [update_result]
    mock_service.campaign_path.return_value = "customers/9876543210/campaigns/789"

    mock_gads_client.get_type.return_value = MagicMock()
    mock_gads_client.enums.CampaignStatusEnum.ENABLED = "ENABLED"
    mock_gads_client.enums.CampaignStatusEnum.PAUSED = "PAUSED"

    return mock_service


class TestUpdateCampaign:
    @pytest.mark.asyncio
    async def test_missing_campaign_id(self, mock_context, mock_gads_client):
        """Omitting campaign_id must return an error."""
        result = await google_ads.execute_action(
            "update_campaign",
            {**BASE_INPUTS, "status": "ENABLED"},
            mock_context,
        )
        assert result.type != ResultType.ACTION
        assert "campaign_id" in str(result.result)

    @pytest.mark.asyncio
    async def test_updates_campaign_successfully(self, mock_context, mock_gads_client):
        """Happy path: updating status returns ActionResult with resource name."""
        _setup_update_campaign_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "update_campaign",
            {**BASE_INPUTS, "campaign_id": "789", "status": "ENABLED"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert "campaign_resource_name" in result.result.data
        assert result.result.data["status"] == "ENABLED"

    @pytest.mark.asyncio
    async def test_update_campaign_name_only(self, mock_context, mock_gads_client):
        """Updating name only (no status) should return 'unchanged' in status field."""
        _setup_update_campaign_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "update_campaign",
            {**BASE_INPUTS, "campaign_id": "789", "name": "Renamed Campaign"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["status"] == "unchanged"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        """An exception from mutate_campaigns must return an ActionError."""
        _setup_update_campaign_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_campaigns.side_effect = Exception("update failed")

        result = await google_ads.execute_action(
            "update_campaign",
            {**BASE_INPUTS, "campaign_id": "789", "status": "PAUSED"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "update failed" in result.result.message

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        """Missing refresh_token must return an ActionError."""
        result = await google_ads.execute_action(
            "update_campaign",
            {**BASE_INPUTS, "campaign_id": "789", "status": "ENABLED"},
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR


# ===========================================================================
# 4. remove_campaign
# ===========================================================================


def _setup_remove_campaign_mocks(mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value

    remove_result = MagicMock()
    remove_result.resource_name = "customers/123/campaigns/789"
    mock_service.mutate_campaigns.return_value.results = [remove_result]
    mock_service.campaign_path.return_value = "customers/9876543210/campaigns/789"

    mock_gads_client.get_type.return_value = MagicMock()

    return mock_service


class TestRemoveCampaign:
    @pytest.mark.asyncio
    async def test_missing_campaign_id(self, mock_context, mock_gads_client):
        """Omitting campaign_id must return an error."""
        result = await google_ads.execute_action(
            "remove_campaign",
            {**BASE_INPUTS},
            mock_context,
        )
        assert result.type != ResultType.ACTION
        assert "campaign_id" in str(result.result)

    @pytest.mark.asyncio
    async def test_removes_campaign_successfully(self, mock_context, mock_gads_client):
        """Happy path: remove_campaign returns REMOVED status and resource name."""
        _setup_remove_campaign_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "remove_campaign",
            {**BASE_INPUTS, "campaign_id": "789"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["status"] == "REMOVED"
        assert "removed_campaign_resource_name" in result.result.data

    @pytest.mark.asyncio
    async def test_removed_resource_name_matches_api_response(self, mock_context, mock_gads_client):
        """The removed resource name in data should match what the API returned."""
        _setup_remove_campaign_mocks(mock_gads_client)

        result = await google_ads.execute_action(
            "remove_campaign",
            {**BASE_INPUTS, "campaign_id": "789"},
            mock_context,
        )
        assert result.type == ResultType.ACTION
        assert result.result.data["removed_campaign_resource_name"] == "customers/123/campaigns/789"

    @pytest.mark.asyncio
    async def test_api_error(self, mock_context, mock_gads_client):
        """An exception from mutate_campaigns must return an ActionError."""
        _setup_remove_campaign_mocks(mock_gads_client)
        mock_gads_client.get_service.return_value.mutate_campaigns.side_effect = Exception("remove failed")

        result = await google_ads.execute_action(
            "remove_campaign",
            {**BASE_INPUTS, "campaign_id": "789"},
            mock_context,
        )
        assert result.type == ResultType.ACTION_ERROR
        assert "remove failed" in result.result.message

    @pytest.mark.asyncio
    async def test_auth_error(self, mock_context_no_token):
        """Missing refresh_token must return an ActionError."""
        result = await google_ads.execute_action(
            "remove_campaign",
            {**BASE_INPUTS, "campaign_id": "789"},
            mock_context_no_token,
        )
        assert result.type == ResultType.ACTION_ERROR
