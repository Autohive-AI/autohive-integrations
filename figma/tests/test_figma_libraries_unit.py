"""Published library pagination and empty records."""

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from figma.figma import figma

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("resource", ["components", "component_sets", "styles"])
async def test_team_library_cursor_round_trip(mock_context, resource):
    data = {"status": 200, "error": False, "meta": {resource: [], "cursor": {"after": 987}}}
    mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=data)
    result = await figma.execute_action(
        f"list_team_{resource}", {"team_id": "123", "page_size": 10, "after": 0}, mock_context
    )
    assert result.type == ResultType.ACTION
    assert result.result.data == data
    mock_context.fetch.assert_awaited_once()
    assert mock_context.fetch.call_args.args == (f"https://api.figma.com/v1/teams/123/{resource}",)
    assert mock_context.fetch.call_args.kwargs["params"] == {"page_size": 10, "after": 0}


@pytest.mark.parametrize("resource", ["components", "component_sets", "styles"])
async def test_library_rejects_conflicting_cursors(mock_context, resource):
    result = await figma.execute_action(
        f"list_team_{resource}", {"team_id": "123", "before": 1, "after": 2}, mock_context
    )
    assert result.type == ResultType.VALIDATION_ERROR
    mock_context.fetch.assert_not_awaited()
