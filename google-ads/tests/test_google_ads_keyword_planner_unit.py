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
def mock_gads_client():
    with patch.object(_mod, "_get_google_ads_client") as mock_factory:
        client = MagicMock(name="GoogleAdsClient")
        mock_factory.return_value = client
        yield client


# ---------------------------------------------------------------------------
# generate_keyword_ideas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_keyword_ideas_missing_seed_and_url(mock_context, mock_gads_client):
    result = await google_ads.execute_action("generate_keyword_ideas", {**BASE_INPUTS}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_generate_keyword_ideas_auth_error(mock_context):
    mock_context.auth = {"credentials": {}}
    result = await google_ads.execute_action(
        "generate_keyword_ideas",
        {**BASE_INPUTS, "seed_keywords": ["shoes"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_generate_keyword_ideas_api_error(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.generate_keyword_ideas.side_effect = Exception("Service unavailable")
    mock_gads_client.get_type.return_value = MagicMock()

    result = await google_ads.execute_action(
        "generate_keyword_ideas",
        {**BASE_INPUTS, "seed_keywords": ["shoes"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Service unavailable" in result.result.message


@pytest.mark.asyncio
async def test_generate_keyword_ideas_returns_keyword_ideas(mock_context, mock_gads_client):
    mock_idea = MagicMock()
    mock_idea.text = "digital marketing"
    mock_idea.keyword_idea_metrics.avg_monthly_searches = 1000
    mock_idea.keyword_idea_metrics.competition.name = "HIGH"
    mock_idea.keyword_idea_metrics.competition_index = 75
    mock_idea.keyword_idea_metrics.low_top_of_page_bid_micros = 500000
    mock_idea.keyword_idea_metrics.high_top_of_page_bid_micros = 2000000

    mock_gads_client.get_service.return_value.generate_keyword_ideas.return_value = [mock_idea]
    mock_gads_client.get_type.return_value = MagicMock()

    result = await google_ads.execute_action(
        "generate_keyword_ideas",
        {**BASE_INPUTS, "seed_keywords": ["marketing"]},
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert "keyword_ideas" in result.result.data
    assert len(result.result.data["keyword_ideas"]) == 1
    idea = result.result.data["keyword_ideas"][0]
    assert idea["keyword"] == "digital marketing"
    assert idea["avg_monthly_searches"] == 1000
    assert idea["competition"] == "HIGH"
    assert result.result.data["total_results"] == 1


@pytest.mark.asyncio
async def test_generate_keyword_ideas_seed_keywords_only(mock_context, mock_gads_client):
    """When only seed_keywords provided, keyword_seed branch is used."""
    mock_gads_client.get_service.return_value.generate_keyword_ideas.return_value = []
    request_mock = MagicMock()
    mock_gads_client.get_type.return_value = request_mock

    result = await google_ads.execute_action(
        "generate_keyword_ideas",
        {**BASE_INPUTS, "seed_keywords": ["running shoes"]},
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert result.result.data["keyword_ideas"] == []
    request_mock.keyword_seed.keywords.extend.assert_called_once_with(["running shoes"])


@pytest.mark.asyncio
async def test_generate_keyword_ideas_page_url_only(mock_context, mock_gads_client):
    """When only page_url provided, url_seed branch is used."""
    mock_gads_client.get_service.return_value.generate_keyword_ideas.return_value = []
    request_mock = MagicMock()
    mock_gads_client.get_type.return_value = request_mock

    result = await google_ads.execute_action(
        "generate_keyword_ideas",
        {**BASE_INPUTS, "page_url": "https://example.com"},
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert request_mock.url_seed.url == "https://example.com"


@pytest.mark.asyncio
async def test_generate_keyword_ideas_both_seed_and_url(mock_context, mock_gads_client):
    """When both seed_keywords and page_url provided, keyword_and_url_seed branch is used."""
    mock_gads_client.get_service.return_value.generate_keyword_ideas.return_value = []
    request_mock = MagicMock()
    mock_gads_client.get_type.return_value = request_mock

    result = await google_ads.execute_action(
        "generate_keyword_ideas",
        {**BASE_INPUTS, "seed_keywords": ["shoes"], "page_url": "https://example.com"},
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert request_mock.keyword_and_url_seed.url == "https://example.com"
    request_mock.keyword_and_url_seed.keywords.extend.assert_called_once_with(["shoes"])


# ---------------------------------------------------------------------------
# generate_keyword_historical_metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_keyword_historical_metrics_missing_keywords(mock_context, mock_gads_client):
    result = await google_ads.execute_action("generate_keyword_historical_metrics", {**BASE_INPUTS}, mock_context)
    assert result.type != ResultType.ACTION
    assert "keywords" in str(result.result)


@pytest.mark.asyncio
async def test_generate_keyword_historical_metrics_auth_error(mock_context):
    mock_context.auth = {"credentials": {}}
    result = await google_ads.execute_action(
        "generate_keyword_historical_metrics",
        {**BASE_INPUTS, "keywords": ["shoes"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_generate_keyword_historical_metrics_api_error(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.generate_keyword_historical_metrics.side_effect = Exception(
        "Quota exceeded"
    )
    mock_gads_client.get_type.return_value = MagicMock()

    result = await google_ads.execute_action(
        "generate_keyword_historical_metrics",
        {**BASE_INPUTS, "keywords": ["shoes"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Quota exceeded" in result.result.message


@pytest.mark.asyncio
async def test_generate_keyword_historical_metrics_returns_data(mock_context, mock_gads_client):
    mock_kw_result = MagicMock()
    mock_kw_result.text = "running shoes"
    metrics = mock_kw_result.keyword_metrics
    metrics.avg_monthly_searches = 5000
    metrics.competition.name = "MEDIUM"
    metrics.competition_index = 50
    metrics.low_top_of_page_bid_micros = 300000
    metrics.high_top_of_page_bid_micros = 1500000
    metrics.monthly_search_volumes = []

    response_mock = MagicMock()
    response_mock.results = [mock_kw_result]
    mock_gads_client.get_service.return_value.generate_keyword_historical_metrics.return_value = response_mock
    mock_gads_client.get_type.return_value = MagicMock()

    result = await google_ads.execute_action(
        "generate_keyword_historical_metrics",
        {**BASE_INPUTS, "keywords": ["running shoes"]},
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert "keyword_metrics" in result.result.data
    assert len(result.result.data["keyword_metrics"]) == 1
    km = result.result.data["keyword_metrics"][0]
    assert km["keyword"] == "running shoes"
    assert km["avg_monthly_searches"] == 5000
    assert km["competition"] == "MEDIUM"


# ---------------------------------------------------------------------------
# generate_keyword_forecast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_keyword_forecast_missing_keywords(mock_context, mock_gads_client):
    result = await google_ads.execute_action("generate_keyword_forecast", {**BASE_INPUTS}, mock_context)
    assert result.type != ResultType.ACTION
    assert "keywords" in str(result.result)


@pytest.mark.asyncio
async def test_generate_keyword_forecast_auth_error(mock_context):
    mock_context.auth = {"credentials": {}}
    result = await google_ads.execute_action(
        "generate_keyword_forecast",
        {**BASE_INPUTS, "keywords": [{"text": "shoes", "match_type": "BROAD"}]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_generate_keyword_forecast_api_error(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.generate_keyword_forecast_metrics.side_effect = Exception(
        "Forecast unavailable"
    )
    mock_gads_client.get_type.return_value = MagicMock()

    result = await google_ads.execute_action(
        "generate_keyword_forecast",
        {**BASE_INPUTS, "keywords": [{"text": "shoes", "match_type": "BROAD"}]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Forecast unavailable" in result.result.message


@pytest.mark.asyncio
async def test_generate_keyword_forecast_returns_forecast(mock_context, mock_gads_client):
    forecast_metrics = MagicMock()
    forecast_metrics.impressions = 10000
    forecast_metrics.clicks = 500
    forecast_metrics.cost_micros = 2500000
    forecast_metrics.average_cpc_micros = 5000

    response_mock = MagicMock()
    response_mock.campaign_forecast_metrics = forecast_metrics
    mock_gads_client.get_service.return_value.generate_keyword_forecast_metrics.return_value = response_mock
    mock_gads_client.get_type.return_value = MagicMock()

    result = await google_ads.execute_action(
        "generate_keyword_forecast",
        {
            **BASE_INPUTS,
            "keywords": [{"text": "digital marketing", "match_type": "BROAD"}],
            "forecast_days": 30,
        },
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert "forecast_period" in result.result.data
    assert "campaign_metrics" in result.result.data
    assert result.result.data["keywords_count"] == 1
    assert result.result.data["campaign_metrics"]["impressions"] == 10000
    assert result.result.data["campaign_metrics"]["clicks"] == 500
    assert result.result.data["forecast_period"]["days"] == 30
