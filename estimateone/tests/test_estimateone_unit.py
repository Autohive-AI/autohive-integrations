from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientConnectionError

import pytest
from autohive_integrations_sdk import ActionError, FetchResponse, HTTPError, RateLimitError, ResultType
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
    data = result.result.data
    assert data["company_id"] == "2030"
    assert data["projects"] == [
        {
            "id": "123",
            "name": "Office",
            "status": None,
            "category": None,
            "address": None,
            "created_at": None,
            "budget": {"low": None, "high": None},
            "tender_count": 1,
            "tenders": [],
        }
    ]
    assert data["returned_count"] == 1
    assert data["total_matching"] is None
    assert data["next_cursor"] == "opaque+/="
    assert data["has_next_page"] is True
    assert data["truncated"] is True
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
    assert result.data["projects"] == []
    assert result.data["returned_count"] == 0
    assert result.data["next_cursor"] is None
    assert result.data["has_next_page"] is False
    assert "keywords" in result.data["message"]
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
    result = await ListMatchedProjectsAction().execute({"company_id": "2030"}, context)
    assert isinstance(result, ActionError)
    assert "list_matched_projects" in result.message
    assert context.fetch.await_count == 4


@pytest.mark.parametrize(
    "error", [HTTPError(403, "Denied"), RateLimitError(60, 429, "Throttled"), HTTPError(500, "Unavailable")]
)
async def test_other_errors_are_not_retried(context, error):
    context.fetch.side_effect = [response({"access_token": "test-token"}), error]  # nosec B105 - synthetic test credential
    result = await ListMatchedProjectsAction().execute({"company_id": "2030"}, context)
    assert isinstance(result, ActionError)
    assert "list_matched_projects" in result.message
    assert context.fetch.await_count == 2


@pytest.mark.parametrize("body", [{}, {"access_token": ""}, {"access_token": 1}, []])  # nosec B105 - synthetic test credential
async def test_invalid_token(context, body):
    context.fetch.return_value = response(body)
    result = await ListMatchedProjectsAction().execute({"company_id": "2030"}, context)
    assert isinstance(result, ActionError)
    assert "No partial page" in result.message
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
    result = await ListMatchedProjectsAction().execute({"company_id": "2030"}, context)
    assert isinstance(result, ActionError)
    assert "No partial page" in result.message


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
    result = await ListMatchedProjectsAction().execute({"company_id": "../other"}, context)
    assert isinstance(result, ActionError)
    assert "company_id" in result.message
    context.fetch.assert_not_called()


@pytest.mark.parametrize("created_since", ["2026-10-01", "2026-10-01T00:00:00", "2026-02-30T00:00:00Z", "yesterday"])
async def test_invalid_timestamp_before_authentication(context, created_since):
    result = await estimateone.execute_action(
        "list_matched_projects",
        {
            "company_id": "2030",
            "created_since": created_since,
        },
        context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "created_since" in result.result.message
    assert "list_matched_projects" in result.result.message
    context.fetch.assert_not_called()


async def test_curated_tenders_omit_bulk_enrichment(context):
    project = {
        "projectId": "123",
        "projectName": "Office",
        "status": "Active",
        "category": "Commercial",
        "budget": {"low": 0, "high": None},
        "consultants": [{"name": "Not needed"}],
        "tenderingSubcontractors": [{"name": "Not needed"}],
        "tenders": [
            {
                "id": "456",
                "name": "Structure",
                "type": "Tender",
                "quotesDueAt": "2026-11-01",
                "builder": {"name": "Builder", "website": "https://example.com"},
                "description": "Very long body" * 10000,
            }
        ],
    }
    context.fetch.side_effect = [response({"access_token": "fixture"}), page([project])]  # nosec B105
    result = await estimateone.execute_action(
        "list_matched_projects",
        {
            "company_id": "2030",
            "include_tenders": True,
        },
        context,
    )
    assert result.type == ResultType.ACTION
    summary = result.result.data["projects"][0]
    assert summary["budget"] == {"low": 0, "high": None}
    assert summary["tenders"] == [
        {
            "id": "456",
            "name": "Structure",
            "type": "Tender",
            "builder": {"name": "Builder"},
            "quotes_due_at": "2026-11-01",
        }
    ]
    assert "consultants" not in summary
    assert "description" not in summary["tenders"][0]


async def test_oversized_output_is_error_not_partial_success(context):
    context.fetch.side_effect = [
        response({"access_token": "fixture"}),  # nosec B105
        page([{"projectId": "123", "projectName": "x" * 40000, "tenders": []}]),
    ]
    result = await estimateone.execute_action("list_matched_projects", {"company_id": "2030"}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "32 KiB" in result.result.message
    assert "include_tenders=false" in result.result.message
    assert "limit" in result.result.message


@pytest.mark.parametrize(
    "projects,cursor,more",
    [
        ([{"projectId": "1", "tenders": []}] * 2, None, False),
        ([], "unchanged", True),
        ([{"projectId": "1", "tenders": "invalid"}], None, False),
        ([{"projectId": "1", "tenders": [], "budget": {"low": "unknown"}}], None, False),
    ],
)
async def test_incomplete_or_invalid_page_is_action_error(context, projects, cursor, more):
    context.fetch.side_effect = [response({"access_token": "fixture"}), page(projects, cursor, more)]  # nosec B105
    result = await estimateone.execute_action(
        "list_matched_projects",
        {
            "company_id": "2030",
            "cursor": "unchanged",
            "limit": 1,
        },
        context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "No partial page" in result.result.message


async def test_empty_created_since_hint(context):
    context.fetch.side_effect = [response({"access_token": "fixture"}), page()]  # nosec B105
    result = await estimateone.execute_action(
        "list_matched_projects",
        {
            "company_id": "2030",
            "created_since": "2026-10-01T00:00:00+13:00",
        },
        context,
    )
    assert result.type == ResultType.ACTION
    assert "without created_since" in result.result.data["message"]


async def test_provider_body_redacted_and_next_step(context):
    error = HTTPError(
        400,
        "Invalid",
        response_data={
            "_errors": [
                {
                    "code": "INVALID_CURSOR",
                    "detail": "cursor rejected for test-secret and fixture",
                    "source": {"parameter": "cursor"},
                }
            ],
            "access_token": "do-not-return",  # nosec B105
            "html": "<html>secret</html>",
        },
    )  # nosec B105
    context.fetch.side_effect = [response({"access_token": "fixture"}), error]  # nosec B105
    result = await estimateone.execute_action("list_matched_projects", {"company_id": "2030"}, context)
    assert result.type == ResultType.ACTION_ERROR
    message = result.result.message
    assert "INVALID_CURSOR" in message
    assert "without cursor" in message
    assert "test-secret" not in message
    assert "fixture" not in message
    assert "do-not-return" not in message
    assert "<html>" not in message


async def test_rate_limit_names_call_and_wait(context):
    context.fetch.side_effect = [response({"access_token": "fixture"}), RateLimitError(60, 429, "Throttled")]  # nosec B105
    result = await estimateone.execute_action("list_matched_projects", {"company_id": "2030"}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "300 seconds" in result.result.message
    assert "list_matched_projects again" in result.result.message
    assert context.fetch.await_count == 2


@pytest.mark.parametrize("error", [TimeoutError(), ClientConnectionError()])
async def test_timeout_action_error(context, error):
    context.fetch.side_effect = error
    result = await estimateone.execute_action("list_matched_projects", {"company_id": "2030"}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Retrying this read is safe" in result.result.message


def test_agent_schema_contract():
    import json
    from pathlib import Path

    config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
    assert config["version"] == "2.0.0"

    def check(schema):
        if isinstance(schema, dict):
            if schema.get("type") == "array":
                assert "items" in schema
            for value in schema.values():
                check(value)
        elif isinstance(schema, list):
            for value in schema:
                check(value)

    for action in config["actions"].values():
        assert not {"oneOf", "anyOf", "allOf"}.intersection(action["input_schema"])
        for schema in (action["input_schema"], action["output_schema"]):
            for prop in schema["properties"].values():
                assert prop.get("description")
            check(schema)


async def test_token_rejection_requires_user_not_cursor_retry(context):
    context.fetch.side_effect = HTTPError(400, "Invalid client", response_data={"error": "invalid_client"})
    result = await estimateone.execute_action("list_matched_projects", {"company_id": "2030"}, context)
    assert result.type == ResultType.ACTION_ERROR
    assert "user must fix" in result.result.message
    assert "invalid_client" in result.result.message
    assert "without cursor" not in result.result.message
    assert context.fetch.await_count == 1


@pytest.mark.parametrize("budget", [False, 0, "invalid"])
async def test_invalid_falsy_budget_is_not_unknown(context, budget):
    context.fetch.side_effect = [
        response({"access_token": "fixture"}),  # nosec B105
        page([{"projectId": "1", "tenders": [], "budget": budget}]),
    ]
    result = await estimateone.execute_action("list_matched_projects", {"company_id": "2030"}, context)
    assert result.type == ResultType.ACTION_ERROR
