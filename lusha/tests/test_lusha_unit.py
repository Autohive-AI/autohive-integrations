"""Contract tests for Lusha v3. All records and credentials are synthetic."""

import copy

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, RateLimitError, ResultType

from lusha.lusha import lusha, request

pytestmark = pytest.mark.unit

CASES = [
    ("search_contacts", {"contacts": [{"email": "person@example.com"}]}, "contacts/search"),
    ("enrich_contacts", {"ids": ["contact-1"]}, "contacts/enrich"),
    ("search_and_enrich_contacts", {"contacts": [{"id": "contact-1"}]}, "contacts/search-and-enrich"),
    ("search_companies", {"companies": [{"domain": "example.com"}]}, "companies/search"),
    ("enrich_companies", {"ids": ["company-1"]}, "companies/enrich"),
    ("search_and_enrich_companies", {"companies": [{"name": "Example"}]}, "companies/search-and-enrich"),
    ("prospect_contacts", {"filters": {"contacts": {"include": {"departments": ["Sales"]}}}}, "contacts/prospecting"),
    (
        "prospect_companies",
        {"filters": {"companies": {"include": {"domains": ["example.com"]}}}},
        "companies/prospecting",
    ),
    ("list_filter_types", {"entity": "contacts"}, "contacts/prospecting/filters"),
    ("get_filter_values", {"entity": "companies", "filter_type": "sizes"}, "companies/prospecting/filters/sizes"),
    ("get_account_usage", {}, "account/usage"),
    ("get_contact_enrichment_job", {"job_id": "wf_example"}, "contacts/jobs/wf_example"),
]


def response_for(action):
    if action == "list_filter_types":
        return {"availableFilters": [{"filterType": "locations", "requiresQuery": True}]}
    if action == "get_filter_values":
        return {"values": [{"min": 10, "max": 50}], "total": 1, "truncated": False}
    if action == "get_account_usage":
        return {"credits": {"total": 100, "used": 25, "remaining": 75}, "plan": {"category": "test"}}
    if action == "get_contact_enrichment_job":
        return {"jobId": "wf_example", "status": "processing", "retryAfter": 5, "covers": []}
    data = {
        "requestId": "request-example",
        "results": [{"id": "record-1"}],
        "billing": {"creditsCharged": 1, "resultsReturned": 1},
    }
    if action.startswith("prospect_"):
        data["pagination"] = {"page": 0, "size": 25, "total": 10000, "totalGuaranteed": False}
    return data


@pytest.mark.parametrize("action,inputs,path", CASES)
async def test_action_contract_and_request(mock_context, action, inputs, path):
    data = response_for(action)
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    original_inputs = copy.deepcopy(inputs)
    result = await lusha.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == data
    assert inputs == original_inputs
    kwargs = mock_context.fetch.call_args.kwargs
    mock_context.fetch.assert_awaited_once()
    assert mock_context.fetch.call_args.args == (f"https://api.lusha.com/v3/{path}",)
    assert kwargs["headers"] == {"api_key": "test-api-key", "Accept": "application/json"}
    method = (
        "GET"
        if action in {"list_filter_types", "get_filter_values", "get_account_usage", "get_contact_enrichment_job"}
        else "POST"
    )
    assert kwargs["method"] == method
    expected_body = copy.deepcopy(inputs) if method == "POST" else None
    if action.startswith("prospect_"):
        expected_body["pagination"] = {"page": 0, "size": 25}
    assert kwargs["json"] == expected_body
    assert kwargs["params"] is None


@pytest.mark.parametrize("action,inputs,path", CASES)
async def test_http_error_is_not_a_success(mock_context, action, inputs, path):
    mock_context.fetch.side_effect = HTTPError(401, "Do not expose provider text or credentials", {})
    result = await lusha.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "authentication failed" in result.result.message
    assert "Do not expose" not in result.result.message


@pytest.mark.parametrize(
    "status,text",
    [
        (400, "rejected"),
        (402, "credits"),
        (403, "access denied"),
        (404, "stop polling"),
        (429, "rate limit"),
        (503, "Retry later"),
        (500, "HTTP 500"),
    ],
)
async def test_provider_error_guidance(mock_context, status, text):
    mock_context.fetch.side_effect = HTTPError(status, "provider-secret", {"message": "provider-secret"})
    result = await lusha.execute_action("get_account_usage", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert text in result.result.message
    assert "provider-secret" not in result.result.message


async def test_rate_limit_retry_after(mock_context):
    mock_context.fetch.side_effect = RateLimitError(37, 429, "too many requests", {})
    result = await lusha.execute_action("get_account_usage", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "37 seconds" in result.result.message
    mock_context.fetch.assert_awaited_once()


@pytest.mark.parametrize(
    "auth",
    [
        {},
        {"api_key": "flat-key"},
        {"auth_type": "Custom", "credentials": {}},
        {"auth_type": "Custom", "credentials": {"api_key": "   "}},
    ],
)
async def test_invalid_auth_never_calls_provider(mock_context, auth):
    mock_context.auth = auth
    result = await lusha.execute_action("get_account_usage", {}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("search_contacts", {"contacts": []}),
        ("search_contacts", {"contacts": [{"id": "x"}] * 101}),
        ("search_contacts", {"contacts": [{"email": None}]}),
        ("search_companies", {"companies": [{"domain": " "}]}),
        ("enrich_contacts", {"ids": ["x"], "reveal": ["competitors"]}),
        ("enrich_contacts", {"ids": ["x"], "reveal": []}),
        ("enrich_companies", {"ids": []}),
        ("enrich_companies", {"ids": [1]}),
        ("search_and_enrich_contacts", {"contacts": [{"id": "x"}], "waterfallEnabled": False}),
        ("search_and_enrich_companies", {}),
        ("prospect_contacts", {"filters": {}, "page": -1}),
        ("prospect_contacts", {"filters": {}, "page": 1001}),
        ("prospect_contacts", {"filters": {}, "size": 9}),
        ("prospect_companies", {"filters": {"companies": {"include": {}}}, "size": 101}),
        ("prospect_companies", {"filters": {"companies": {}}}),
        ("prospect_contacts", {"filters": {"contacts": {"include": {"seniorityIds": ["4"]}}}}),
        ("list_filter_types", {"entity": "people"}),
        ("get_filter_values", {"entity": "companies", "filter_type": "locations", "query": "x"}),
        ("get_contact_enrichment_job", {}),
    ],
)
async def test_schema_validation_blocks_bad_requests(mock_context, action, inputs):
    result = await lusha.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("search_contacts", {"contacts": [{}]}),
        ("search_contacts", {"contacts": [{"firstName": "Alex", "lastName": "Example"}]}),
        ("search_and_enrich_contacts", {"contacts": [{"firstName": "Alex", "companyDomain": "example.com"}]}),
        ("search_companies", {"companies": [{"clientReferenceId": "ref"}]}),
        ("search_and_enrich_companies", {"companies": [{}]}),
        ("prospect_contacts", {"filters": {}}),
        ("get_filter_values", {"entity": "contacts", "filter_type": "locations"}),
        ("get_filter_values", {"entity": "companies", "filter_type": "technologies", "query": "  "}),
    ],
)
async def test_semantic_validation_blocks_bad_requests(mock_context, action, inputs):
    result = await lusha.execute_action(action, inputs, mock_context)
    assert result.type in (ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR)
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize(
    "contact",
    [
        {"id": "contact-1"},
        {"linkedinUrl": "https://www.linkedin.com/in/example"},
        {"email": "person@example.com"},
        {"firstName": "Alex", "lastName": "Example", "companyName": "Example"},
        {"firstName": "Alex", "lastName": "Example", "companyDomain": "example.com"},
    ],
)
async def test_contact_identifier_alternatives(mock_context, contact):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})
    result = await lusha.execute_action("search_contacts", {"contacts": [contact]}, mock_context)
    assert result.type == ResultType.ACTION
    assert mock_context.fetch.call_args.kwargs["json"]["contacts"] == [contact]


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("enrich_contacts", {"ids": ["contact-1"], "reveal": ["emails"], "waterfallEnabled": False}),
        (
            "search_and_enrich_contacts",
            {
                "contacts": [{"id": "contact-1", "clientReferenceId": "my-ref"}],
                "reveal": ["phones"],
                "options": {"includePartialProfiles": False},
            },
        ),
        (
            "search_contacts",
            {"contacts": [{"email": "person@example.com"}], "options": {"includePartialProfiles": False}},
        ),
        ("search_companies", {"companies": [{"domain": "example.com"}], "options": {"includePartialProfiles": False}}),
        ("enrich_companies", {"ids": ["company-1"], "reveal": ["competitors", "directParent"]}),
        (
            "search_and_enrich_companies",
            {
                "companies": [{"domain": "example.com"}],
                "reveal": ["employeesByDepartment"],
                "options": {"includePartialProfiles": True},
            },
        ),
    ],
)
async def test_optional_fields_and_false_values_are_preserved(mock_context, action, inputs):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"results": []})
    result = await lusha.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION
    assert mock_context.fetch.call_args.kwargs["json"] == inputs


@pytest.mark.parametrize("entity", ["contacts", "companies"])
async def test_prospecting_one_page_with_explicit_options(mock_context, entity):
    inputs = {
        "filters": {"companies": {"include": {"domains": ["example.com"]}, "exclude": {"names": ["Excluded"]}}},
        "page": 3,
        "size": 100,
        "options": {"includePartialProfiles": False},
    }
    data = {"results": [], "pagination": {"page": 3, "size": 100, "total": 9999, "totalGuaranteed": False}}
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    result = await lusha.execute_action(f"prospect_{entity}", inputs, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == data
    assert mock_context.fetch.call_args.kwargs["json"] == {
        "filters": inputs["filters"],
        "pagination": {"page": 3, "size": 100},
        "options": inputs["options"],
    }
    mock_context.fetch.assert_awaited_once()


async def test_partial_failure_and_async_job_metadata_survive(mock_context):
    data = {
        "results": [
            {"id": "contact-1", "emails": []},
            {"error": {"code": "NOT_FOUND", "message": "Contact not found"}},
        ],
        "billing": {"creditsCharged": 1},
        "status": "partial",
        "job": {"id": "wf_example", "status": "processing", "retryAfter": 5},
    }
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    result = await lusha.execute_action("enrich_contacts", {"ids": ["contact-1", "missing"]}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == data
    mock_context.fetch.assert_awaited_once()


@pytest.mark.parametrize("status", ["processing", "complete", "expired", "failed"])
async def test_job_states_are_returned_without_polling_or_merging(mock_context, status):
    data = {
        "jobId": "wf_example",
        "status": status,
        "contacts": [{"id": "contact-1", "phones": []}],
        "creditsCharged": 2,
        "retryAfter": 5,
    }
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    result = await lusha.execute_action("get_contact_enrichment_job", {"job_id": "wf_example"}, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == data
    mock_context.fetch.assert_awaited_once()


async def test_filter_query_and_path_encoding(mock_context):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"values": [], "truncated": False})
    result = await lusha.execute_action(
        "get_filter_values",
        {"entity": "companies", "filter_type": "new/type", "query": "  New York & area  "},
        mock_context,
    )
    assert result.type == ResultType.ACTION
    assert mock_context.fetch.call_args.args[0].endswith("filters/new%2Ftype")
    assert mock_context.fetch.call_args.kwargs["params"] == {"query": "New York & area"}


@pytest.mark.parametrize("entity", ["contacts", "companies"])
async def test_discovery_for_both_entities(mock_context, entity):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"availableFilters": []})
    result = await lusha.execute_action("list_filter_types", {"entity": entity}, mock_context)
    assert result.type == ResultType.ACTION
    assert mock_context.fetch.call_args.args[0].endswith(f"{entity}/prospecting/filters")


async def test_unexpected_response_is_action_error(mock_context):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data="<html>bad gateway</html>")
    result = await lusha.execute_action("get_account_usage", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "expected a JSON object" in result.result.message


async def test_empty_key_guard_for_direct_helper_calls(mock_context):
    mock_context.auth["credentials"]["api_key"] = " "
    result = await request(mock_context, "account/usage", method="GET")
    assert "non-empty" in result.message
    mock_context.fetch.assert_not_awaited()
