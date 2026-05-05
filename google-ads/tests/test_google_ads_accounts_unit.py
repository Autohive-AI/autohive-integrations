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


def _make_list_response(resource_names):
    mock_response = MagicMock()
    mock_response.resource_names = resource_names
    return mock_response


# ---------------------------------------------------------------------------
# get_accessible_accounts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_refresh_token(mock_context):
    """Missing refresh token returns ActionError with descriptive message."""
    mock_context.auth = {}

    result = await google_ads.execute_action("get_accessible_accounts", {}, mock_context)

    assert result.type == ResultType.ACTION_ERROR
    assert "refresh_token" in result.result.message.lower() or "Refresh token" in result.result.message


@pytest.mark.asyncio
async def test_returns_accounts_list(mock_context, mock_gads_client):
    """Valid credentials with 2 resource names returns ActionResult with accounts key."""
    mock_response = _make_list_response(["customers/111", "customers/222"])
    mock_gads_client.get_service.return_value.list_accessible_customers.return_value = mock_response
    mock_gads_client.get_service.return_value.search.return_value = []

    result = await google_ads.execute_action("get_accessible_accounts", {}, mock_context)

    assert result.type == ResultType.ACTION
    assert "accounts" in result.result.data
    assert len(result.result.data["accounts"]) == 2


@pytest.mark.asyncio
async def test_accounts_have_expected_fields(mock_context, mock_gads_client):
    """Each account entry exposes the four required fields."""
    mock_response = _make_list_response(["customers/111", "customers/222"])
    mock_gads_client.get_service.return_value.list_accessible_customers.return_value = mock_response
    mock_gads_client.get_service.return_value.search.return_value = []

    result = await google_ads.execute_action("get_accessible_accounts", {}, mock_context)

    for account in result.result.data["accounts"]:
        assert "resource_name" in account
        assert "customer_id" in account
        assert "descriptive_name" in account
        assert "currency_code" in account


@pytest.mark.asyncio
async def test_accounts_customer_id_parsed_correctly(mock_context, mock_gads_client):
    """customer_id is the numeric portion of the resource name."""
    mock_response = _make_list_response(["customers/987654321"])
    mock_gads_client.get_service.return_value.list_accessible_customers.return_value = mock_response
    mock_gads_client.get_service.return_value.search.return_value = []

    result = await google_ads.execute_action("get_accessible_accounts", {}, mock_context)

    account = result.result.data["accounts"][0]
    assert account["customer_id"] == "987654321"
    assert account["resource_name"] == "customers/987654321"


@pytest.mark.asyncio
async def test_api_error_returns_action_error(mock_context, mock_gads_client):
    """If list_accessible_customers raises, the action returns ActionError."""
    mock_gads_client.get_service.return_value.list_accessible_customers.side_effect = Exception(
        "API unavailable"
    )

    result = await google_ads.execute_action("get_accessible_accounts", {}, mock_context)

    assert result.type == ResultType.ACTION_ERROR
    assert "API unavailable" in result.result.message


@pytest.mark.asyncio
async def test_empty_accounts(mock_context, mock_gads_client):
    """No accessible customers returns ActionResult with empty accounts list."""
    mock_response = _make_list_response([])
    mock_gads_client.get_service.return_value.list_accessible_customers.return_value = mock_response
    mock_gads_client.get_service.return_value.search.return_value = []

    result = await google_ads.execute_action("get_accessible_accounts", {}, mock_context)

    assert result.type == ResultType.ACTION
    assert result.result.data["accounts"] == []


@pytest.mark.asyncio
async def test_detail_fetch_failure_still_returns_account(mock_context, mock_gads_client):
    """If the per-account detail query fails, the account is still included with default values."""
    mock_response = _make_list_response(["customers/555"])
    service_mock = MagicMock()
    service_mock.list_accessible_customers.return_value = mock_response
    service_mock.search.side_effect = Exception("Permission denied")
    mock_gads_client.get_service.return_value = service_mock

    result = await google_ads.execute_action("get_accessible_accounts", {}, mock_context)

    assert result.type == ResultType.ACTION
    assert len(result.result.data["accounts"]) == 1
    account = result.result.data["accounts"][0]
    assert account["customer_id"] == "555"
    assert account["descriptive_name"] == "Unknown"
    assert account["currency_code"] == "N/A"


@pytest.mark.asyncio
async def test_cost_usd_is_zero(mock_context, mock_gads_client):
    """Successful response carries cost_usd of 0.00."""
    mock_response = _make_list_response(["customers/111"])
    mock_gads_client.get_service.return_value.list_accessible_customers.return_value = mock_response
    mock_gads_client.get_service.return_value.search.return_value = []

    result = await google_ads.execute_action("get_accessible_accounts", {}, mock_context)

    assert result.type == ResultType.ACTION
    assert result.result.cost_usd == 0.00
