from urllib.parse import unquote
from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from authorize_sandbox import exchange, save_credentials
from trademe.trademe import oauth_header, trademe

pytestmark = pytest.mark.unit

LISTS = [
    ("list_selling_items", "SellingItems", "All"),
    ("list_sold_items", "SoldItems", "Last45Days"),
    ("list_unsold_items", "UnsoldItems", "Last45Days"),
]


def response(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def test_oauth_encoding():
    header = oauth_header("key /+", "secret&= /", "token/+", "token&secret")
    values = dict(part.strip().split("=", 1) for part in header.removeprefix("OAuth ").split(","))
    values = {key: unquote(value.strip('"')) for key, value in values.items()}
    assert values == {
        "oauth_consumer_key": "key /+",
        "oauth_token": "token/+",  # nosec B105 - mock credential
        "oauth_signature_method": "PLAINTEXT",
        "oauth_signature": "secret%26%3D%20%2F&token%26secret",
    }


async def test_profile(mock_context):
    mock_context.fetch.return_value = response({"SellingCount": 3, "SoldCount": 2})
    result = await trademe.execute_action("get_profile", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == {"profile": {"SellingCount": 3, "SoldCount": 2}}
    call = mock_context.fetch.call_args
    assert call.args[0] == "https://api.tmsandbox.co.nz/v1/MyTradeMe/Summary.json"
    assert call.kwargs["method"] == "GET"
    assert call.kwargs["headers"]["Authorization"] == (
        'OAuth oauth_consumer_key="test-consumer", oauth_signature_method="PLAINTEXT", '
        'oauth_signature="test-consumer-secret%26test-token-secret", oauth_token="test-token"'
    )


async def test_explicit_production(mock_context):
    mock_context.auth["credentials"]["environment"] = "production"
    mock_context.fetch.return_value = response({"SellingCount": 0})
    await trademe.execute_action("get_profile", {}, mock_context)
    assert mock_context.fetch.call_args.args[0].startswith("https://api.trademe.co.nz/")


async def test_default_is_sandbox(mock_context):
    del mock_context.auth["credentials"]["environment"]
    mock_context.fetch.return_value = response({"SellingCount": 0})
    result = await trademe.execute_action("get_profile", {}, mock_context)
    assert result.type == ResultType.ACTION
    assert mock_context.fetch.call_args.args[0].startswith("https://api.tmsandbox.co.nz/")


@pytest.mark.parametrize("action,resource,default_filter", LISTS)
async def test_list_defaults(action, resource, default_filter, mock_context):
    body = {"List": [{"ListingId": 123}], "TotalCount": 65, "Page": 1, "PageSize": 50}
    mock_context.fetch.return_value = response(body)
    result = await trademe.execute_action(action, {}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == {"items": body["List"], "total_count": 65, "page": 1, "page_size": 50}
    call = mock_context.fetch.call_args
    assert call.args[0] == f"https://api.tmsandbox.co.nz/v1/MyTradeMe/{resource}/{default_filter}.json"
    assert call.kwargs["params"] == {"page": 1, "rows": 50}


@pytest.mark.parametrize("action,resource,default_filter", LISTS)
async def test_list_next_page(action, resource, default_filter, mock_context):
    chosen_filter = "ClosingToday" if resource == "SellingItems" else "LastHour"
    mock_context.fetch.return_value = response({"List": None, "TotalCount": 2, "Page": 2, "PageSize": 0})
    result = await trademe.execute_action(action, {"filter": chosen_filter, "page": 2, "rows": 2}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == {"items": [], "total_count": 2, "page": 2, "page_size": 0}
    assert mock_context.fetch.call_args.args[0].endswith(f"/{chosen_filter}.json")
    assert mock_context.fetch.call_args.kwargs["params"] == {"page": 2, "rows": 2}
    mock_context.fetch.assert_awaited_once()


async def test_owned_listing(mock_context):
    mock_context.fetch.return_value = response({"Title": "Sandbox listing", "Description": ["Example"]})
    result = await trademe.execute_action("get_selling_listing", {"listing_id": 123}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["listing"]["Title"] == "Sandbox listing"
    assert mock_context.fetch.call_args.args[0] == "https://api.tmsandbox.co.nz/v1/Selling/Listings/123.json"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
@pytest.mark.parametrize("raises", [False, True])
async def test_safe_errors(status, raises, mock_context):
    if raises:
        mock_context.fetch.side_effect = HTTPError(status, "private-provider-data")
    else:
        mock_context.fetch.return_value = response({"ErrorDescription": "private-provider-data"}, status)
    result = await trademe.execute_action("get_profile", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Trade Me" in result.result.message
    assert "private-provider-data" not in result.result.message


@pytest.mark.parametrize(
    "action,inputs", [(name, {}) for name, _, _ in LISTS] + [("get_selling_listing", {"listing_id": 1})]
)
async def test_action_errors(action, inputs, mock_context):
    mock_context.fetch.side_effect = HTTPError(401, "Unauthorized")
    result = await trademe.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.parametrize("data", [None, [], "not json"])
async def test_invalid_provider_response(data, mock_context):
    mock_context.fetch.return_value = response(data)
    result = await trademe.execute_action("get_profile", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("get_selling_listing", {}),
        ("get_selling_listing", {"listing_id": "../Summary"}),
        ("list_selling_items", {"page": 0}),
        ("list_sold_items", {"rows": 101}),
        ("list_unsold_items", {"filter": "All"}),
    ],
)
async def test_invalid_inputs(action, inputs, mock_context):
    result = await trademe.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()


async def test_invalid_environment(mock_context):
    mock_context.auth["credentials"]["environment"] = "https://other.example"
    result = await trademe.execute_action("get_profile", {}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize("field", ["consumer_key", "consumer_secret", "access_token", "access_token_secret"])
async def test_missing_credentials(field, mock_context):
    del mock_context.auth["credentials"][field]
    result = await trademe.execute_action("get_profile", {}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()


def test_save_credentials(tmp_path):
    path = tmp_path / ".env"
    path.write_text("OTHER_KEY=preserve\nTRADEME_ACCESS_TOKEN=old\n")
    save_credentials(path, {"TRADEME_ACCESS_TOKEN": "new"})  # nosec B105 - mock credential
    assert path.read_text() == 'OTHER_KEY=preserve\nTRADEME_ACCESS_TOKEN="new"\n'


async def test_token_exchange():
    session = MagicMock()
    result = MagicMock(status=200)
    result.text = AsyncMock(return_value="oauth_token=token%2B&oauth_token_secret=secret%26")
    session.post.return_value.__aenter__ = AsyncMock(return_value=result)
    assert await exchange(session, "RequestToken", "OAuth example", {"scope": "MyTradeMeRead"}) == ("token+", "secret&")
    call = session.post.call_args
    assert call.args[0] == "https://api.tmsandbox.co.nz/Oauth/RequestToken"
    assert call.kwargs["allow_redirects"] is False
    assert call.kwargs["params"] == {"scope": "MyTradeMeRead"}


async def test_token_error_does_not_expose_response():
    session = MagicMock()
    session.post.return_value.__aenter__ = AsyncMock(return_value=MagicMock(status=401))
    with pytest.raises(RuntimeError, match="HTTP 401"):
        await exchange(session, "AccessToken", "private-header")
