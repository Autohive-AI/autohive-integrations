"""The live replies test discovers a real parent ID without creating comments."""

import runpy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("configured_id", ["", "configured-comment"])
async def test_reply_test_uses_top_level_comment_id(configured_id, monkeypatch):
    module = runpy.run_path(str(Path(__file__).with_name("test_youtube_integration.py")))
    test = module["TestListCommentReplies"]().test_returns_replies
    monkeypatch.setitem(test.__func__.__globals__, "TEST_COMMENT_ID", configured_id)
    context = MagicMock()
    context.fetch = AsyncMock(
        return_value=FetchResponse(
            status=200,
            headers={},
            data={"items": [{"id": "thread-id", "snippet": {"topLevelComment": {"id": "parent-comment"}}}]},
        )
    )
    result = MagicMock()
    result.type = ResultType.ACTION
    result.result.data = {"replies": []}
    execute = AsyncMock(return_value=result)
    monkeypatch.setattr(module["youtube"], "execute_action", execute)

    await test(context)

    execute.assert_awaited_once_with(
        "list_comment_replies",
        {"parent_comment_id": configured_id or "parent-comment", "max_results": 5},
        context,
    )
    assert context.fetch.await_count == (0 if configured_id else 1)


async def test_missing_comment_is_a_failure(monkeypatch):
    module = runpy.run_path(str(Path(__file__).with_name("test_youtube_integration.py")))
    test = module["TestListCommentReplies"]().test_returns_replies
    monkeypatch.setitem(test.__func__.__globals__, "TEST_COMMENT_ID", "")
    context = MagicMock()
    context.fetch = AsyncMock(return_value=FetchResponse(status=200, headers={}, data={"items": []}))
    with pytest.raises(AssertionError, match="Set YOUTUBE_TEST_COMMENT_ID"):
        await test(context)
