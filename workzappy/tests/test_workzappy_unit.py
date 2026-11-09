from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from autohive_integrations_sdk import ActionError, FetchResponse

from .context import BASE_URL, CreateTask

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
