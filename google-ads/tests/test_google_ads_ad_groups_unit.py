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
def mock_gads_client():
    with patch.object(_mod, "_get_google_ads_client") as mock_factory:
        client = MagicMock(name="GoogleAdsClient")
        mock_factory.return_value = client
        yield client


# ---------------------------------------------------------------------------
# retrieve_ad_group_metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_ad_group_metrics_missing_date_ranges(
    mock_context, mock_gads_client
):
    result = await google_ads.execute_action(
        "retrieve_ad_group_metrics", {**BASE_INPUTS}, mock_context
    )
    assert result.type != ResultType.ACTION
    assert "date_ranges" in str(result.result)


@pytest.mark.asyncio
async def test_retrieve_ad_group_metrics_auth_error(mock_context):
    mock_context.auth = {"credentials": {}}
    result = await google_ads.execute_action(
        "retrieve_ad_group_metrics",
        {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_retrieve_ad_group_metrics_empty_results(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.search.return_value = []
    result = await google_ads.execute_action(
        "retrieve_ad_group_metrics",
        {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert "results" in result.result.data
    assert isinstance(result.result.data["results"], list)


@pytest.mark.asyncio
async def test_retrieve_ad_group_metrics_returns_data(mock_context, mock_gads_client):
    row = MagicMock()
    mock_gads_client.get_service.return_value.search.return_value = [row]

    row_data = {
        "ad_group": {
            "id": "111",
            "name": "Test AG",
            "status": "ENABLED",
            "type": "SEARCH_STANDARD",
            "cpc_bid_micros": 500000,
        },
        "campaign": {"id": "222", "name": "Test Campaign", "status": "ENABLED"},
        "metrics": {
            "impressions": 100,
            "clicks": 10,
            "ctr": 0.1,
            "average_cpc": 500000,
            "cost_micros": 5000000,
            "conversions": 1.0,
            "conversions_value": 10.0,
            "cost_per_conversion": 5000000,
            "all_conversions": 1.0,
            "interaction_rate": 0.1,
        },
    }

    with patch("proto.Message.to_dict", return_value=row_data):
        result = await google_ads.execute_action(
            "retrieve_ad_group_metrics",
            {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
            mock_context,
        )

    assert result.type == ResultType.ACTION
    assert len(result.result.data["results"]) == 1
    assert result.result.data["results"][0]["data"][0]["ad_group_id"] == "111"


@pytest.mark.asyncio
async def test_retrieve_ad_group_metrics_api_error(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.search.side_effect = Exception(
        "API failure"
    )
    result = await google_ads.execute_action(
        "retrieve_ad_group_metrics",
        {**BASE_INPUTS, "date_ranges": ["2025-05-14_2025-05-20"]},
        mock_context,
    )
    assert result.type != ResultType.ACTION
    assert "API failure" in str(result.result)


# ---------------------------------------------------------------------------
# create_ad_group
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_ad_group_success(mock_context, mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value
    result_mock = MagicMock()
    result_mock.resource_name = "customers/123/adGroups/456"
    mock_service.mutate_ad_groups.return_value.results = [result_mock]
    mock_gads_client.get_type.return_value = MagicMock()
    mock_gads_client.enums.AdGroupTypeEnum.SEARCH_STANDARD = "SEARCH_STANDARD"
    mock_gads_client.enums.AdGroupStatusEnum.PAUSED = "PAUSED"

    result = await google_ads.execute_action(
        "create_ad_group",
        {**BASE_INPUTS, "campaign_id": "111", "ad_group_name": "My Ad Group"},
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert result.result.data["ad_group_id"] == "456"


@pytest.mark.asyncio
async def test_create_ad_group_missing_campaign_id(mock_context, mock_gads_client):
    result = await google_ads.execute_action(
        "create_ad_group",
        {**BASE_INPUTS, "ad_group_name": "My Ad Group"},
        mock_context,
    )
    assert result.type != ResultType.ACTION
    assert "campaign_id" in str(result.result)


@pytest.mark.asyncio
async def test_create_ad_group_missing_ad_group_name(mock_context, mock_gads_client):
    result = await google_ads.execute_action(
        "create_ad_group",
        {**BASE_INPUTS, "campaign_id": "111"},
        mock_context,
    )
    assert result.type != ResultType.ACTION


@pytest.mark.asyncio
async def test_create_ad_group_auth_error(mock_context):
    mock_context.auth = {"credentials": {}}
    result = await google_ads.execute_action(
        "create_ad_group",
        {**BASE_INPUTS, "campaign_id": "111", "ad_group_name": "My Ad Group"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_create_ad_group_api_error(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.mutate_ad_groups.side_effect = Exception(
        "Quota exceeded"
    )
    mock_gads_client.get_type.return_value = MagicMock()

    result = await google_ads.execute_action(
        "create_ad_group",
        {**BASE_INPUTS, "campaign_id": "111", "ad_group_name": "My Ad Group"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Quota exceeded" in result.result.message


# ---------------------------------------------------------------------------
# update_ad_group
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_ad_group_success(mock_context, mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value
    result_mock = MagicMock()
    result_mock.resource_name = "customers/123/adGroups/789"
    mock_service.mutate_ad_groups.return_value.results = [result_mock]
    mock_gads_client.get_type.return_value = MagicMock()
    mock_gads_client.enums.AdGroupStatusEnum.PAUSED = "PAUSED"

    result = await google_ads.execute_action(
        "update_ad_group",
        {**BASE_INPUTS, "ad_group_id": "789", "status": "PAUSED"},
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert result.result.data["ad_group_id"] == "789"


@pytest.mark.asyncio
async def test_update_ad_group_missing_ad_group_id(mock_context, mock_gads_client):
    result = await google_ads.execute_action(
        "update_ad_group", {**BASE_INPUTS}, mock_context
    )
    assert result.type != ResultType.ACTION
    assert "ad_group_id" in str(result.result)


@pytest.mark.asyncio
async def test_update_ad_group_auth_error(mock_context):
    mock_context.auth = {"credentials": {}}
    result = await google_ads.execute_action(
        "update_ad_group",
        {**BASE_INPUTS, "ad_group_id": "789", "status": "PAUSED"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_update_ad_group_api_error(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.mutate_ad_groups.side_effect = Exception(
        "Permission denied"
    )
    mock_gads_client.get_type.return_value = MagicMock()

    result = await google_ads.execute_action(
        "update_ad_group",
        {**BASE_INPUTS, "ad_group_id": "789", "status": "PAUSED"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Permission denied" in result.result.message


@pytest.mark.asyncio
async def test_update_ad_group_with_field_mask(mock_context, mock_gads_client):
    """Ensure field mask is applied when updating multiple fields."""
    mock_service = mock_gads_client.get_service.return_value
    result_mock = MagicMock()
    result_mock.resource_name = "customers/123/adGroups/789"
    mock_service.mutate_ad_groups.return_value.results = [result_mock]
    ad_group_op = MagicMock()
    mock_gads_client.get_type.return_value = ad_group_op
    mock_gads_client.enums.AdGroupStatusEnum.ENABLED = "ENABLED"

    result = await google_ads.execute_action(
        "update_ad_group",
        {
            **BASE_INPUTS,
            "ad_group_id": "789",
            "status": "ENABLED",
            "name": "Renamed Group",
            "cpc_bid_micros": 2000000,
        },
        mock_context,
    )

    assert result.type == ResultType.ACTION
    mock_gads_client.copy_from.assert_called()


# ---------------------------------------------------------------------------
# remove_ad_group
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_ad_group_success(mock_context, mock_gads_client):
    mock_service = mock_gads_client.get_service.return_value
    result_mock = MagicMock()
    result_mock.resource_name = "customers/123/adGroups/789"
    mock_service.mutate_ad_groups.return_value.results = [result_mock]
    mock_gads_client.get_type.return_value = MagicMock()

    result = await google_ads.execute_action(
        "remove_ad_group",
        {**BASE_INPUTS, "ad_group_id": "789"},
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert result.result.data["status"] == "REMOVED"
    assert result.result.data["ad_group_id"] == "789"


@pytest.mark.asyncio
async def test_remove_ad_group_missing_ad_group_id(mock_context, mock_gads_client):
    result = await google_ads.execute_action(
        "remove_ad_group", {**BASE_INPUTS}, mock_context
    )
    assert result.type != ResultType.ACTION
    assert "ad_group_id" in str(result.result)


@pytest.mark.asyncio
async def test_remove_ad_group_auth_error(mock_context):
    mock_context.auth = {"credentials": {}}
    result = await google_ads.execute_action(
        "remove_ad_group",
        {**BASE_INPUTS, "ad_group_id": "789"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_remove_ad_group_api_error(mock_context, mock_gads_client):
    mock_gads_client.get_service.return_value.mutate_ad_groups.side_effect = Exception(
        "Not found"
    )
    mock_gads_client.get_type.return_value = MagicMock()

    result = await google_ads.execute_action(
        "remove_ad_group",
        {**BASE_INPUTS, "ad_group_id": "789"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Not found" in result.result.message
