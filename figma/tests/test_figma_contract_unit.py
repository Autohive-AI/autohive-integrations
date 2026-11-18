"""Exercise every registered action through SDK input and output validation."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import ExecutionContext, FetchResponse, HTTPError
from autohive_integrations_sdk.integration import ResultType

from figma.figma import figma

pytestmark = pytest.mark.unit

CASES = [
    ("get_me", {}, "/me", {"id": "123", "handle": "Designer", "email": "designer@example.com"}),
    ("get_file", {"file_key": "AbC123"}, "/files/AbC123", {"name": "Design", "document": {"id": "0:0"}}),
    ("get_file_nodes", {"file_key": "AbC123", "ids": ["1:2"]}, "/files/AbC123/nodes", {"nodes": {"1:2": None}}),
    (
        "get_file_metadata",
        {"file_key": "AbC123"},
        "/files/AbC123/meta",
        {
            "file": {
                "name": "Design",
                "last_touched_at": "2026-11-18T00:00:00Z",
                "creator": {"id": "123"},
                "editorType": "figma",
            },
        },
    ),
    ("export_images", {"file_key": "AbC123", "ids": ["1:2"]}, "/images/AbC123", {"images": {"1:2": None}, "err": None}),
    ("get_image_fills", {"file_key": "AbC123"}, "/files/AbC123/images", {"meta": {"images": {}}}),
    ("list_comments", {"file_key": "AbC123"}, "/files/AbC123/comments", {"comments": []}),
    (
        "create_comment",
        {"file_key": "AbC123", "message": "Review"},
        "/files/AbC123/comments",
        {"id": "456", "message": "Review"},
    ),
    ("delete_comment", {"file_key": "AbC123", "comment_id": "456"}, "/files/AbC123/comments/456", {"deleted": True}),
    ("list_file_versions", {"file_key": "AbC123"}, "/files/AbC123/versions", {"versions": [], "pagination": {}}),
    ("list_file_components", {"file_key": "AbC123"}, "/files/AbC123/components", {"meta": {"components": []}}),
    ("list_team_components", {"team_id": "123"}, "/teams/123/components", {"meta": {"components": []}}),
    ("get_component", {"key": "abc123"}, "/components/abc123", {"meta": {"key": "abc123", "name": "Button"}}),
    (
        "list_file_component_sets",
        {"file_key": "AbC123"},
        "/files/AbC123/component_sets",
        {"meta": {"component_sets": []}},
    ),
    ("list_team_component_sets", {"team_id": "123"}, "/teams/123/component_sets", {"meta": {"component_sets": []}}),
    ("get_component_set", {"key": "abc123"}, "/component_sets/abc123", {"meta": {"key": "abc123", "name": "Buttons"}}),
    ("list_file_styles", {"file_key": "AbC123"}, "/files/AbC123/styles", {"meta": {"styles": []}}),
    ("list_team_styles", {"team_id": "123"}, "/teams/123/styles", {"meta": {"styles": []}}),
    ("get_style", {"key": "abc123"}, "/styles/abc123", {"meta": {"key": "abc123", "name": "Primary"}}),
]


def test_all_configured_actions_are_covered():
    config = json.loads(Path(__file__).parents[1].joinpath("config.json").read_text())
    assert {case[0] for case in CASES} == set(config["actions"])


async def test_sdk_sends_oauth_bearer_token():
    context = ExecutionContext(
        auth={
            "auth_type": "PlatformOauth2",
            "credentials": {"access_token": "test_figma_token"},  # nosec B105
        }
    )
    response = MagicMock(status=200, ok=True)
    response.headers = {"Content-Type": "application/json"}
    response.json = AsyncMock(return_value={"id": "123", "handle": "Designer", "email": "designer@example.com"})
    session = MagicMock()
    session.request.return_value.__aenter__ = AsyncMock(return_value=response)
    context._session = session

    result = await figma.execute_action("get_me", {}, context)

    assert result.type == ResultType.ACTION
    headers = session.request.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test_figma_token"
    assert "X-Figma-Token" not in headers


@pytest.mark.parametrize("action,inputs,path,data", CASES, ids=[case[0] for case in CASES])
async def test_action_contract(mock_context, action, inputs, path, data):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    result = await figma.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION
    assert result.result.data == data
    mock_context.fetch.assert_awaited_once()
    call = mock_context.fetch.call_args
    assert call.args == (f"https://api.figma.com/v1{path}",)
    assert call.kwargs["headers"] == {"Accept": "application/json"}
    assert call.kwargs["method"] == {"create_comment": "POST", "delete_comment": "DELETE"}.get(action, "GET")


@pytest.mark.parametrize("action,inputs,path,data", CASES, ids=[case[0] for case in CASES])
async def test_api_errors_are_not_success(mock_context, action, inputs, path, data):
    mock_context.fetch.side_effect = HTTPError(403, "Insufficient permissions")
    result = await figma.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "403" in result.result.message


@pytest.mark.parametrize(
    "auth",
    [{}, {"access_token": "flat"}, {"auth_type": "PlatformOauth2", "credentials": {}}],  # nosec B105
)
async def test_missing_or_flat_auth_is_rejected(mock_context, auth):
    mock_context.auth = auth
    result = await figma.execute_action("get_me", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_awaited()


async def test_whitespace_token_does_not_make_request(mock_context):
    mock_context.auth["credentials"]["access_token"] = "   "  # nosec B105
    result = await figma.execute_action("get_me", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    mock_context.fetch.assert_not_awaited()


@pytest.mark.parametrize("status", [401, 403, 404, 500])
async def test_non_2xx_response(mock_context, status):
    mock_context.fetch.return_value = FetchResponse(status=status, headers={}, data={"message": "Failure"})
    result = await figma.execute_action("get_me", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert str(status) in result.result.message


async def test_rate_limit_retry_after(mock_context):
    mock_context.fetch.return_value = FetchResponse(
        status=429, headers={"Retry-After": "60"}, data={"err": "Rate limited"}
    )
    result = await figma.execute_action("get_me", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Retry after 60 seconds" in result.result.message


async def test_http_exception_retains_retry_hint_without_leaking_credentials(mock_context):
    mock_context.fetch.side_effect = HTTPError(
        429, "test_figma_token", headers={"rEtRy-AfTeR": "90", "Authorization": "private"}
    )
    result = await figma.execute_action("get_me", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "Retry after 90 seconds" in result.result.message
    assert "test_figma_token" not in result.result.message
    assert "private" not in result.result.message


async def test_delete_error_body_is_not_reported_as_deleted(mock_context):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"error": True})
    result = await figma.execute_action("delete_comment", {"file_key": "AbC123", "comment_id": "456"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.parametrize("data", [[], {"err": "Render failed"}, {"error": True, "status": 400}])
async def test_malformed_and_api_error_bodies(mock_context, data):
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    result = await figma.execute_action("get_me", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
