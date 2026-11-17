"""Offline regressions for live workflow assertions and provider response contracts."""

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

from lusha.lusha import lusha
from lusha.tests.test_lusha_prospecting_integration import test_prospecting as run_prospecting

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("action", ["prospect_contacts", "prospect_companies"])
@pytest.mark.parametrize("reported_size", [1, 10])
async def test_live_workflow_accepts_short_page_and_uses_discovered_filters(mock_context, action, reported_size):
    entity = "contacts" if action == "prospect_contacts" else "companies"
    filter_type = "seniority" if entity == "contacts" else "sizes"
    values = [{"id": 4, "name": "Director"}] if entity == "contacts" else [{"min": 51, "max": 200}]
    mock_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"availableFilters": [{"filterType": filter_type}]}),
        FetchResponse(status=200, headers={}, data={"values": values}),
        FetchResponse(
            status=200,
            headers={},
            data={
                "requestId": "request-example",
                "results": [{"id": "record-1"}],
                "pagination": {"page": 0, "size": reported_size, "total": 1},
                "billing": {"creditsCharged": 1, "resultsReturned": 1},
            },
        ),
    ]
    await run_prospecting(mock_context, "example.com", action)
    calls = mock_context.fetch.await_args_list
    assert len(calls) == 3
    assert calls[0].args[0].endswith(f"{entity}/prospecting/filters")
    assert calls[1].args[0].endswith(f"filters/{filter_type}")
    payload = calls[2].kwargs["json"]
    assert payload["pagination"] == {"page": 0, "size": 10}
    if entity == "contacts":
        assert payload["filters"]["contacts"]["include"]["seniorityIds"] == [4]
    else:
        assert payload["filters"]["companies"]["include"]["sizes"] == values


@pytest.mark.parametrize("reported_size", [0, 11])
async def test_live_workflow_rejects_inconsistent_or_oversized_page(mock_context, reported_size):
    mock_context.fetch.side_effect = [
        FetchResponse(status=200, headers={}, data={"availableFilters": [{"filterType": "sizes"}]}),
        FetchResponse(status=200, headers={}, data={"values": [{"min": 51, "max": 200}]}),
        FetchResponse(
            status=200,
            headers={},
            data={
                "requestId": "request-example",
                "results": [{"id": "company-1"}],
                "pagination": {"page": 0, "size": reported_size},
                "billing": {"creditsCharged": 1, "resultsReturned": 1},
            },
        ),
    ]
    with pytest.raises(AssertionError):
        await run_prospecting(mock_context, "example.com", "prospect_companies")


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("search_contacts", {"contacts": [{"id": "contact-1"}]}),
        ("enrich_contacts", {"ids": ["contact-1"]}),
        ("search_and_enrich_contacts", {"contacts": [{"id": "contact-1"}]}),
        ("search_companies", {"companies": [{"id": "company-1"}]}),
        ("enrich_companies", {"ids": ["company-1"]}),
        ("search_and_enrich_companies", {"companies": [{"id": "company-1"}]}),
        ("prospect_contacts", {"filters": {"companies": {"include": {"domains": ["example.com"]}}}}),
        ("prospect_companies", {"filters": {"companies": {"include": {"domains": ["example.com"]}}}}),
    ],
)
async def test_schema_preserves_error_only_records_and_future_fields(mock_context, action, inputs):
    data = {
        "requestId": "request-example",
        "results": [
            {"error": {"code": "COMPLIANCE_RESTRICTED", "message": "Restricted"}, "futureField": {"kept": True}},
        ],
        "billing": {"creditsCharged": 0, "resultsReturned": 0},
    }
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    result = await lusha.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == data


@pytest.mark.parametrize("missing", ["requestId", "expiresAt"])
async def test_job_schema_requires_correlation_and_expiry(mock_context, missing):
    data = {
        "jobId": "wf_example",
        "status": "complete",
        "requestId": "request-example",
        "expiresAt": "2026-11-17T01:00:00Z",
        "contacts": [],
        "creditsCharged": 0,
    }
    del data[missing]
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    result = await lusha.execute_action("get_contact_enrichment_job", {"job_id": "wf_example"}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR
