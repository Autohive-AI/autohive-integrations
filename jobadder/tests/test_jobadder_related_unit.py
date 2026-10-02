import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType
from urllib.parse import parse_qs, urlparse

from jobadder.jobadder import jobadder


pytestmark = pytest.mark.unit


def response(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def list_payload(items=None, total_count=0):
    return {
        "items": items or [],
        "totalCount": total_count,
        "links": {"self": "https://au-api.jobadder.com/v2/resource"},
    }


RELATED_ACTION_CASES = [
    (
        "list_candidate_applications",
        {"candidate_id": 21, "offset": 5, "limit": 10},
        "/candidates/21/applications",
        "applications",
        {"offset": 5, "limit": 10},
    ),
    (
        "list_candidate_active_applications",
        {"candidate_id": 21, "offset": 5, "limit": 10},
        "/candidates/21/applications/active",
        "applications",
        {"offset": 5, "limit": 10},
    ),
    ("list_candidate_placements", {"candidate_id": 21}, "/candidates/21/placements", "placements", None),
    (
        "list_candidate_approved_placements",
        {"candidate_id": 21},
        "/candidates/21/placements/approved",
        "placements",
        None,
    ),
    (
        "list_candidate_attachments",
        {"candidate_id": 21, "offset": 5, "limit": 10},
        "/candidates/21/attachments",
        "attachments",
        {"offset": 5, "limit": 10},
    ),
    ("list_candidate_skills", {"candidate_id": 21}, "/candidates/21/skills", "skills", None),
    (
        "get_candidate_availability",
        {"candidate_id": 21},
        "/candidates/21/availability",
        "availability",
        "no_params",
    ),
    (
        "list_candidate_notes",
        {"candidate_id": 21, "offset": 5, "limit": 10},
        "/candidates/21/notes",
        "notes",
        {"sort": "-createdAt", "offset": 5, "limit": 10},
    ),
    (
        "list_job_applications",
        {"job_id": 11, "offset": 5, "limit": 10},
        "/jobs/11/applications",
        "applications",
        {"offset": 5, "limit": 10},
    ),
    (
        "list_job_active_applications",
        {"job_id": 11, "offset": 5, "limit": 10},
        "/jobs/11/applications/active",
        "applications",
        {"offset": 5, "limit": 10},
    ),
    ("list_job_placements", {"job_id": 11}, "/jobs/11/placements", "placements", None),
    (
        "list_job_approved_placements",
        {"job_id": 11},
        "/jobs/11/placements/approved",
        "placements",
        None,
    ),
    (
        "list_job_attachments",
        {"job_id": 11, "offset": 5, "limit": 10},
        "/jobs/11/attachments",
        "attachments",
        {"offset": 5, "limit": 10},
    ),
    (
        "list_job_notes",
        {"job_id": 11, "offset": 5, "limit": 10},
        "/jobs/11/notes",
        "notes",
        {"sort": "-createdAt", "offset": 5, "limit": 10},
    ),
    ("list_job_activities", {"job_id": 11}, "/jobs/11/activities", "activities", None),
    (
        "list_application_attachments",
        {"application_id": 31, "offset": 5, "limit": 10},
        "/applications/31/attachments",
        "attachments",
        {"offset": 5, "limit": 10},
    ),
    (
        "list_application_notes",
        {"application_id": 31, "offset": 5, "limit": 10},
        "/applications/31/notes",
        "notes",
        {"offset": 5, "limit": 10},
    ),
    (
        "list_application_activities",
        {"application_id": 31},
        "/applications/31/activities",
        "activities",
        None,
    ),
    (
        "list_placement_attachments",
        {"placement_id": 41, "offset": 5, "limit": 10},
        "/placements/41/attachments",
        "attachments",
        {"offset": 5, "limit": 10},
    ),
    (
        "list_placement_notes",
        {"placement_id": 41, "offset": 5, "limit": 10},
        "/placements/41/notes",
        "notes",
        {"sort": "-createdAt", "offset": 5, "limit": 10},
    ),
    (
        "list_placement_timesheets",
        {"placement_id": 41, "period_from": "2026-01-01", "period_to": "2026-01-31"},
        "/placements/41/timesheets",
        "timesheets",
        {"period": [">2026-01-01", "<2026-01-31"]},
    ),
    (
        "list_placement_activities",
        {"placement_id": 41},
        "/placements/41/activities",
        "activities",
        None,
    ),
    ("list_company_contacts", {"company_id": 51}, "/companies/51/contacts", "contacts", None),
    ("list_company_addresses", {"company_id": 51}, "/companies/51/addresses", "addresses", None),
    (
        "list_company_jobs",
        {"company_id": 51, "offset": 5, "limit": 10},
        "/companies/51/jobs",
        "jobs",
        {"offset": 5, "limit": 10},
    ),
    (
        "list_company_active_jobs",
        {"company_id": 51, "offset": 5, "limit": 10},
        "/companies/51/jobs/active",
        "jobs",
        {"offset": 5, "limit": 10},
    ),
    ("list_company_placements", {"company_id": 51}, "/companies/51/placements", "placements", None),
    (
        "list_company_approved_placements",
        {"company_id": 51},
        "/companies/51/placements/approved",
        "placements",
        None,
    ),
    (
        "list_company_attachments",
        {"company_id": 51, "offset": 5, "limit": 10},
        "/companies/51/attachments",
        "attachments",
        {"offset": 5, "limit": 10},
    ),
    (
        "list_company_notes",
        {"company_id": 51, "offset": 5, "limit": 10},
        "/companies/51/notes",
        "notes",
        {"sort": "-createdAt", "offset": 5, "limit": 10},
    ),
]


@pytest.mark.parametrize("action,inputs,path,key,expected_params", RELATED_ACTION_CASES)
@pytest.mark.asyncio
async def test_related_action_returns_data_and_maps_request(mock_context, action, inputs, path, key, expected_params):
    record = {"id": 1}
    if action == "get_candidate_availability":
        mock_context.fetch.return_value = response(record)
    else:
        mock_context.fetch.return_value = response(list_payload([record], 1))

    result = await jobadder.execute_action(action, inputs, mock_context)

    assert result.type == ResultType.ACTION
    if action == "get_candidate_availability":
        assert result.result.data[key] == record
    else:
        assert result.result.data[key] == [record]
        assert result.result.data["total_count"] == 1

    call = mock_context.fetch.call_args
    request_url = urlparse(call.args[0])
    assert f"{request_url.scheme}://{request_url.netloc}{request_url.path}" == (f"https://au-api.jobadder.com/v2{path}")
    expected_query = {"fields": ["text"]} if action.endswith("_notes") else {}
    expected_scalar_params = {}
    params_to_split = expected_params if isinstance(expected_params, dict) else {}
    for param_name, param_value in params_to_split.items():
        if isinstance(param_value, list):
            expected_query[param_name] = [str(value) for value in param_value]
        else:
            expected_scalar_params[param_name] = param_value
    assert parse_qs(request_url.query) == expected_query
    assert call.kwargs["method"] == "GET"
    if expected_params == "no_params":
        assert "params" not in call.kwargs
    elif expected_scalar_params:
        assert call.kwargs["params"] == expected_scalar_params
    else:
        assert "params" not in call.kwargs


@pytest.mark.parametrize("action,inputs,_path,_key,_expected_params", RELATED_ACTION_CASES)
@pytest.mark.asyncio
async def test_related_action_returns_action_error(mock_context, action, inputs, _path, _key, _expected_params):
    mock_context.fetch.side_effect = Exception("related resource unavailable")

    result = await jobadder.execute_action(action, inputs, mock_context)

    assert result.type == ResultType.ACTION_ERROR
    assert "related resource unavailable" in result.result.message


@pytest.mark.parametrize("action,inputs,_path,_key,_expected_params", RELATED_ACTION_CASES)
@pytest.mark.asyncio
async def test_related_action_requires_parent_id(mock_context, action, inputs, _path, _key, _expected_params):
    missing_id_inputs = {
        key: value
        for key, value in inputs.items()
        if key not in {"candidate_id", "job_id", "application_id", "placement_id", "company_id"}
    }

    result = await jobadder.execute_action(action, missing_id_inputs, mock_context)

    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_paginated_list_uses_item_count_when_api_omits_total(mock_context):
    mock_context.fetch.return_value = response({"items": [{"categoryId": 1}, {"categoryId": 2}]})

    result = await jobadder.execute_action("list_candidate_skills", {"candidate_id": 21}, mock_context)

    assert result.result.data["total_count"] == 2
