"""
Live integration tests for Google Ads.

These tests call the real Google Ads API and require safe read-only fixture
IDs. They are skipped by the default pytest marker filter.
"""

import importlib
import os
import sys

import pytest
from autohive_integrations_sdk import ExecutionContext

REQUIRED_ENV = [
    "ADWORDS_DEVELOPER_TOKEN",
    "ADWORDS_CLIENT_ID",
    "ADWORDS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
    "GOOGLE_ADS_CUSTOMER_ID",
    "GOOGLE_ADS_TEST_CAMPAIGN_IDS",
    "GOOGLE_ADS_TEST_AD_GROUP_IDS",
]

missing_env = [name for name in REQUIRED_ENV if not os.environ.get(name)]
if missing_env:
    pytest.skip(f"Missing Google Ads integration test env vars: {', '.join(missing_env)}", allow_module_level=True)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

google_ads_mod = importlib.import_module("google_ads")


pytestmark = pytest.mark.integration


def _csv_env(name: str) -> list[str]:
    return [value.strip() for value in os.environ[name].split(",") if value.strip()]


@pytest.fixture
def live_context():
    return ExecutionContext(
        auth={
            "credentials": {
                "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
            }
        }
    )


async def test_retrieve_keyword_metrics_returns_identifier_fields(live_context):
    result = await google_ads_mod.google_ads.execute_action(
        "retrieve_keyword_metrics",
        {
            "login_customer_id": os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"],
            "customer_id": os.environ["GOOGLE_ADS_CUSTOMER_ID"],
            "campaign_ids": _csv_env("GOOGLE_ADS_TEST_CAMPAIGN_IDS"),
            "ad_group_ids": _csv_env("GOOGLE_ADS_TEST_AD_GROUP_IDS"),
            "date_ranges": [os.environ.get("GOOGLE_ADS_TEST_DATE_RANGE", "last 7 days")],
        },
        live_context,
    )

    ranges = result.result.data["results"]
    rows = [row for date_range in ranges for row in date_range.get("data", [])]
    if not rows:
        pytest.skip("No keyword metric rows returned for the configured Google Ads fixture IDs and date range")

    row = rows[0]
    for field in ("Campaign ID", "Campaign", "Ad Group ID", "Ad Group", "Keyword ID", "Keyword"):
        assert row[field] not in ("", "N/A")
    assert row["Match Type"] not in ("", "N/A", "UNSPECIFIED")
    assert row["Status"] not in ("", "N/A", "UNSPECIFIED")
