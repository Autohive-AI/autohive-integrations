"""Comment writes and caller-controlled pagination."""

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from figma.figma import figma

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"comment_id": "456"},
        {"client_meta": {"x": 10, "y": 20}},
        {"client_meta": {"node_id": "1:2", "node_offset": {"x": 10, "y": 20}}},
    ],
)
async def test_comment_body(mock_context, extra):
    mock_context.fetch.return_value = FetchResponse(
        status=200, headers={}, data={"id": "789", "message": "Review this"}
    )
    result = await figma.execute_action(
        "create_comment", {"file_key": "AbC123", "message": "Review this", **extra}, mock_context
    )
    assert result.type == ResultType.ACTION
    assert result.result.data["id"] == "789"
    call = mock_context.fetch.call_args
    assert call.args == ("https://api.figma.com/v1/files/AbC123/comments",)
    assert call.kwargs["method"] == "POST"
    assert call.kwargs["json"] == {"message": "Review this", **extra}
    assert "params" not in call.kwargs


async def test_delete_empty_body_and_escaped_id(mock_context):
    mock_context.fetch.return_value = FetchResponse(status=204, headers={}, data=None)
    result = await figma.execute_action(
        "delete_comment", {"file_key": "AbC123", "comment_id": "123/456?x=1"}, mock_context
    )
    assert result.result.data == {"deleted": True}
    assert mock_context.fetch.call_args.args == ("https://api.figma.com/v1/files/AbC123/comments/123%2F456%3Fx%3D1",)
    assert mock_context.fetch.call_args.kwargs["method"] == "DELETE"


async def test_versions_return_links_without_following_them(mock_context):
    pagination = {"next_page": "https://api.figma.com/v1/files/AbC123/versions?before=987"}
    mock_context.fetch.return_value = FetchResponse(
        status=200, headers={}, data={"versions": [], "pagination": pagination}
    )
    result = await figma.execute_action(
        "list_file_versions", {"file_key": "AbC123", "page_size": 50, "before": 1234}, mock_context
    )
    assert result.result.data["pagination"] == pagination
    mock_context.fetch.assert_awaited_once()
    assert mock_context.fetch.call_args.kwargs["params"] == {"page_size": 50, "before": 1234}


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("create_comment", {"file_key": "AbC123", "message": ""}),
        ("create_comment", {"file_key": "AbC123", "message": "Review", "client_meta": {"node_id": "1:2"}}),
        ("list_file_versions", {"file_key": "AbC123", "page_size": 51}),
        ("list_file_versions", {"file_key": "AbC123", "before": 1, "after": 2}),
        ("list_team_projects", {"team_id": "../123"}),
    ],
)
async def test_invalid_collaboration_inputs(mock_context, action, inputs):
    result = await figma.execute_action(action, inputs, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()
