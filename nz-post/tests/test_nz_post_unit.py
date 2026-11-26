"""Mocked API contracts, application authentication and failure handling."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from aiohttp import ClientConnectionError
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

from nz_post import TOKEN_URL, _token_cache, nz_post

pytestmark = pytest.mark.unit


def response(body):
    return FetchResponse(status=200, headers={}, data=body)


def token_response(value="test-access", expires_in=3600):  # nosec B107
    return response({"access_token": value, "token_type": "Bearer", "expires_in": expires_in})  # nosec B105: OAuth type


@pytest.fixture(autouse=True)
def application_credentials(monkeypatch):
    monkeypatch.setenv("NZPOST_CLIENT_ID", "test-application")
    monkeypatch.setenv("NZPOST_CLIENT_SECRET", "test-application-credential")
    _token_cache.clear()
    yield
    _token_cache.clear()


async def lookup(context):
    return await nz_post.execute_action("search_addresses", {"query": "151 Victoria"}, context)


async def test_address_search_and_form_encoded_application_auth(mock_context):
    addresses = {"success": True, "addresses": [{"full_address": "151 Victoria Road", "address_id": "949793"}]}
    mock_context.fetch.side_effect = [token_response(), response(addresses)]
    result = await lookup(mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == addresses
    token_call, api_call = mock_context.fetch.call_args_list
    assert token_call.args == (TOKEN_URL,)
    assert token_call.kwargs == {
        "method": "POST",
        "content_type": "application/x-www-form-urlencoded",
        "data": {
            "grant_type": "client_credentials",
            "client_id": "test-application",
            "client_secret": "test-application-credential",  # nosec B105: dummy test credential
        },
    }
    assert api_call.args == ("https://api.nzpost.co.nz/parceladdress/2.0/domestic/addresses",)
    assert api_call.kwargs["headers"]["Authorization"] == "Bearer test-access"
    assert "test-application-credential" not in str(result)


async def test_search_then_get_address(mock_context):
    search = {"success": True, "addresses": [{"full_address": "151 Victoria Road", "address_id": "949793"}]}
    detail = {"success": True, "address": {"postcode": "9012", "is_rural_delivery": False, "dpid": "1376601"}}
    mock_context.fetch.side_effect = [token_response(), response(search), response(detail)]
    result = await nz_post.execute_action("search_addresses", {"query": "  151 Victoria  ", "count": 5}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == search
    assert mock_context.fetch.call_args.kwargs["params"] == {"q": "151 Victoria", "count": 5}
    result = await nz_post.execute_action("get_address", {"address_id": "949793"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == detail
    assert mock_context.fetch.call_args.args[0].endswith("/parceladdress/2.0/domestic/addresses/949793")
    assert mock_context.fetch.await_count == 3  # Token shared by both address actions.


async def test_no_matching_addresses_is_success(mock_context):
    mock_context.fetch.side_effect = [token_response(), response({"success": True, "addresses": []})]
    result = await nz_post.execute_action("search_addresses", {"query": "No match"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["addresses"] == []
    assert mock_context.fetch.call_args.kwargs["params"]["count"] == 10


@pytest.mark.parametrize(
    "action, inputs",
    [
        ("search_addresses", {"query": " a  "}),
        ("search_addresses", {"query": "Victoria", "count": 11}),
        ("search_addresses", {"query": "Victoria", "count": 0}),
        ("search_addresses", {"query": "Victoria", "count": "5"}),
        ("get_address", {"address_id": "../123"}),
        ("get_address", {"address_id": "１２３"}),
    ],
)
async def test_invalid_inputs_never_make_requests(mock_context, action, inputs):
    result = await nz_post.execute_action(action, inputs, mock_context)
    assert result.type in (ResultType.VALIDATION_ERROR, ResultType.ACTION_ERROR)
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize("variable", ["NZPOST_CLIENT_ID", "NZPOST_CLIENT_SECRET"])
async def test_missing_shared_configuration(mock_context, monkeypatch, variable):
    monkeypatch.delenv(variable)
    result = await lookup(mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "administrator" in result.result.message
    mock_context.fetch.assert_not_awaited()


async def test_cache_refreshes_before_expiry(mock_context):
    mock_context.fetch.side_effect = [
        token_response(),
        response({"success": True, "addresses": []}),
        token_response(),
        response({"success": True, "addresses": []}),
    ]
    with patch("nz_post.time.monotonic", return_value=1000):
        await lookup(mock_context)
    with patch("nz_post.time.monotonic", return_value=4541):
        await lookup(mock_context)
    assert mock_context.fetch.await_count == 4


@pytest.mark.parametrize(
    "variable,new_value",
    [("NZPOST_CLIENT_ID", "rotated-id"), ("NZPOST_CLIENT_SECRET", "rotated-credential")],
)
async def test_cache_isolated_on_configuration_changes(mock_context, monkeypatch, variable, new_value):
    mock_context.fetch.side_effect = [
        token_response(),
        response({"success": True, "addresses": []}),
        token_response(),
        response({"success": True, "addresses": []}),
    ]
    await lookup(mock_context)
    monkeypatch.setenv(variable, new_value)
    await lookup(mock_context)
    assert mock_context.fetch.await_count == 4
    assert len(_token_cache) == 1


async def test_unauthorised_request_renews_token_once(mock_context):
    mock_context.fetch.side_effect = [
        token_response(),
        HTTPError(401, "expired"),
        token_response("new-access"),
        response({"success": True, "addresses": []}),
    ]
    assert (await lookup(mock_context)).type == ResultType.ACTION
    assert mock_context.fetch.await_count == 4
    assert mock_context.fetch.call_args.kwargs["headers"]["Authorization"] == "Bearer new-access"


async def test_repeated_unauthorised_request_stops(mock_context):
    mock_context.fetch.side_effect = [
        token_response(),
        HTTPError(401, "expired"),
        token_response(),
        HTTPError(401, "expired"),
    ]
    result = await lookup(mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert mock_context.fetch.await_count == 4
    assert not _token_cache


@pytest.mark.parametrize("status", [400, 403, 404, 500])
async def test_http_failures_do_not_echo_provider_bodies(mock_context, status):
    mock_context.fetch.side_effect = [token_response(), HTTPError(status, "sensitive-provider-body")]
    result = await lookup(mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "sensitive-provider-body" not in str(result)
    assert mock_context.fetch.await_count == 2


async def test_rate_limit_preserves_retry_guidance(mock_context):
    mock_context.fetch.side_effect = [token_response(), RateLimitError(23, 429, "sensitive-provider-body")]
    result = await lookup(mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "23 seconds" in result.result.message


async def test_token_error_does_not_echo_credentials(mock_context):
    mock_context.fetch.side_effect = HTTPError(401, "test-application-credential")
    result = await lookup(mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "test-application-credential" not in str(result)
    assert mock_context.fetch.await_count == 1


@pytest.mark.parametrize("expiry", [None, "invalid", -1, 0, "nan", "inf"])
async def test_invalid_token_expiry(mock_context, expiry):
    mock_context.fetch.return_value = token_response(expires_in=expiry)
    assert (await lookup(mock_context)).type == ResultType.ACTION_ERROR
    assert mock_context.fetch.await_count == 1
    assert not _token_cache


@pytest.mark.parametrize("body", [{}, {"access_token": ""}, {"access_token": 123}, "invalid"])  # nosec B105: invalid fixtures
async def test_invalid_token_response(mock_context, body):
    mock_context.fetch.return_value = response(body)
    assert (await lookup(mock_context)).type == ResultType.ACTION_ERROR
    assert not _token_cache


@pytest.mark.parametrize("error", [ClientConnectionError("private network detail"), TimeoutError()])
async def test_network_failures_are_sanitised(mock_context, error):
    mock_context.fetch.side_effect = [token_response(), error]
    result = await lookup(mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "private network detail" not in str(result)


@pytest.mark.parametrize("success", [True, False])
async def test_application_error_inside_http_200(mock_context, success):
    mock_context.fetch.side_effect = [
        token_response(),
        response({"success": success, "errors": [{"code": "400002", "details": "private input"}]}),
    ]
    result = await lookup(mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "400002" in result.result.message
    assert "private input" not in str(result)


async def test_partial_result_warnings_are_preserved(mock_context):
    body = {"success": True, "addresses": [], "errors": [{"code": "200001", "message": "Partial results"}]}
    mock_context.fetch.side_effect = [token_response(), response(body)]
    result = await lookup(mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == body


@pytest.mark.parametrize("body", ["not JSON", [], {}])
async def test_malformed_api_response(mock_context, body):
    mock_context.fetch.side_effect = [token_response(), response(body)]
    assert (await lookup(mock_context)).type == ResultType.ACTION_ERROR


async def test_check_address_preserves_candidates_and_scores(mock_context):
    body = {
        "success": True,
        "status": "success",
        "addresses": [
            {"DPID": 3499717, "FullAddress": "8 Waterloo Quay, Wellington 6011", "MatchScore": 95, "Deliverable": "N"},
            {"DPID": 109570, "FullAddress": "8 Water Lane, New Plymouth 4310", "MatchScore": 42, "Deliverable": "Y"},
        ],
    }
    mock_context.fetch.side_effect = [token_response(), response(deepcopy(body))]
    result = await nz_post.execute_action(
        "check_address",
        {
            "address_line_1": " 8 waterloo quay ",
            "address_line_2": " Pipitea ",
            "address_line_3": "Wellington",
            "address_line_4": " ",
            "address_line_5": "6011",
            "count": 5,
        },
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data == body
    assert mock_context.fetch.call_args.args[0].endswith("/addresschecker/1.0/find")
    assert mock_context.fetch.call_args.kwargs["params"] == {
        "address_line_1": "8 waterloo quay",
        "address_line_2": "Pipitea",
        "address_line_3": "Wellington",
        "address_line_5": "6011",
        "max": 5,
    }


@pytest.mark.parametrize("as_list", [True, False])
async def test_postal_details_preserve_provider_fields(mock_context, as_list):
    detail = {
        "DPID": 109570,
        "AddressLine1": "8 Water Lane",
        "AddressLine2": "New Plymouth 4310",
        "AddressLine3": None,
        "Postcode": "4310",
        "RuralDelivery": None,
        "Deliverable": "Y",
        "DeliveredOnMonday": True,
        "NZGD2kCoord": {"type": "Point", "coordinates": [174.1, -39.0]},
    }
    body = {"success": True, "status": "success", "details": [detail] if as_list else detail}
    mock_context.fetch.side_effect = [token_response(), response(deepcopy(body))]
    result = await nz_post.execute_action("get_postal_address_details", {"dpid": " 109570 "}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == body
    assert mock_context.fetch.call_args.args[0].endswith("/addresschecker/1.0/details")
    assert mock_context.fetch.call_args.kwargs["params"] == {"dpid": "109570"}


async def test_partial_address_search(mock_context):
    body = {
        "success": True,
        "addresses": [{"UniqueId": 109570, "FullPartial": "Willis Street, Te Aro, Wellington 6011"}],
    }
    mock_context.fetch.side_effect = [token_response(), response(body)]
    result = await nz_post.execute_action("search_partial_addresses", {"query": " willis ", "count": 5}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == body
    assert mock_context.fetch.call_args.args[0].endswith("/addresschecker/1.0/suggest_partial")
    assert mock_context.fetch.call_args.kwargs["params"] == {"q": "willis", "max": 5}


@pytest.mark.parametrize(
    "action,inputs",
    [("check_address", {"address_line_1": "No match"}), ("search_partial_addresses", {"query": "No match"})],
)
async def test_addresschecker_empty_matches_are_success(mock_context, action, inputs):
    mock_context.fetch.side_effect = [token_response(), response({"success": True, "addresses": []})]
    result = await nz_post.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data["addresses"] == []
    assert mock_context.fetch.call_args.kwargs["params"]["max"] == 10


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("check_address", {}),
        ("check_address", {"address_line_1": "   "}),
        ("check_address", {"address_line_1": "8 water", "count": 11}),
        ("check_address", {"address_line_1": "8 water", "address_line_2": 42}),
        ("get_postal_address_details", {"dpid": "../109570"}),
        ("get_postal_address_details", {"dpid": "１２３"}),
        ("get_postal_address_details", {"dpid": 109570}),
        ("search_partial_addresses", {"query": "   "}),
        ("search_partial_addresses", {"query": "willis", "count": 0}),
        ("search_partial_addresses", {"query": "willis", "count": "5"}),
    ],
)
async def test_addresschecker_invalid_input_makes_no_request(mock_context, action, inputs):
    result = await nz_post.execute_action(action, inputs, mock_context)
    assert result.type in (ResultType.VALIDATION_ERROR, ResultType.ACTION_ERROR)
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize(
    "action,inputs,body",
    [
        ("check_address", {"address_line_1": "8 water"}, {"success": True, "addresses": {}}),
        ("get_postal_address_details", {"dpid": "109570"}, {"success": True, "details": "invalid"}),
        ("search_partial_addresses", {"query": "willis"}, {"success": True}),
    ],
)
async def test_addresschecker_malformed_payloads_are_errors(mock_context, action, inputs, body):
    mock_context.fetch.side_effect = [token_response(), response(body)]
    result = await nz_post.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("check_address", {"address_line_1": "8 water"}),
        ("get_postal_address_details", {"dpid": "109570"}),
        ("search_partial_addresses", {"query": "willis"}),
    ],
)
async def test_addresschecker_provider_failure(mock_context, action, inputs):
    mock_context.fetch.side_effect = [token_response(), response({"success": False, "status": "failed"})]
    result = await nz_post.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION_ERROR
