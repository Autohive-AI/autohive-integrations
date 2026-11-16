from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from jobadder.jobadder import jobadder
from jobadder.tests import test_jobadder_integration as live_tests


pytestmark = pytest.mark.unit
BASE = "https://au-api.jobadder.com/v2"


def response(data=None, status=200):
    return FetchResponse(status=status, headers={}, data=data)


# Provider-shaped fixtures distinguish invoices, detail objects and list envelopes.
ACTION_CASES = [
    ("create_job", {"job_title": "Engineer"}, "POST", "/jobs", {"jobId": 11}, {"job": {"jobId": 11}}),
    (
        "update_job",
        {"job_id": 11, "job_title": "Engineer"},
        "PUT",
        "/jobs/11",
        None,
        {"updated": True, "job_id": 11},
    ),
    (
        "set_job_status",
        {"job_id": 11, "status_id": 3},
        "PUT",
        "/jobs/11/status",
        None,
        {"updated": True, "job_id": 11, "status_id": 3},
    ),
    (
        "submit_candidate_to_evergreen_job",
        {"job_id": 11, "first_name": "Alex", "last_name": "Lee", "email": "alex@example.com"},
        "POST",
        "/jobs/11/applications/submit",
        {"applicationId": 31},
        {"application": {"applicationId": 31}},
    ),
    (
        "list_job_invoices",
        {"job_id": 11},
        "GET",
        "/jobs/11/invoices",
        {"job": {"jobId": 11}, "invoices": [{"invoiceId": 8}]},
        {"job": {"jobId": 11}, "invoices": [{"invoiceId": 8}]},
    ),
    (
        "get_job_invoice",
        {"job_id": 11, "invoice_id": 8},
        "GET",
        "/jobs/11/invoices/8",
        {"job": {"jobId": 11}, "invoice": {"invoiceId": 8}, "links": {"self": "invoice-url"}},
        {"invoice": {"job": {"jobId": 11}, "invoice": {"invoiceId": 8}, "links": {"self": "invoice-url"}}},
    ),
    (
        "get_job_rate_card",
        {"job_id": 11},
        "GET",
        "/jobs/11/ratecard",
        {"jobOrderId": 11, "rateCard": "101"},
        {"rate_card": {"jobOrderId": 11, "rateCard": "101"}},
    ),
    (
        "add_job_rate_card",
        {"job_id": 11, "rate_card_id": 101},
        "POST",
        "/jobs/11/ratecard/101",
        {"jobOrderId": 11, "rateCard": "101"},
        {"rate_card": {"jobOrderId": 11, "rateCard": "101"}},
    ),
    (
        "update_job_rate_card",
        {"job_id": 11, "rate_card_id": 101},
        "PUT",
        "/jobs/11/ratecard/101",
        {"jobOrderId": 11, "rateCard": "101"},
        {"rate_card": {"jobOrderId": 11, "rateCard": "101"}},
    ),
    ("remove_job_rate_card", {"job_id": 11}, "DELETE", "/jobs/11/ratecard", None, {"removed": True, "job_id": 11}),
    (
        "create_job_activity",
        {"job_id": 11, "activity_setting_id": 2},
        "POST",
        "/jobs/11/activities",
        {"activityId": 7, "jobId": 11},
        {"activity": {"activityId": 7, "jobId": 11}},
    ),
    (
        "get_job_activity",
        {"job_id": 11, "activity_id": 7},
        "GET",
        "/jobs/11/activities/7",
        {"activityId": 7, "details": {"textAnswers": []}},
        {"activity": {"activityId": 7, "details": {"textAnswers": []}}},
    ),
    (
        "get_job_activity_setting",
        {"setting_id": 2},
        "GET",
        "/jobs/activitysettings/2",
        {"settingId": 2, "questions": []},
        {"activity_setting": {"settingId": 2, "questions": []}},
    ),
    (
        "create_job_task",
        {"job_id": 11, "title": "Call hiring manager", "assignee_user_ids": [4]},
        "POST",
        "/jobs/11/usertasks",
        {"taskId": 9, "jobId": 11},
        {"task": {"taskId": 9, "jobId": 11}},
    ),
    (
        "get_job_task",
        {"job_id": 11, "task_id": 9},
        "GET",
        "/jobs/11/usertasks/9",
        {"taskId": 9, "complete": False},
        {"task": {"taskId": 9, "complete": False}},
    ),
    (
        "get_job_custom_field",
        {"field_id": 2},
        "GET",
        "/jobs/fields/custom/2",
        {"fieldId": 2, "name": "Region", "type": "List", "values": ["North", "South"]},
        {"custom_field": {"fieldId": 2, "name": "Region", "type": "List", "values": ["North", "South"]}},
    ),
]
LIST_CASES = [
    ("list_job_sources", "/jobs/lists/source", "sources"),
    ("search_job_activities", "/jobs/activities", "activities"),
    ("list_job_activity_settings", "/jobs/activitysettings", "activity_settings"),
    ("list_job_custom_fields", "/jobs/fields/custom", "custom_fields"),
    ("list_deleted_jobs", "/jobs/deleted", "jobs"),
]
LIST_INPUTS = {"search_job_activities": {"created_at_from": "2026-11-01T00:00:00Z"}}


@pytest.mark.parametrize("action,inputs,method,path,payload,expected", ACTION_CASES)
async def test_action_request_and_provider_response(mock_context, action, inputs, method, path, payload, expected):
    mock_context.fetch.return_value = response(payload, 204 if action == "remove_job_rate_card" else 200)
    result = await jobadder.execute_action(action, inputs, mock_context)

    assert result.type == ResultType.ACTION
    assert result.result.data == expected
    mock_context.fetch.assert_awaited_once()
    assert mock_context.fetch.call_args.args == (BASE + path,)
    assert mock_context.fetch.call_args.kwargs["method"] == method
    if "rate_card" in action:
        # Assignment IDs go in the path; the provider does not accept a JSON body.
        assert mock_context.fetch.call_args.kwargs == {"method": method}


@pytest.mark.parametrize("action,path,key", LIST_CASES)
async def test_list_response_and_supported_parameters(mock_context, action, path, key):
    mock_context.fetch.return_value = response({"items": [{"name": "Example"}]})
    result = await jobadder.execute_action(action, LIST_INPUTS.get(action, {}), mock_context)

    assert result.type == ResultType.ACTION
    assert result.result.data == {key: [{"name": "Example"}], "total_count": 1, "links": {}}
    expected = {"method": "GET"}
    if action == "search_job_activities":
        expected["params"] = {"offset": 0, "limit": 100}
        path += "?createdAt=%3E2026-11-01T00%3A00%3A00Z"
    mock_context.fetch.assert_awaited_once_with(BASE + path, **expected)


ALL_ACTION_INPUTS = [(case[0], case[1]) for case in ACTION_CASES] + [
    (case[0], LIST_INPUTS.get(case[0], {})) for case in LIST_CASES
]


@pytest.mark.parametrize("action,inputs", ALL_ACTION_INPUTS)
async def test_provider_errors_are_returned(mock_context, action, inputs):
    mock_context.fetch.side_effect = HTTPError(403, "JobAdder denied this operation")
    result = await jobadder.execute_action(action, inputs, mock_context)

    assert result.type == ResultType.ACTION_ERROR
    assert "JobAdder denied this operation" in result.result.message


@pytest.mark.parametrize("action,inputs", ALL_ACTION_INPUTS)
async def test_missing_tenant_prevents_requests(mock_context, action, inputs):
    mock_context.metadata = {}
    result = await jobadder.execute_action(action, inputs, mock_context)

    assert result.type == ResultType.ACTION_ERROR
    assert "reconnect" in result.result.message.lower()
    mock_context.fetch.assert_not_awaited()


JOB_FIELDS = {
    "job_title": "Engineer",
    "company_id": 5,
    "contact_id": 6,
    "job_description": "Develop software",
    "status_id": 3,
    "user_favourite": False,
    "category": {"categoryId": 10, "subCategoryId": None},
    "location": {"locationId": 12, "areaId": 13},
    "workplace_address_id": "3e9ffaf1-ee5d-48c3-9378-5f88d8e03401",
    "start": {"immediate": False, "date": "2026-12-01"},
    "duration": {"period": 2},
    "work_type_id": 14,
    "salary": {"rateLow": 0, "rateHigh": None, "currency": "NZD"},
    "fee": {"rate": 0, "estimatedTotal": 0},
    "number_of_jobs": 0,
    "source": "Autohive",
    "custom_fields": [{"fieldId": 1, "value": "North"}],
    "skill_tags": {"matchAll": False, "tags": ["Python"]},
    "owner_user_id": 4,
    "recruiter_user_ids": [],
    "workflow_id": None,
    "work_shift": {},
    "end_date": None,
}
JOB_BODY = {
    "jobTitle": "Engineer",
    "companyId": 5,
    "contactId": 6,
    "jobDescription": "Develop software",
    "statusId": 3,
    "userFavourite": False,
    "category": {"categoryId": 10, "subCategoryId": None},
    "location": {"locationId": 12, "areaId": 13},
    "workplaceAddressId": "3e9ffaf1-ee5d-48c3-9378-5f88d8e03401",
    "start": {"immediate": False, "date": "2026-12-01"},
    "duration": {"period": 2},
    "workTypeId": 14,
    "salary": {"rateLow": 0, "rateHigh": None, "currency": "NZD"},
    "fee": {"rate": 0, "estimatedTotal": 0},
    "numberOfJobs": 0,
    "source": "Autohive",
    "custom": [{"fieldId": 1, "value": "North"}],
    "skillTags": {"matchAll": False, "tags": ["Python"]},
    "ownerUserId": 4,
    "recruiterUserId": [],
    "workflowId": None,
    "workShift": {},
    "endDate": None,
}


@pytest.mark.parametrize("action,method,path", [("create_job", "POST", "/jobs"), ("update_job", "PUT", "/jobs/11")])
async def test_job_fields_preserve_nested_data_false_zero_and_null(mock_context, action, method, path):
    mock_context.fetch.return_value = response({"jobId": 11})
    inputs = dict(JOB_FIELDS)
    if action == "update_job":
        inputs["job_id"] = 11
    result = await jobadder.execute_action(action, inputs, mock_context)

    assert result.type == ResultType.ACTION
    mock_context.fetch.assert_awaited_once_with(
        BASE + path, method=method, headers={"Content-Type": "application/json"}, json=JOB_BODY
    )


@pytest.mark.parametrize("action,inputs", [("create_job", {}), ("update_job", {"job_id": 11})])
async def test_job_title_required_before_request(mock_context, action, inputs):
    result = await jobadder.execute_action(action, inputs, mock_context)

    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()


async def test_job_update_only_sends_supplied_fields(mock_context):
    mock_context.fetch.return_value = response()
    await jobadder.execute_action(
        "update_job", {"job_id": 11, "job_title": "Engineer", "contact_id": None}, mock_context
    )

    assert mock_context.fetch.call_args.kwargs["json"] == {"jobTitle": "Engineer", "contactId": None}


@pytest.mark.parametrize("fields", [{"category": {}}, {"location": {}}, {"salary": {"rateLow": -1}}, {"start": None}])
async def test_invalid_nested_job_fields_rejected(mock_context, fields):
    result = await jobadder.execute_action("create_job", {"job_title": "Engineer", **fields}, mock_context)

    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize("http_status", [200, 202])
async def test_status_change_handles_optional_note_and_already_assigned(mock_context, http_status):
    mock_context.fetch.return_value = response(status=http_status)
    result = await jobadder.execute_action(
        "set_job_status",
        {"job_id": 11, "status_id": 3, "note_type": "General", "note_text": "Role closed"},
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert mock_context.fetch.call_args.kwargs["json"] == {
        "statusId": 3,
        "note": {"type": "General", "text": "Role closed"},
    }


async def test_status_change_omits_unsupplied_note(mock_context):
    mock_context.fetch.return_value = response(status=202)
    await jobadder.execute_action("set_job_status", {"job_id": 11, "status_id": 3}, mock_context)

    assert mock_context.fetch.call_args.kwargs["json"] == {"statusId": 3}


async def test_evergreen_submission_maps_candidate_fields(mock_context):
    mock_context.fetch.return_value = response({"applicationId": 31}, 201)
    inputs = {
        "job_id": 11,
        "first_name": "Alex",
        "last_name": "Lee",
        "email": "alex@example.com",
        "source": "Autohive",
        "salutation": None,
        "phone": "012345678",
        "mobile": None,
        "address": {},
        "social": {},
        "employment": {},
        "availability": {},
        "education": [],
        "skill_tags": ["Python"],
        "screening": {},
        "custom_fields": {},
    }
    result = await jobadder.execute_action("submit_candidate_to_evergreen_job", inputs, mock_context)

    assert result.type == ResultType.ACTION
    mock_context.fetch.assert_awaited_once_with(
        BASE + "/jobs/11/applications/submit",
        method="POST",
        headers={"Content-Type": "application/json"},
        json={
            "firstName": "Alex",
            "lastName": "Lee",
            "email": "alex@example.com",
            "source": "Autohive",
            "salutation": None,
            "phone": "012345678",
            "mobile": None,
            "address": {},
            "social": {},
            "employment": {},
            "availability": {},
            "education": [],
            "skillTags": ["Python"],
            "screening": {},
            "custom": {},
        },
    )


@pytest.mark.parametrize("missing", ["first_name", "last_name", "email"])
async def test_evergreen_submission_requires_candidate_identity(mock_context, missing):
    inputs = {"job_id": 11, "first_name": "Alex", "last_name": "Lee", "email": "alex@example.com"}
    inputs.pop(missing)
    result = await jobadder.execute_action("submit_candidate_to_evergreen_job", inputs, mock_context)

    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize("invoices", [[], None])
async def test_empty_invoices_preserve_job_context(mock_context, invoices):
    mock_context.fetch.return_value = response({"job": {"jobId": 11}, "invoices": invoices})
    result = await jobadder.execute_action("list_job_invoices", {"job_id": 11}, mock_context)

    assert result.result.data == {"job": {"jobId": 11}, "invoices": []}


@pytest.mark.parametrize("action,path,key", LIST_CASES)
async def test_empty_list_results(mock_context, action, path, key):
    mock_context.fetch.return_value = response({"items": None})
    result = await jobadder.execute_action(action, LIST_INPUTS.get(action, {}), mock_context)

    assert result.result.data == {key: [], "total_count": 0, "links": {}}


async def test_source_name_filter(mock_context):
    mock_context.fetch.return_value = response({"items": [{"name": "Referral"}]})
    await jobadder.execute_action("list_job_sources", {"name": "Referral"}, mock_context)

    mock_context.fetch.assert_awaited_once_with(BASE + "/jobs/lists/source", method="GET", params={"name": "Referral"})


async def test_structured_activity_answer_payload(mock_context):
    mock_context.fetch.return_value = response({"activityId": 7}, 201)
    answers = {
        "textAnswers": [{"questionId": 1, "text": "Discussed role"}],
        "listValueAnswers": [{"questionId": 2, "values": ["Yes"]}],
        "dateRangeValueAnswers": [
            {"questionId": 3, "startDate": "2026-11-16T00:00:00Z", "endDate": "2026-11-17T00:00:00Z"}
        ],
        "ratingValueAnswers": [{"questionId": 4, "rating": 0}],
    }
    result = await jobadder.execute_action(
        "create_job_activity",
        {"job_id": 11, "activity_setting_id": 2, "status_id": None, "answers": answers},
        mock_context,
    )

    assert result.type == ResultType.ACTION
    assert mock_context.fetch.call_args.kwargs["json"] == {"activitySettingId": 2, "statusId": None, "answers": answers}


async def test_activity_search_encodes_both_date_boundaries_and_false(mock_context):
    mock_context.fetch.return_value = response({"items": [], "totalCount": 45, "links": {"next": "next-page"}})
    result = await jobadder.execute_action(
        "search_job_activities",
        {
            "created_at_from": "2026-11-01T00:00:00Z",
            "created_at_to": "2026-11-15T23:59:59Z",
            "updated_at_from": "2026-11-02T00:00:00Z",
            "updated_at_to": "2026-11-16T23:59:59Z",
            "include_details": False,
            "offset": 5,
            "limit": 0,
        },
        mock_context,
    )

    call = mock_context.fetch.call_args
    assert urlparse(call.args[0]).path == "/v2/jobs/activities"
    assert parse_qs(urlparse(call.args[0]).query) == {
        "createdAt": [">2026-11-01T00:00:00Z", "<2026-11-15T23:59:59Z"],
        "updatedAt": [">2026-11-02T00:00:00Z", "<2026-11-16T23:59:59Z"],
    }
    assert call.kwargs == {"method": "GET", "params": {"offset": 5, "limit": 0, "includeDetails": "false"}}
    assert result.result.data == {"activities": [], "total_count": 45, "links": {"next": "next-page"}}


@pytest.mark.parametrize(
    "inputs,expected_type",
    [
        ({}, ResultType.ACTION_ERROR),
        ({"limit": 2}, ResultType.ACTION_ERROR),
        ({"created_at_from": ""}, ResultType.VALIDATION_ERROR),
        ({"updated_at_to": ""}, ResultType.VALIDATION_ERROR),
    ],
)
async def test_activity_search_requires_nonempty_date_boundary(mock_context, inputs, expected_type):
    result = await jobadder.execute_action("search_job_activities", inputs, mock_context)

    assert result.type == expected_type
    if expected_type == ResultType.ACTION_ERROR:
        assert "JobAdder requires a CreatedAt or UpdatedAt filter" in result.result.message
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize(
    "field,query_key,prefix",
    [
        ("created_at_from", "createdAt", ">"),
        ("created_at_to", "createdAt", "<"),
        ("updated_at_from", "updatedAt", ">"),
        ("updated_at_to", "updatedAt", "<"),
    ],
)
async def test_activity_search_accepts_each_date_boundary(mock_context, field, query_key, prefix):
    mock_context.fetch.return_value = response({"items": []})
    date = "2026-11-01T00:00:00Z"
    result = await jobadder.execute_action("search_job_activities", {field: date}, mock_context)

    assert result.type == ResultType.ACTION
    assert parse_qs(urlparse(mock_context.fetch.call_args.args[0]).query) == {query_key: [prefix + date]}


async def test_live_activity_search_supplies_recent_creation_boundary(mock_context):
    mock_context.fetch.return_value = response({"items": [], "totalCount": 0})
    await live_tests.TestAdditionalJobReads().test_search_job_activities(mock_context)

    call = mock_context.fetch.call_args
    query = parse_qs(urlparse(call.args[0]).query)
    assert query["createdAt"][0].startswith(">")
    boundary = datetime.fromisoformat(query["createdAt"][0][1:])
    now = datetime.now(timezone.utc)
    assert now - timedelta(days=31) < boundary < now - timedelta(days=29)
    assert call.kwargs["params"] == {"offset": 0, "limit": 2, "includeDetails": "true"}


@pytest.mark.parametrize("method_name", ["test_list_job_invoices", "test_get_job_invoice"])
async def test_live_invoice_tests_use_dedicated_job_and_do_not_hide_404(mock_context, method_name):
    mock_context.fetch.side_effect = HTTPError(404, "Requested job's invoices were not found")
    method = getattr(live_tests.TestAdditionalJobReads(), method_name)

    with pytest.raises(AssertionError):
        await method(mock_context, invoice_job_id=99)

    mock_context.fetch.assert_awaited_once_with(BASE + "/jobs/99/invoices", method="GET")


def test_live_invoice_fixture_skips_when_not_configured():
    with pytest.raises(pytest.skip.Exception, match="JOBADDER_TEST_INVOICE_JOB_ID not set"):
        live_tests.invoice_job_id.__wrapped__(lambda name: None)


def test_live_invoice_fixture_uses_its_own_variable():
    def credentials(name):
        assert name == "JOBADDER_TEST_INVOICE_JOB_ID"
        return "99"

    assert live_tests.invoice_job_id.__wrapped__(credentials) == 99


async def test_task_maps_assignees_dates_and_linked_records(mock_context):
    mock_context.fetch.return_value = response({"taskId": 9}, 201)
    result = await jobadder.execute_action(
        "create_job_task",
        {
            "job_id": 11,
            "title": "Call hiring manager",
            "assignee_user_ids": [4, 5],
            "start_at": "2026-11-17T00:00:00Z",
            "end_at": "2026-11-17T01:00:00Z",
            "all_day": False,
            "priority": 0,
            "candidate_ids": [21],
            "job_ids": [11],
            "placement_ids": [],
            "company_ids": [6],
            "contact_ids": [8],
            "application_ids": [31],
        },
        mock_context,
    )

    assert result.type == ResultType.ACTION
    mock_context.fetch.assert_awaited_once_with(
        BASE + "/jobs/11/usertasks",
        method="POST",
        headers={"Content-Type": "application/json"},
        json={
            "title": "Call hiring manager",
            "assignees": [4, 5],
            "startAt": "2026-11-17T00:00:00Z",
            "endAt": "2026-11-17T01:00:00Z",
            "allDay": False,
            "priority": 0,
            "candidates": [21],
            "jobs": [11],
            "placements": [],
            "companies": [6],
            "contacts": [8],
            "applications": [31],
        },
    )


@pytest.mark.parametrize("fields", [{"assignee_user_ids": []}, {"priority": 4}, {"title": ""}])
async def test_task_invalid_inputs_rejected(mock_context, fields):
    result = await jobadder.execute_action(
        "create_job_task", {"job_id": 11, "title": "Follow up", "assignee_user_ids": [4], **fields}, mock_context
    )

    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()
