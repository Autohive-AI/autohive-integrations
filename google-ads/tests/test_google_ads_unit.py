"""
Unit tests for the Google Ads integration.

Uses a real GoogleAdsClient so request messages are the library's real proto types,
with only the service calls mocked.

Run with:
    pytest google-ads/tests/test_google_ads_unit.py -m unit
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from autohive_integrations_sdk import ResultType
from google.ads.googleads.client import GoogleAdsClient
from google.auth.credentials import AnonymousCredentials

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("ADWORDS_DEVELOPER_TOKEN", "test-developer-token")
os.environ.setdefault("ADWORDS_CLIENT_ID", "test-client-id")
os.environ.setdefault("ADWORDS_CLIENT_SECRET", "test-client-secret")

import google_ads as google_ads_module  # noqa: E402
from google_ads import _to_campaign_date_time, google_ads  # noqa: E402

pytestmark = pytest.mark.unit

AUTH = {"auth_type": "PlatformOAuth2", "credentials": {"refresh_token": "test-refresh-token"}}  # nosec B105
CAMPAIGN_INPUTS = {
    "login_customer_id": "1111111111",
    "customer_id": "2222222222",
    "campaign_name": "Test Campaign",
    "budget_amount_micros": 10_000_000,
}


@pytest.fixture
def ads_client():
    """Real offline client with mocked services; captures the operations sent to each mutate call."""
    client = GoogleAdsClient(
        credentials=AnonymousCredentials(),
        developer_token="test-developer-token",  # nosec B106
        use_proto_plus=True,
    )

    budget_service = MagicMock(name="CampaignBudgetService")
    budget_service.mutate_campaign_budgets.return_value.results = [
        MagicMock(resource_name="customers/2222222222/campaignBudgets/1")
    ]
    campaign_service = MagicMock(name="CampaignService")
    campaign_service.mutate_campaigns.return_value.results = [
        MagicMock(resource_name="customers/2222222222/campaigns/3")
    ]
    services = {"CampaignBudgetService": budget_service, "CampaignService": campaign_service}
    client.get_service = lambda name, **kwargs: services[name]

    with patch.object(google_ads_module, "_get_google_ads_client", return_value=client):
        yield client, budget_service, campaign_service


def _sent_campaign(campaign_service):
    operations = campaign_service.mutate_campaigns.call_args.kwargs["operations"]
    return operations[0].create


# ---- _to_campaign_date_time ----


@pytest.mark.parametrize(
    "value, time_of_day, expected",
    [
        ("20261110", "00:00:00", "2026-11-10 00:00:00"),
        ("2026-11-10", "23:59:59", "2026-11-10 23:59:59"),
        (" 2026-11-10 ", "00:00:00", "2026-11-10 00:00:00"),
        ("2026-11-10 08:30:00", "00:00:00", "2026-11-10 08:30:00"),
        (20261110, "00:00:00", "2026-11-10 00:00:00"),
    ],
)
def test_to_campaign_date_time_converts(value, time_of_day, expected):
    assert _to_campaign_date_time(value, time_of_day) == expected


@pytest.mark.parametrize("value", ["10/11/2026", "2026-13-01", "", "tomorrow"])
def test_to_campaign_date_time_rejects_invalid(value):
    with pytest.raises(ValueError, match="Invalid date"):
        _to_campaign_date_time(value, "00:00:00")


# ---- create_campaign ----


async def test_create_campaign_sets_date_time_fields(make_context, ads_client):
    _, _, campaign_service = ads_client
    inputs = {**CAMPAIGN_INPUTS, "start_date": "20261201", "end_date": "2026-12-31"}

    result = await google_ads.execute_action("create_campaign", inputs, make_context(auth=AUTH))

    assert result.type == ResultType.ACTION
    assert result.result.data["campaign_id"] == "3"
    campaign = _sent_campaign(campaign_service)
    assert campaign.start_date_time == "2026-12-01 00:00:00"
    assert campaign.end_date_time == "2026-12-31 23:59:59"


async def test_create_campaign_defaults_dates(make_context, ads_client):
    _, _, campaign_service = ads_client

    result = await google_ads.execute_action("create_campaign", CAMPAIGN_INPUTS, make_context(auth=AUTH))

    assert result.type == ResultType.ACTION
    campaign = _sent_campaign(campaign_service)
    assert campaign.start_date_time.endswith(" 00:00:00")
    assert campaign.end_date_time.endswith(" 23:59:59")
    assert campaign.start_date_time < campaign.end_date_time


async def test_create_campaign_invalid_date_creates_no_budget(make_context, ads_client):
    _, budget_service, campaign_service = ads_client
    inputs = {**CAMPAIGN_INPUTS, "start_date": "01/12/2026"}

    with pytest.raises(ValueError, match="Invalid date"):
        await google_ads.execute_action("create_campaign", inputs, make_context(auth=AUTH))

    budget_service.mutate_campaign_budgets.assert_not_called()
    campaign_service.mutate_campaigns.assert_not_called()
