from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, HTTPError, ResultType
from procore.procore import api_request, object_result, page_result, procore

pytestmark = pytest.mark.unit


@pytest.fixture
def context():
    ctx = MagicMock()
    ctx.auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "unit-token"}}  # nosec B105
    ctx.fetch = AsyncMock()
    return ctx


def response(data, headers=None):
    return FetchResponse(status=200, headers=headers or {}, data=data)


PROJECT = {"company_id": 10, "project_id": 20}
RFI = {"subject": "Beam detail", "question": {"body": "Confirm size?"}, "rfi_manager_id": 30}
CASES = [
    ("list_companies", {}, "/rest/v1.0/companies", "GET", [{"id": 10, "name": "Builder"}]),
    ("list_projects", {"company_id": 10}, "/rest/v1.1/projects", "GET", [{"id": 20, "name": "Office"}]),
    ("get_project", PROJECT, "/rest/v1.0/projects/20", "GET", {"id": 20, "name": "Office"}),
    ("create_project", {"company_id": 10, "project": {"name": "Office"}}, "/rest/v1.0/projects", "POST", {"id": 20}),
    (
        "update_project",
        {**PROJECT, "project": {"active": False}},
        "/rest/v1.0/projects/20",
        "PATCH",
        {"id": 20, "active": False},
    ),
    ("list_rfis", PROJECT, "/rest/v1.0/projects/20/rfis", "GET", [{"id": 40, "subject": "Beam detail"}]),
    (
        "get_rfi",
        {**PROJECT, "rfi_id": 40},
        "/rest/v1.0/projects/20/rfis/40",
        "GET",
        {"id": 40, "subject": "Beam detail"},
    ),
    ("create_rfi", {**PROJECT, "rfi": RFI}, "/rest/v1.0/projects/20/rfis", "POST", {"id": 40, "status": "draft"}),
    (
        "update_rfi",
        {**PROJECT, "rfi_id": 40, "rfi": {"subject": "Updated"}},
        "/rest/v1.0/projects/20/rfis/40",
        "PATCH",
        {"id": 40},
    ),
    ("recycle_rfi", {**PROJECT, "rfi_id": 40}, "/rest/v1.0/projects/20/rfis/40/recycle", "PATCH", None),
    ("restore_rfi", {**PROJECT, "rfi_id": 40}, "/rest/v1.0/projects/20/rfis/40/retrieve", "PATCH", None),
    (
        "list_submittals",
        PROJECT,
        "/rest/v1.1/projects/20/submittals",
        "GET",
        [{"id": 50, "number": "1", "title": "Steel"}],
    ),
    (
        "get_submittal",
        {**PROJECT, "submittal_id": 50},
        "/rest/v1.1/projects/20/submittals/50",
        "GET",
        {"id": 50, "number": "1"},
    ),
    (
        "create_submittal",
        {**PROJECT, "submittal": {"number": "1", "title": "Steel"}},
        "/rest/v1.1/projects/20/submittals",
        "POST",
        {"id": 50},
    ),
    (
        "update_submittal",
        {**PROJECT, "submittal_id": 50, "submittal": {"number": "1", "title": "Steel revised"}},
        "/rest/v1.1/projects/20/submittals/50",
        "PATCH",
        {"id": 50},
    ),
    ("delete_submittal", {**PROJECT, "submittal_id": 50}, "/rest/v1.1/projects/20/submittals/50", "DELETE", None),
    (
        "list_submittal_revisions",
        {**PROJECT, "submittal_id": 50},
        "/rest/v1.1/projects/20/submittals/50/revisions",
        "GET",
        [{"id": 51, "revision": "2"}],
    ),
    (
        "get_submittal_workflow",
        {**PROJECT, "submittal_id": 50},
        "/rest/v1.1/projects/20/submittals/50/workflow_data",
        "GET",
        {"steps": [], "approvers": []},
    ),
    ("list_project_users", PROJECT, "/rest/v1.0/projects/20/users", "GET", [{"id": 30, "name": "Manager"}]),
    (
        "get_project_user",
        {**PROJECT, "user_id": 30},
        "/rest/v1.0/projects/20/users/30",
        "GET",
        {"id": 30, "name": "Manager"},
    ),
    ("list_project_vendors", PROJECT, "/rest/v1.1/projects/20/vendors", "GET", [{"id": 60, "name": "Steel Co"}]),
    ("get_project_vendor", {**PROJECT, "vendor_id": 60}, "/rest/v1.1/projects/20/vendors/60", "GET", {"id": 60}),
    ("list_locations", PROJECT, "/rest/v1.0/projects/20/locations", "GET", [{"id": 70, "name": "Ground Floor"}]),
    (
        "list_submittal_types",
        {"company_id": 10},
        "/rest/v1.0/companies/10/submittal_types",
        "GET",
        [{"id": 1, "name": "Shop Drawing"}],
    ),
    (
        "list_submittal_statuses",
        {"company_id": 10},
        "/rest/v1.0/companies/10/submittal_statuses",
        "GET",
        [{"id": 1, "name": "Open"}],
    ),
    ("get_document_root", PROJECT, "/rest/v1.0/folders", "GET", {"id": 80, "folders": [], "files": [{"id": 90}]}),
    ("get_folder", {**PROJECT, "folder_id": 80}, "/rest/v1.0/folders/80", "GET", {"id": 80, "files": []}),
    ("get_file", {**PROJECT, "file_id": 90}, "/rest/v1.0/files/90", "GET", {"id": 90, "name": "Plan.pdf"}),
    (
        "create_folder",
        {**PROJECT, "folder": {"name": "Plans", "parent_id": 80}},
        "/rest/v1.0/folders",
        "POST",
        {"id": 81, "name": "Plans"},
    ),
]


@pytest.mark.parametrize("name,inputs,path,method,data", CASES)
async def test_documented_action_requests(context, name, inputs, path, method, data):
    context.fetch.return_value = response(data)
    result = await procore.execute_action(name, inputs, context)
    assert result.type == ResultType.ACTION
    call = context.fetch.call_args
    assert call.args == ("https://api.procore.com" + path,)
    assert call.kwargs["method"] == method
    assert call.kwargs["headers"]["Accept"] == "application/json"
    assert "Authorization" not in call.kwargs["headers"]  # SDK owns OAuth injection.
    if "company_id" in inputs:
        assert call.kwargs["headers"]["Procore-Company-Id"] == "10"
    expected_params = {
        "list_projects": {"page": 1, "per_page": 100, "company_id": 10},
        "get_project": {"company_id": 10},
        "list_rfis": {"page": 1, "per_page": 100},
        "list_submittals": {"page": 1, "per_page": 100},
        "list_project_users": {"page": 1, "per_page": 100},
        "list_project_vendors": {"page": 1, "per_page": 100},
        "list_locations": {"page": 1, "per_page": 100},
        "list_submittal_statuses": {"page": 1, "per_page": 100},
        "get_document_root": {"project_id": 20},
        "get_folder": {"project_id": 20},
        "get_file": {"project_id": 20},
        "create_folder": {"project_id": 20},
        "create_submittal": {},
        "update_submittal": {},
    }.get(name)
    assert call.kwargs["params"] == expected_params
    if isinstance(data, list):
        assert result.result.data["items"] == data
    else:
        assert result.result.data["result"] == (data or {})
    for field in ("project", "rfi", "submittal", "folder"):
        if field in inputs:
            body = call.kwargs["json"]
            expected = {**inputs[field]}
            if name == "create_rfi":
                expected.setdefault("draft", True)
            assert body[field] == expected
            if field == "project":
                assert body["company_id"] == 10


async def test_sandbox_and_filter_mapping(context):
    context.fetch.return_value = response([], {"Total": "0"})
    result = await procore.execute_action(
        "list_projects",
        {"company_id": 10, "environment": "sandbox", "page": 2, "per_page": 25, "status": "Active", "name": "Office"},
        context,
    )
    assert result.type == ResultType.ACTION
    assert context.fetch.call_args.args == ("https://sandbox.procore.com/rest/v1.1/projects",)
    assert context.fetch.call_args.kwargs["params"] == {
        "company_id": 10,
        "page": 2,
        "per_page": 25,
        "filters[by_status]": "Active",
        "filters[name]": "Office",
    }


async def test_create_rfi_explicit_issue_and_references(context):
    context.fetch.return_value = response({"id": 40})
    rfi = {
        **RFI,
        "draft": False,
        "assignee_ids": [31],
        "due_date": "2026-11-01",
        "question": {"body": "Confirm?", "prostore_file_ids": [9], "upload_ids": ["existing-upload"]},
    }
    result = await procore.execute_action("create_rfi", {**PROJECT, "rfi": rfi}, context)
    assert result.type == ResultType.ACTION
    assert context.fetch.call_args.kwargs["json"] == {"rfi": rfi}
    assert rfi["draft"] is False


async def test_notifications_and_false_values_preserved(context):
    context.fetch.return_value = response({"id": 50})
    result = await procore.execute_action(
        "update_submittal",
        {**PROJECT, "submittal_id": 50, "send_emails": False, "submittal": {"number": "1", "private": False}},
        context,
    )
    assert result.type == ResultType.ACTION
    assert context.fetch.call_args.kwargs["params"] == {"send_emails": False}
    assert context.fetch.call_args.kwargs["json"] == {"submittal": {"number": "1", "private": False}}


def test_link_pagination_case_insensitive_headers():
    data = [{"id": 40}]
    r = response(
        data,
        {
            "tOtAl": "100",
            "LiNk": (
                '<https://api.procore.com/rest/v1.0/projects/20/rfis?page=2&per_page=25>; rel="ne'
                'xt", <https://api.procore.com/rest/v1.0/projects/20/rfis?page=4>; rel="last"'
            ),
        },
    )
    assert page_result(r, page=1, per_page=25) == {"items": data, "total": 100, "next_page": 2}
    assert (
        page_result(response([], {"Link": '<https://api.procore.com/x?page=1>; rel="prev"'}), page=2)["next_page"]
        is None
    )


def test_total_pagination_and_empty_page():
    assert page_result(response([{"id": 1}], {"Total": "51"}), page=1, per_page=25)["next_page"] == 2
    assert page_result(response([], {"Total": "51"}), page=3, per_page=25)["next_page"] is None
    assert page_result(response([])) == {"items": [], "next_page": None, "total": None}


@pytest.mark.parametrize(
    "link",
    [
        '<https://other.example/?page=1>; rel="next"',
        '<https://api.procore.com/x>; rel="next"',
        '<https://api.procore.com/x?page=no>; rel="next"',
    ],
)
def test_invalid_next_page(link):
    with pytest.raises(ValueError):
        page_result(response([], {"Link": link}), page=1)


@pytest.mark.parametrize("data", [None, {"items": []}, "bad", ["bad"]])
def test_invalid_list_response(data):
    with pytest.raises(ValueError):
        page_result(response(data))


@pytest.mark.parametrize("data", [[], "bad", 3])
def test_invalid_object_response(data):
    with pytest.raises(ValueError):
        object_result(data)


@pytest.mark.parametrize(
    "name,inputs",
    [
        ("list_projects", {}),
        ("get_rfi", {**PROJECT, "rfi_id": "../40"}),
        ("list_rfis", {**PROJECT, "per_page": 101}),
        ("get_project", {**PROJECT, "project_id": 0}),
        ("create_rfi", {**PROJECT, "rfi": {"subject": "Missing question"}}),
        ("create_rfi", {**PROJECT, "rfi": {**RFI, "question": {"body": "Q", "attachments": ["fake.pdf"]}}}),
        ("update_project", {**PROJECT, "project": {}}),
        ("create_submittal", {**PROJECT, "submittal": {"title": "Missing number"}}),
        ("get_project", {**PROJECT, "environment": "https://other.example"}),
    ],
)
async def test_invalid_inputs_do_not_fetch(context, name, inputs):
    result = await procore.execute_action(name, inputs, context)
    assert result.type == ResultType.VALIDATION_ERROR
    context.fetch.assert_not_called()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 429, 500])
async def test_wrapper_propagates_http_errors_without_repeating_fetch(context, status):
    context.fetch.side_effect = HTTPError(status, "Provider rejected request")
    with pytest.raises(HTTPError):
        await api_request(
            context, "production", "/rest/v1.0/projects/20", method="POST", payload={"project": {"name": "Office"}}
        )
    assert context.fetch.await_count == 1


async def test_reject_environment_direct(context):
    with pytest.raises(ValueError):
        await api_request(context, "https://other.example", "/rest/v1.0/companies")
    context.fetch.assert_not_called()


@pytest.mark.parametrize("name", [case[0] for case in CASES])
async def test_each_action_uses_explicit_sandbox_host(context, name):
    _, inputs, path, _, data = next(case for case in CASES if case[0] == name)
    context.fetch.return_value = response(data)
    result = await procore.execute_action(name, {**inputs, "environment": "sandbox"}, context)
    assert result.type == ResultType.ACTION
    assert context.fetch.call_args.args == ("https://sandbox.procore.com" + path,)


async def test_rfi_status_and_pagination_mapping(context):
    context.fetch.return_value = response([])
    await procore.execute_action("list_rfis", {**PROJECT, "status": "open", "page": 3, "per_page": 7}, context)
    assert context.fetch.call_args.kwargs["params"] == {"page": 3, "per_page": 7, "filters[status]": "open"}


async def test_create_submittal_explicit_notification_setting(context):
    context.fetch.return_value = response({"id": 50})
    await procore.execute_action(
        "create_submittal", {**PROJECT, "submittal": {"number": "1"}, "send_emails": False}, context
    )
    assert context.fetch.call_args.kwargs["params"] == {"send_emails": False}


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 429, 500])
async def test_sdk_injects_auth_and_does_not_retry_http_rejections(monkeypatch, status):
    from autohive_integrations_sdk import ExecutionContext

    provider_response = MagicMock()
    provider_response.status = status
    provider_response.ok = False
    provider_response.headers = {"Content-Type": "application/json", "Retry-After": "1"}
    provider_response.json = AsyncMock(return_value={"errors": "Rejected test request"})
    provider_response.text = AsyncMock(return_value="Rejected test request")
    request_context = MagicMock()
    request_context.__aenter__ = AsyncMock(return_value=provider_response)
    request_context.__aexit__ = AsyncMock(return_value=False)
    request = MagicMock(return_value=request_context)
    monkeypatch.setattr("aiohttp.ClientSession.request", request)
    auth = {"auth_type": "PlatformOauth2", "credentials": {"access_token": "test-access"}}  # nosec B105
    async with ExecutionContext(auth=auth) as context:
        with pytest.raises(HTTPError) as error:
            await procore.execute_action("list_companies", {"environment": "sandbox"}, context)
    assert error.value.status == status
    request.assert_called_once()
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer test-access"
    assert request.call_args.kwargs["url"] == "https://sandbox.procore.com/rest/v1.0/companies"
