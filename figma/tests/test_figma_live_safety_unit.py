"""Offline checks for live-test write guards and failure cleanup, never API verification."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from figma.figma import figma
from figma.tests import test_figma_integration as live_tests

pytestmark = pytest.mark.unit


class CommentTransport:
    """Small transport fake to exercise the live harness without credentials or network."""

    def __init__(self, failed_delete=None):
        self.comments = {}
        self.deleted = []
        self.failed_delete = failed_delete
        self.next_id = 1
        self.last_headers = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def request(self, method, url, **kwargs):
        self.last_headers = kwargs["headers"]
        status = 200
        if method == "POST":
            comment_id = str(self.next_id)
            self.next_id += 1
            body = kwargs["json"]
            data = {"id": comment_id, "message": body["message"], "parent_id": body.get("comment_id", "")}
            self.comments[comment_id] = data
        elif method == "DELETE":
            comment_id = url.rsplit("/", 1)[1]
            self.deleted.append(comment_id)
            if comment_id == self.failed_delete:
                status, data = 500, {"err": "simulated cleanup failure"}
            else:
                self.comments.pop(comment_id, None)
                data = None
        else:
            data = {"comments": list(self.comments.values())}
        response = MagicMock(status=status, headers={})
        response.text = AsyncMock(return_value=json.dumps(data) if data is not None else "")
        manager = MagicMock()
        manager.__aenter__ = AsyncMock(return_value=response)
        manager.__aexit__ = AsyncMock(return_value=False)
        return manager


def harness(monkeypatch, transport, enabled=True, marked=True):
    monkeypatch.setattr(live_tests.aiohttp, "ClientSession", lambda **kwargs: transport)
    values = {
        "FIGMA_ACCESS_TOKEN": "offline-placeholder",  # nosec B105
        "FIGMA_RUN_DESTRUCTIVE_TESTS": "1" if enabled else "0",
        "FIGMA_TEST_COMMENT_FILE_KEY": "TestFile",
    }
    request = MagicMock()
    request.node.get_closest_marker.return_value = object() if marked else None
    return live_tests.live_context.__wrapped__(values.__getitem__, values.get, request, {}), values


async def test_cleanup_runs_after_test_failure(monkeypatch):
    transport = CommentTransport()
    generator, _ = harness(monkeypatch, transport)
    context = await anext(generator)
    await figma.execute_action("create_comment", {"file_key": "TestFile", "message": "root"}, context)
    await figma.execute_action(
        "create_comment", {"file_key": "TestFile", "message": "reply", "comment_id": "1"}, context
    )
    with pytest.raises(AssertionError, match="simulated test failure"):
        await generator.athrow(AssertionError("simulated test failure"))
    assert transport.deleted == ["2", "1"]
    assert not transport.comments


async def test_cleanup_attempts_every_comment_and_reports_leftovers(monkeypatch):
    transport = CommentTransport(failed_delete="2")
    generator, _ = harness(monkeypatch, transport)
    context = await anext(generator)
    for message in ("root", "reply"):
        await figma.execute_action("create_comment", {"file_key": "TestFile", "message": message}, context)
    with pytest.raises(AssertionError, match="Could not clean up Figma test comment IDs"):
        await generator.aclose()
    assert transport.deleted == ["2", "1"]
    assert set(transport.comments) == {"2"}


@pytest.mark.parametrize("enabled,marked", [(False, True), (True, False)])
async def test_live_writes_require_opt_in_and_marker(monkeypatch, enabled, marked):
    transport = CommentTransport()
    generator, _ = harness(monkeypatch, transport, enabled=enabled, marked=marked)
    context = await anext(generator)
    try:
        with pytest.raises(AssertionError, match="Writes require"):
            await context.fetch(
                "https://api.figma.com/v1/files/TestFile/comments", method="POST", json={"message": "x"}
            )
    finally:
        await generator.aclose()
    assert not transport.comments


async def test_local_pat_fallback_does_not_use_oauth_bearer_header(monkeypatch):
    transport = CommentTransport()
    generator, values = harness(monkeypatch, transport, enabled=False)
    values["FIGMA_PERSONAL_ACCESS_TOKEN"] = values.pop("FIGMA_ACCESS_TOKEN")
    context = await anext(generator)
    try:
        await context.fetch("https://api.figma.com/v1/files/TestFile/comments")
    finally:
        await generator.aclose()
    assert transport.last_headers["X-Figma-Token"] == "offline-placeholder"
    assert "Authorization" not in transport.last_headers


async def test_oauth_takes_precedence_over_optional_local_pat(monkeypatch):
    transport = CommentTransport()
    generator, values = harness(monkeypatch, transport, enabled=False)
    values["FIGMA_PERSONAL_ACCESS_TOKEN"] = "unused-placeholder"  # nosec B105
    context = await anext(generator)
    try:
        await context.fetch("https://api.figma.com/v1/files/TestFile/comments")
    finally:
        await generator.aclose()
    assert transport.last_headers["Authorization"] == "Bearer offline-placeholder"
    assert "X-Figma-Token" not in transport.last_headers


async def test_comment_lifecycle_deletes_only_its_own_records(monkeypatch):
    transport = CommentTransport()
    transport.comments["existing"] = {"id": "existing", "message": "keep me"}
    generator, values = harness(monkeypatch, transport)
    context = await anext(generator)
    call = live_tests.call.__wrapped__(context, {})
    try:
        await live_tests.TestCommentLifecycle().test_create_reply_list_and_delete(
            values.get, values.__getitem__, context, call
        )
    finally:
        await generator.aclose()
    assert transport.deleted == ["2", "1"]
    assert set(transport.comments) == {"existing"}
