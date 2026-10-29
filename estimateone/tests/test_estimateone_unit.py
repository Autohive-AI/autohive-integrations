from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType
from estimateone.estimateone import ListMatchedProjectsAction, estimateone

pytestmark = pytest.mark.unit


def response(data):
    return FetchResponse(status=200, headers={}, data=data)


@pytest.fixture
def context():
    ctx = MagicMock()
    ctx.auth = {"auth_type": "Custom", "credentials": {"client_id": "test-client", "client_secret": "test-secret"}}  # nosec B105 - synthetic test credential
    ctx.fetch = AsyncMock()
    return ctx


def page(projects=None, cursor=None, more=False):
    return response({"data": projects or [], "_metadata": {"nextCursor": cursor, "hasNextPage": more}})


async def test_projects_and_next_cursor(context):
    projects = [{"projectId": "123", "projectName": "Office", "tenders": [{"id": "456", "matchedKeywords": ["steel"]}]}]
    context.fetch.side_effect = [response({"access_token": "test-token"}), page(projects, "opaque+/=", True)]  # nosec B105 - synthetic test credential
    result = await estimateone.execute_action(
        "list_matched_projects",
        {
            "company_id": "2030",
            "cursor": "previous+/=",
            "limit": 100,
            "created_since": "2026-10-01T00:00:00Z",
        },
        context,
    )
    assert result.type == ResultType.ACTION
    assert result.result.data == {"projects": projects, "next_cursor": "opaque+/=", "has_next_page": True}
    token_call, data_call = context.fetch.call_args_list
    assert token_call.args[0] == "https://auth.api.estimateone.com/oauth2/token"
    assert token_call.kwargs["data"] == {
        "grant_type": "client_credentials",
        "client_id": "test-client",
        "client_secret": "test-secret",  # nosec B105 - synthetic test credential
    }
    assert token_call.kwargs["content_type"] == "application/x-www-form-urlencoded"
    assert data_call.args[0].endswith("/2030/speci-finder/results")
    assert data_call.kwargs["params"] == {
        "limit": 100,
        "cursor": "previous+/=",
        "createdSince": "2026-10-01T00:00:00Z",
    }
    assert data_call.kwargs["headers"]["x-e1-client-id"] == "test-client"
    assert data_call.kwargs["headers"]["Authorization"] == "Bearer test-token"


async def test_empty_last_page(context):
    context.fetch.side_effect = [response({"access_token": "test-token"}), page()]  # nosec B105 - synthetic test credential
    result = await ListMatchedProjectsAction().execute({"company_id": "2030"}, context)
    assert result.data == {"projects": [], "next_cursor": None, "has_next_page": False}
    assert context.fetch.call_args.kwargs["params"] == {"limit": 25}


async def test_retry_401_once(context):
    context.fetch.side_effect = [
        response({"access_token": "old"}),  # nosec B105 - synthetic test credential
        HTTPError(401, "Expired"),
        response({"access_token": "new"}),  # nosec B105 - synthetic test credential
        page(),
    ]
    await ListMatchedProjectsAction().execute({"company_id": "2030"}, context)
    assert context.fetch.await_count == 4
    assert context.fetch.call_args.kwargs["headers"]["Authorization"] == "Bearer new"


async def test_persistent_401_stops(context):
    context.fetch.side_effect = [
        response({"access_token": "old"}),  # nosec B105 - synthetic test credential
        HTTPError(401, "Denied"),
        response({"access_token": "new"}),  # nosec B105 - synthetic test credential
        HTTPError(401, "Denied"),
    ]
    with pytest.raises(HTTPError):
        await ListMatchedProjectsAction().execute({"company_id": "2030"}, context)
    assert context.fetch.await_count == 4


@pytest.mark.parametrize(
    "error", [HTTPError(403, "Denied"), RateLimitError(60, 429, "Throttled"), HTTPError(500, "Unavailable")]
)
async def test_other_errors_are_not_retried(context, error):
    context.fetch.side_effect = [response({"access_token": "test-token"}), error]  # nosec B105 - synthetic test credential
    with pytest.raises(HTTPError):
        await ListMatchedProjectsAction().execute({"company_id": "2030"}, context)
    assert context.fetch.await_count == 2


@pytest.mark.parametrize("body", [{}, {"access_token": ""}, {"access_token": 1}, []])  # nosec B105 - synthetic test credential
async def test_invalid_token(context, body):
    context.fetch.return_value = response(body)
    with pytest.raises(ValueError):
        await ListMatchedProjectsAction().execute({"company_id": "2030"}, context)
    assert context.fetch.await_count == 1


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"data": {}, "_metadata": {}},
        {"data": [], "_metadata": {}},
        {"data": [], "_metadata": {"hasNextPage": True}},
        {"data": [], "_metadata": {"hasNextPage": False, "nextCursor": 7}},
    ],
)
async def test_invalid_response(context, body):
    context.fetch.side_effect = [response({"access_token": "test-token"}), response(body)]  # nosec B105 - synthetic test credential
    with pytest.raises(ValueError):
        await ListMatchedProjectsAction().execute({"company_id": "2030"}, context)


@pytest.mark.parametrize(
    "inputs",
    [
        {},
        {"company_id": "../other"},
        {"company_id": "2030", "limit": 101},
        {"company_id": "2030", "limit": 0},
        {"company_id": "2030", "url": "https://other"},
    ],
)
async def test_invalid_inputs_do_not_call_api(context, inputs):
    result = await estimateone.execute_action("list_matched_projects", inputs, context)
    assert result.type == ResultType.VALIDATION_ERROR
    context.fetch.assert_not_called()


async def test_invalid_company_id_direct(context):
    with pytest.raises(ValueError):
        await ListMatchedProjectsAction().execute({"company_id": "../other"}, context)
    context.fetch.assert_not_called()
