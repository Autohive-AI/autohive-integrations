from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from autohive_integrations_sdk import ActionError, FetchResponse

from .. import workzappy as actions
from ..workzappy import BASE_URL, CreateTask

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

INPUTS = {"project_id": 1, "task_type_id": 2, "summary": "Send proposal"}


def response(data):
    return FetchResponse(status=200, headers={}, data=data)


@pytest.fixture
def ctx():
    dummy_credential = "mock-value"
    return SimpleNamespace(
        auth={"credentials": {"client_id": "client", "secret_key": dummy_credential}},
        fetch=AsyncMock(),
    )


@pytest.mark.parametrize("extra", [{}, {"description": "By Friday"}])
async def test_create_task(ctx, extra):
    ctx.fetch.side_effect = [
        response({"code": "0", "data": {"accessToken": "token"}}),
        response({"code": "0", "data": {"id": 42}}),
    ]
    result = await CreateTask().execute({**INPUTS, **extra}, ctx)
    assert result.data == {"task_id": 42}
    assert ctx.fetch.await_args_list == [
        call(
            f"{BASE_URL}/authorize/access-permanent-token",
            method="POST",
            json={"clientId": "client", "secretKey": ctx.auth["credentials"]["secret_key"]},
        ),
        call(
            f"{BASE_URL}/issue/add",
            method="POST",
            headers={"accessToken": "token"},
            json={"projectId": 1, "issueTypeId": 2, "data": {"summary": "Send proposal", **extra}},
            retry_count=1_000,
        ),
    ]


@pytest.mark.parametrize("payload", [{"code": "denied"}, {"code": "0", "data": {}}, "<html>"])
async def test_auth_failure_prevents_task_creation(ctx, payload):
    ctx.fetch.return_value = response(payload)
    result = await CreateTask().execute(INPUTS, ctx)
    assert isinstance(result, ActionError)
    assert "authentication failed" in result.message
    assert ctx.fetch.await_count == 1


@pytest.mark.parametrize(
    "failure",
    [response({"code": "rejected"}), response({"code": "0", "data": {}}), TimeoutError()],
)
async def test_unconfirmed_creation_returns_action_error(ctx, failure):
    ctx.fetch.side_effect = [response({"code": "0", "data": {"accessToken": "token"}}), failure]
    result = await CreateTask().execute(INPUTS, ctx)
    assert isinstance(result, ActionError)
    assert "before retrying" in result.message
    assert ctx.fetch.await_count == 2


@pytest.mark.parametrize(
    "handler, inputs, method, path, mode, wire, output, data, write",
    [
        (actions.ListProjects, {}, "GET", "/project/list", "params", None, "projects", [{"id": 42}], False),
        (
            actions.GetProject,
            {"project_id": 2},
            "GET",
            "/project/get",
            "params",
            {"projectId": 2},
            "project",
            {"id": 42},
            False,
        ),
        (
            actions.ListProjectMembers,
            {"project_id": 2},
            "GET",
            "/user/project-user-list",
            "params",
            {"projectId": 2},
            "members",
            [{"id": 42}],
            False,
        ),
        (
            actions.ListTaskTypes,
            {"project_id": 2},
            "GET",
            "/issue/type-list",
            "params",
            {"projectId": 2},
            "task_types",
            [{"id": 42}],
            False,
        ),
        (
            actions.GetTaskScheme,
            {"project_id": 2, "task_type_id": 7},
            "GET",
            "/issue/issue-scheme",
            "params",
            {"projectId": 2, "issueTypeId": 7},
            "scheme",
            {"id": 42},
            False,
        ),
        (actions.GetTask, {"task_id": 2}, "GET", "/issue/v2/get", "params", {"id": 2}, "task", {"id": 42}, False),
        (
            actions.SearchTasks,
            {"project_id": 2, "summary": "Example", "page_number": 3, "page_size": 11},
            "POST",
            "/issue/v2/page",
            "body",
            {"projectId": 2, "summary": "Example", "pageNumber": 3, "pageSize": 11},
            "page",
            {"id": 42},
            False,
        ),
        (
            actions.UpdateTask,
            {"task_id": 2, "fields": {"summary": "Revised"}},
            "PATCH",
            "/issue/update",
            "body",
            {"id": 2, "data": {"summary": "Revised"}},
            "result",
            {"success": True},
            True,
        ),
        (
            actions.RemoveTask,
            {"task_id": 2},
            "DELETE",
            "/issue/remove",
            "body",
            {"id": 2},
            "result",
            {"success": True},
            True,
        ),
        (
            actions.ListTaskComments,
            {"task_id": 2, "page_number": 3, "page_size": 11},
            "POST",
            "/comment/page",
            "body",
            {"commentModule": "issue", "linkId": 2, "pageNumber": 3, "pageSize": 11},
            "page",
            {"id": 42},
            False,
        ),
        (
            actions.AddTaskComment,
            {"task_id": 2, "content": "Example", "parent_comment_id": 9},
            "POST",
            "/comment/add",
            "body",
            {"commentModule": "issue", "linkId": 2, "plainContent": "Example", "commentId": 9, "content": "Example"},
            "comment",
            {"id": 42},
            True,
        ),
        (
            actions.ListProjectPhases,
            {"project_id": 2},
            "POST",
            "/sprint/list-with-count",
            "body",
            {"projectId": 2},
            "phases",
            [{"id": 42}],
            False,
        ),
        (
            actions.ListProjectTags,
            {"project_id": 2},
            "POST",
            "/tag/list",
            "body",
            {"projectId": 2},
            "tags",
            [{"id": 42}],
            False,
        ),
        (
            actions.CreateProject,
            {"project_name": "Example", "template_code": "Example", "description": "Example", "leader_id": 2},
            "POST",
            "/project/add",
            "body",
            {"projectName": "Example", "templateCode": "Example", "description": "Example", "leaderId": 2},
            "project",
            {"id": 42},
            True,
        ),
        (
            actions.UpdateProject,
            {"project_id": 2, "fields": {"summary": "Revised"}},
            "PATCH",
            "/project/update",
            "body",
            {"id": 2, "data": {"summary": "Revised"}},
            "result",
            {"success": True},
            True,
        ),
    ],
)
async def test_action_contract(ctx, handler, inputs, method, path, mode, wire, output, data, write):
    ctx.fetch.side_effect = [
        response({"code": "0", "data": {"accessToken": "token"}}),
        response({"code": "0", "data": data}),
    ]
    result = await handler().execute(inputs, ctx)
    assert result.data == {output: data}
    ctx.fetch.assert_awaited_with(
        f"{BASE_URL}{path}",
        method=method,
        headers={"accessToken": "token"},
        params=wire if mode == "params" else None,
        json=wire if mode == "body" else None,
        retry_count=1_000 if write else 0,
    )


@pytest.mark.parametrize(
    "handler, inputs, payloads",
    [
        (actions.UpdateTask, {"task_id": 1, "fields": {"summary": "New"}}, [{}, {"id": 42}, {"success": 1}]),
        (actions.RemoveTask, {"task_id": 1}, [{}, {"success": False}]),
        (actions.UpdateProject, {"project_id": 1, "fields": {"pname": "New"}}, [{}, {"success": "true"}]),
        (actions.CreateProject, {"project_name": "New", "template_code": "BLANK", "leader_id": 1}, [{}, {"id": 0}]),
        (actions.AddTaskComment, {"task_id": 1, "content": "New"}, [{}, {"id": True}]),
    ],
)
async def test_write_requires_confirmation(ctx, handler, inputs, payloads):
    for payload in payloads:
        ctx.fetch.side_effect = [
            response({"code": "0", "data": {"accessToken": "token"}}),
            response({"code": "0", "data": payload}),
        ]
        result = await handler().execute(inputs, ctx)
        assert isinstance(result, ActionError)
