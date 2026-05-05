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
    ctx.auth = {"credentials": {"refresh_token": "test_refresh_token"}}  # nosec B105
    return ctx


@pytest.fixture
def mock_gads_client():
    with patch.object(_mod, "_get_google_ads_client") as mock_factory:
        client = MagicMock(name="GoogleAdsClient")
        mock_factory.return_value = client
        yield client


# ---------------------------------------------------------------------------
# retrieve_search_terms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_search_terms_missing_date_ranges(mock_context, mock_gads_client):
    result = await google_ads.execute_action("retrieve_search_terms", {**BASE_INPUTS}, mock_context)
    assert result.type != ResultType.ACTION
    assert "date_ranges" in str(result.result)


@pytest.mark.asyncio
async def test_retrieve_search_terms_auth_error(mock_context):
    mock_context.auth = {"credentials": {}}
    result = await google_ads.execute_action(
        "retrieve_search_terms",
        {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_retrieve_search_terms_returns_empty_results(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.search.return_value = []
    result = await google_ads.execute_action(
        "retrieve_search_terms",
        {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert "results" in result.result.data
    assert isinstance(result.result.data["results"], list)
    assert result.result.data["results"][0]["data"] == []


@pytest.mark.asyncio
async def test_retrieve_search_terms_returns_search_term_data(mock_context, mock_gads_client):
    row = MagicMock()
    mock_gads_client.get_service.return_value.search.return_value = [row]

    with patch("proto.Message.to_dict") as mock_to_dict:
        mock_to_dict.return_value = {
            "search_term_view": {"search_term": "test query", "status": "ADDED"},
            "segments": {"keyword": {"info": {"text": "test keyword", "match_type": "BROAD"}}},
            "ad_group": {"id": "1", "name": "Test Ad Group"},
            "campaign": {"id": "2", "name": "Test Campaign"},
            "metrics": {
                "impressions": "100",
                "clicks": "10",
                "ctr": 0.1,
                "average_cpc": 500000,
                "cost_micros": 5000000,
                "conversions": 1.0,
                "conversions_value": 10.0,
            },
        }

        result = await google_ads.execute_action(
            "retrieve_search_terms",
            {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context,
        )

    assert result.type == ResultType.ACTION
    data = result.result.data["results"][0]["data"]
    assert len(data) == 1
    entry = data[0]
    assert entry["search_term"] == "test query"
    assert entry["status"] == "ADDED"
    assert entry["matched_keyword"] == "test keyword"
    assert entry["match_type"] == "BROAD"
    assert entry["ad_group_id"] == "1"
    assert entry["ad_group_name"] == "Test Ad Group"
    assert entry["campaign_id"] == "2"
    assert entry["campaign_name"] == "Test Campaign"


@pytest.mark.asyncio
async def test_retrieve_search_terms_api_error(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.search.side_effect = Exception("Internal server error")
    result = await google_ads.execute_action(
        "retrieve_search_terms",
        {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
        mock_context,
    )
    assert result.type != ResultType.ACTION
    assert "Internal server error" in str(result.result)


@pytest.mark.asyncio
async def test_retrieve_search_terms_campaign_filter(mock_context, mock_gads_client):
    """campaign_ids filter is accepted and search is called."""
    mock_gads_client.get_service.return_value.search.return_value = []
    result = await google_ads.execute_action(
        "retrieve_search_terms",
        {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"], "campaign_ids": ["111", "222"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    mock_gads_client.get_service.return_value.search.assert_called_once()
    call_args = mock_gads_client.get_service.return_value.search.call_args
    assert "111" in call_args.kwargs.get("query", "") or "111" in str(call_args)


# ---------------------------------------------------------------------------
# get_active_ad_urls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_ad_urls_returns_active_ads(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.search.return_value = []
    result = await google_ads.execute_action("get_active_ad_urls", {**BASE_INPUTS}, mock_context)
    assert result.type == ResultType.ACTION
    assert "active_ads" in result.result.data
    assert "total_count" in result.result.data
    assert result.result.data["total_count"] == 0
    assert result.result.data["active_ads"] == []


@pytest.mark.asyncio
async def test_get_active_ad_urls_auth_error(mock_context):
    mock_context.auth = {"credentials": {}}
    result = await google_ads.execute_action("get_active_ad_urls", {**BASE_INPUTS}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_get_active_ad_urls_api_error(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.search.side_effect = Exception("Network error")
    result = await google_ads.execute_action("get_active_ad_urls", {**BASE_INPUTS}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Network error" in result.result.message


@pytest.mark.asyncio
async def test_get_active_ad_urls_url_filter_applied(mock_context, mock_gads_client):
    """Only ads whose final_urls contain the filter string should be returned."""
    row_matching = MagicMock()
    row_non_matching = MagicMock()
    mock_gads_client.get_service.return_value.search.return_value = [row_matching, row_non_matching]

    matching_data = {
        "campaign": {"id": "1", "name": "Camp A", "status": "ENABLED"},
        "ad_group": {"id": "10", "name": "AG A", "status": "ENABLED"},
        "ad_group_ad": {
            "status": "ENABLED",
            "ad": {
                "id": "100",
                "name": "Ad A",
                "type": "RESPONSIVE_SEARCH_AD",
                "final_urls": ["https://example.com/landing"],
                "final_mobile_urls": [],
                "tracking_url_template": "",
            },
        },
    }
    non_matching_data = {
        "campaign": {"id": "2", "name": "Camp B", "status": "ENABLED"},
        "ad_group": {"id": "20", "name": "AG B", "status": "ENABLED"},
        "ad_group_ad": {
            "status": "ENABLED",
            "ad": {
                "id": "200",
                "name": "Ad B",
                "type": "RESPONSIVE_SEARCH_AD",
                "final_urls": ["https://other.com/page"],
                "final_mobile_urls": [],
                "tracking_url_template": "",
            },
        },
    }

    with patch("proto.Message.to_dict") as mock_to_dict:
        mock_to_dict.side_effect = [matching_data, non_matching_data]

        result = await google_ads.execute_action(
            "get_active_ad_urls", {**BASE_INPUTS, "url_filter": "example.com"}, mock_context
        )

    assert result.type == ResultType.ACTION
    assert result.result.data["total_count"] == 1
    assert result.result.data["active_ads"][0]["ad_id"] == "100"
    assert "https://example.com/landing" in result.result.data["active_ads"][0]["final_urls"]


@pytest.mark.asyncio
async def test_get_active_ad_urls_no_filter_returns_all(mock_context, mock_gads_client):
    """Without url_filter all ads are returned."""
    row1 = MagicMock()
    row2 = MagicMock()
    mock_gads_client.get_service.return_value.search.return_value = [row1, row2]

    ad_data_template = {
        "campaign": {"id": "1", "name": "Camp", "status": "ENABLED"},
        "ad_group": {"id": "10", "name": "AG", "status": "ENABLED"},
        "ad_group_ad": {
            "status": "ENABLED",
            "ad": {
                "id": "100",
                "name": "Ad",
                "type": "RESPONSIVE_SEARCH_AD",
                "final_urls": ["https://any.com/page"],
                "final_mobile_urls": [],
                "tracking_url_template": "",
            },
        },
    }

    with patch("proto.Message.to_dict", return_value=ad_data_template):
        result = await google_ads.execute_action("get_active_ad_urls", {**BASE_INPUTS}, mock_context)

    assert result.type == ResultType.ACTION
    assert result.result.data["total_count"] == 2
