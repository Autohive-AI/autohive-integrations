"""Read-only live Google Ads tests. See the Google Ads section in .env.example."""

from importlib import import_module
from pathlib import Path

import pytest
from autohive_integrations_sdk import ExecutionContext, ResultType

pytestmark = pytest.mark.integration


@pytest.fixture
def live_ads(env_credentials, monkeypatch):
    settings = {name: f"ADWORDS_{name}" for name in ("DEVELOPER_TOKEN", "CLIENT_ID", "CLIENT_SECRET")}
    names = [*settings.values(), "GOOGLE_ADS_REFRESH_TOKEN"]
    credentials = {name: env_credentials(name) for name in names}
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        pytest.skip(f"Missing Google Ads credentials: {', '.join(missing)}")

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    module = import_module("google_ads")
    # Unit tests may have imported the module with dummy settings.
    for attribute, name in settings.items():
        monkeypatch.setattr(module, attribute, credentials[name])

    context = ExecutionContext(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"refresh_token": credentials["GOOGLE_ADS_REFRESH_TOKEN"]},
        }
    )
    return module.google_ads, context


@pytest.fixture
def account_inputs(env_credentials):
    customer_id = env_credentials("GOOGLE_ADS_TEST_CUSTOMER_ID")
    manager_id = env_credentials("GOOGLE_ADS_TEST_LOGIN_CUSTOMER_ID")
    if not customer_id or not manager_id:
        pytest.skip("Set GOOGLE_ADS_TEST_CUSTOMER_ID and GOOGLE_ADS_TEST_LOGIN_CUSTOMER_ID")
    return {"customer_id": customer_id, "login_customer_id": manager_id}


async def action_data(live_ads, action, inputs):
    integration, context = live_ads
    result = await integration.execute_action(action, inputs, context)
    assert result.type == ResultType.ACTION, result.result
    return result.result.data


async def test_get_accessible_accounts(live_ads):
    data = await action_data(live_ads, "get_accessible_accounts", {})
    assert data["accounts"], "The authorized account should have access to at least one Google Ads customer"
    for account in data["accounts"]:
        assert account["resource_name"] == f"customers/{account['customer_id']}"


@pytest.mark.parametrize(
    "action",
    [
        "retrieve_campaign_metrics",
        "retrieve_keyword_metrics",
        "retrieve_ad_group_metrics",
        "retrieve_ad_metrics",
        "retrieve_search_terms",
    ],
)
async def test_read_reporting_metrics(live_ads, account_inputs, action):
    inputs = {**account_inputs, "date_ranges": ["LAST_7_DAYS"]}
    if action == "retrieve_keyword_metrics":
        inputs.update(ad_group_ids=[], campaign_ids=[])

    data = await action_data(live_ads, action, inputs)

    assert len(data["results"]) == 1
    report = data["results"][0]
    assert report["date_range"]
    assert isinstance(report["data"], list)
    assert not report.get("error")


async def test_get_active_ad_urls(live_ads, account_inputs):
    data = await action_data(live_ads, "get_active_ad_urls", account_inputs)
    assert isinstance(data["active_ads"], list)
    assert data["total_count"] == len(data["active_ads"])


async def test_generate_keyword_ideas(live_ads, account_inputs):
    data = await action_data(live_ads, "generate_keyword_ideas", {**account_inputs, "seed_keywords": ["running shoes"]})
    assert data["keyword_ideas"]
    assert data["total_results"] == len(data["keyword_ideas"])


async def test_generate_keyword_historical_metrics(live_ads, account_inputs):
    data = await action_data(
        live_ads, "generate_keyword_historical_metrics", {**account_inputs, "keywords": ["running shoes"]}
    )
    assert data["keyword_metrics"]


async def test_generate_keyword_forecast(live_ads, account_inputs):
    data = await action_data(
        live_ads,
        "generate_keyword_forecast",
        {**account_inputs, "keywords": [{"text": "running shoes"}], "forecast_days": 7},
    )
    assert data["keywords_count"] == 1
    assert data["forecast_period"]["days"] == 7
    assert data["campaign_metrics"]["clicks"] >= 0
