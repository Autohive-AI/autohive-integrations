"""
Unit tests for the Google Ads integration.

Uses a real GoogleAdsClient so request messages are the library's real proto types,
with only the service calls mocked.

Run with:
    pytest google-ads/tests/test_google_ads_unit.py -m unit
"""

import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from autohive_integrations_sdk import ResultType
from google.ads.googleads.client import GoogleAdsClient
from google.auth.credentials import AnonymousCredentials
from google.auth.exceptions import RefreshError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("ADWORDS_DEVELOPER_TOKEN", "test-developer-token")
os.environ.setdefault("ADWORDS_CLIENT_ID", "test-client-id")
os.environ.setdefault("ADWORDS_CLIENT_SECRET", "test-client-secret")

import google_ads as google_ads_module  # noqa: E402
from google_ads import _to_campaign_date_time, google_ads  # noqa: E402

pytestmark = pytest.mark.unit

AUTH = {"auth_type": "PlatformOauth2", "credentials": {"refresh_token": "test-refresh-token"}}  # nosec B105
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
    ga_service = MagicMock(name="GoogleAdsService")
    ga_service.search.return_value = [_customer_row("Pacific/Auckland")]
    services = {
        "CampaignBudgetService": budget_service,
        "CampaignService": campaign_service,
        "GoogleAdsService": ga_service,
    }
    client.get_service = lambda name, **kwargs: services[name]

    with patch.object(google_ads_module, "_get_google_ads_client", return_value=client):
        yield SimpleNamespace(budget=budget_service, campaign=campaign_service, ga=ga_service)


def _customer_row(time_zone):
    row = MagicMock(name="GoogleAdsRow")
    row.customer.time_zone = time_zone
    return row


def _freeze_utc_now(value):
    """Patches the module's datetime so now() returns the given UTC moment."""

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            frozen = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
            return frozen.astimezone(tz) if tz else frozen.replace(tzinfo=None)

    return patch.object(google_ads_module, "datetime", FrozenDatetime)


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
        ("2026-12-1 8:05:00", "00:00:00", "2026-12-01 08:05:00"),
        ("2026-12-1", "00:00:00", "2026-12-01 00:00:00"),
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
    inputs = {**CAMPAIGN_INPUTS, "start_date": "20261201", "end_date": "2026-12-31"}

    result = await google_ads.execute_action("create_campaign", inputs, make_context(auth=AUTH))

    assert result.type == ResultType.ACTION
    assert result.result.data["campaign_id"] == "3"
    campaign = _sent_campaign(ads_client.campaign)
    assert campaign.start_date_time == "2026-12-01 00:00:00"
    assert campaign.end_date_time == "2026-12-31 23:59:59"
    ads_client.ga.search.assert_not_called()


@pytest.mark.parametrize(
    "utc_now, time_zone, expected_start, expected_end",
    [
        # 21:00 UTC is already 10:00 the next day in Auckland.
        ("2026-11-09T21:00:00", "Pacific/Auckland", "2026-11-11 00:00:00", "2027-11-11 23:59:59"),
        # 05:00 UTC is still 21:00 the previous day in Los Angeles.
        ("2026-11-10T05:00:00", "America/Los_Angeles", "2026-11-10 00:00:00", "2027-11-10 23:59:59"),
    ],
)
async def test_create_campaign_defaults_use_account_time_zone(
    make_context, ads_client, utc_now, time_zone, expected_start, expected_end
):
    ads_client.ga.search.return_value = [_customer_row(time_zone)]

    with _freeze_utc_now(utc_now):
        result = await google_ads.execute_action("create_campaign", CAMPAIGN_INPUTS, make_context(auth=AUTH))

    assert result.type == ResultType.ACTION
    campaign = _sent_campaign(ads_client.campaign)
    assert campaign.start_date_time == expected_start
    assert campaign.end_date_time == expected_end


async def test_create_campaign_default_end_follows_start_date(make_context, ads_client):
    inputs = {**CAMPAIGN_INPUTS, "start_date": "2028-03-01"}

    result = await google_ads.execute_action("create_campaign", inputs, make_context(auth=AUTH))

    assert result.type == ResultType.ACTION
    campaign = _sent_campaign(ads_client.campaign)
    assert campaign.start_date_time == "2028-03-01 00:00:00"
    assert campaign.end_date_time == "2029-03-01 23:59:59"


async def test_create_campaign_normalises_unpadded_dates(make_context, ads_client):
    inputs = {**CAMPAIGN_INPUTS, "start_date": "2026-12-1 00:00:00", "end_date": "2026-12-02"}

    result = await google_ads.execute_action("create_campaign", inputs, make_context(auth=AUTH))

    assert result.type == ResultType.ACTION
    campaign = _sent_campaign(ads_client.campaign)
    assert campaign.start_date_time == "2026-12-01 00:00:00"
    assert campaign.end_date_time == "2026-12-02 23:59:59"


@pytest.mark.parametrize(
    "date_inputs, error",
    [
        ({"start_date": "01/12/2026"}, "Invalid date"),
        ({"start_date": "2026-12-31", "end_date": "2026-12-01"}, "must be before end_date"),
        ({"start_date": "2026-12-01 23:59:59", "end_date": "2026-11-30"}, "must be before end_date"),
    ],
)
async def test_create_campaign_bad_dates_create_no_budget(make_context, ads_client, date_inputs, error):
    inputs = {**CAMPAIGN_INPUTS, **date_inputs}

    result = await google_ads.execute_action("create_campaign", inputs, make_context(auth=AUTH))

    assert result.type == ResultType.ACTION_ERROR
    assert error in result.result.message

    ads_client.budget.mutate_campaign_budgets.assert_not_called()
    ads_client.campaign.mutate_campaigns.assert_not_called()


@pytest.mark.parametrize("action", ["retrieve_campaign_metrics", "retrieve_keyword_metrics"])
async def test_failed_report_returns_safe_action_error(make_context, ads_client, action):
    ads_client.ga.search.side_effect = RefreshError("sensitive provider response")
    inputs = {"login_customer_id": "1111111111", "customer_id": "2222222222", "date_ranges": ["LAST_7_DAYS"]}

    if action == "retrieve_keyword_metrics":
        inputs.update(campaign_ids=[], ad_group_ids=[])

    result = await google_ads.execute_action(action, inputs, make_context(auth=AUTH))

    assert result.type == ResultType.ACTION_ERROR
    assert "Reconnect your Google Ads account" in result.result.message
    assert "sensitive provider response" not in result.result.message
