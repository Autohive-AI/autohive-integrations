"""
Unit tests for the Circle integration using a mocked context.fetch().

Covers the SDK 2.0.0 migration surface:
- context.fetch() returns a FetchResponse; action output reads the body via .data
- error paths return ActionError (ResultType.ACTION_ERROR), not ActionResult error dicts
- missing required inputs surface as ResultType.VALIDATION_ERROR
plus the pure helper functions (auth headers, param building, markdown -> TipTap).
"""

import os
import sys

import pytest
from unittest.mock import MagicMock, AsyncMock
from autohive_integrations_sdk import FetchResponse, ResultType

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import circle as circle_mod  # noqa: E402
from circle import (  # noqa: E402
    build_auth_headers,
    build_search_params,
    handle_api_response,
    text_to_tiptap_body,
)

circle_integration = circle_mod.circle

pytestmark = pytest.mark.unit

AUTH = {"credentials": {"api_token": "test-token"}}  # nosec B105


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def make_ctx(response_data=None, status=200, auth=None):
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(return_value=ok(response_data, status))
    ctx.auth = AUTH if auth is None else auth
    return ctx


def make_ctx_multi(items, auth=None):
    """items: list of body dicts (wrapped as 200) or FetchResponse objects."""
    responses = [it if isinstance(it, FetchResponse) else ok(it) for it in items]
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=responses)
    ctx.auth = AUTH if auth is None else auth
    return ctx


# =============================================================================
# HELPERS — build_auth_headers
# =============================================================================


def test_build_auth_headers_uses_token_scheme():
    ctx = MagicMock()
    ctx.auth = AUTH
    headers = build_auth_headers(ctx)
    assert headers["Authorization"] == "Token test-token"
    assert headers["Content-Type"] == "application/json"


def test_build_auth_headers_missing_token_raises():
    ctx = MagicMock()
    ctx.auth = {}
    with pytest.raises(Exception, match="API token is required"):
        build_auth_headers(ctx)


# =============================================================================
# HELPERS — build_search_params
# =============================================================================


def test_build_search_params_filters_allowed_only():
    inputs = {"query": "hello", "not_allowed": "dropme", "page": 2}
    params = build_search_params(inputs, ["query", "page"])
    assert params == {"query": "hello", "page": 2}


def test_build_search_params_drops_none_values():
    inputs = {"query": None, "page": 1}
    params = build_search_params(inputs, ["query", "page"])
    assert params == {"page": 1}


# =============================================================================
# HELPERS — handle_api_response (FetchResponse -> ActionError)
# =============================================================================


def test_handle_api_response_ok_returns_none():
    assert handle_api_response(ok({"records": []})) is None


def test_handle_api_response_error_body_returns_action_error():
    err = handle_api_response(ok({"error": "Not found"}, status=200))
    assert err is not None
    assert "Not found" in err.message


def test_handle_api_response_non_2xx_without_error_body():
    err = handle_api_response(ok({"records": []}, status=500))
    assert err is not None
    assert "HTTP 500" in err.message


def test_handle_api_response_truncates_html_error_page():
    err = handle_api_response(ok({"error": "<html>" + "x" * 800 + "</html>"}))
    assert err is not None
    assert "HTML error page" in err.message
    assert len(err.message) < 300


# =============================================================================
# HELPERS — text_to_tiptap_body
# =============================================================================


def test_text_to_tiptap_body_returns_doc():
    doc = text_to_tiptap_body("# Title\n\nHello **world**")
    assert doc["type"] == "doc"
    assert isinstance(doc["content"], list)
    assert doc["content"][0]["type"] == "heading"


def test_text_to_tiptap_body_bold_mark():
    doc = text_to_tiptap_body("Hello **world**")
    para = doc["content"][0]
    marks = [m["type"] for node in para["content"] for m in node.get("marks", [])]
    assert "bold" in marks


# =============================================================================
# SEARCH POSTS
# =============================================================================


async def test_search_posts_success():
    ctx = make_ctx({"records": [{"id": 1, "name": "Post"}], "count": 1})
    result = await circle_integration.execute_action("search_posts", {"query": "hi"}, ctx)
    data = result.result.data
    assert data["posts"] == [{"id": 1, "name": "Post"}]
    assert data["count"] == 1
    assert "result" not in data  # success flag dropped in 2.0.0


async def test_search_posts_default_per_page():
    ctx = make_ctx({"records": [], "count": 0})
    await circle_integration.execute_action("search_posts", {}, ctx)
    params = ctx.fetch.call_args.kwargs.get("params", {})
    assert params["per_page"] == 10


async def test_search_posts_api_error_returns_action_error():
    ctx = make_ctx({"error": "Bad token"})
    result = await circle_integration.execute_action("search_posts", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "Bad token" in result.result.message


async def test_search_posts_auth_missing_returns_action_error():
    ctx = make_ctx({"records": []}, auth={})
    result = await circle_integration.execute_action("search_posts", {}, ctx)
    assert result.type == ResultType.ACTION_ERROR
    assert "API token is required" in result.result.message


# =============================================================================
# GET POST
# =============================================================================


async def test_get_post_success_unwraps_data():
    ctx = make_ctx({"id": "p1", "name": "My Post"})
    result = await circle_integration.execute_action("get_post", {"post_id": "p1"}, ctx)
    # The body (FetchResponse.data) must be returned, not the FetchResponse object
    assert result.result.data["post"] == {"id": "p1", "name": "My Post"}


async def test_get_post_missing_id_validation_error():
    ctx = make_ctx({})
    result = await circle_integration.execute_action("get_post", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


async def test_get_post_api_error():
    ctx = make_ctx({"error": "Post not found"})
    result = await circle_integration.execute_action("get_post", {"post_id": "x"}, ctx)
    assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# CREATE POST
# =============================================================================


async def test_create_post_success_and_tiptap_payload():
    # Circle's real create response wraps the post: {"message", "post": {...}}.
    ctx = make_ctx({"message": "Post created", "post": {"id": "new1", "name": "T"}})
    result = await circle_integration.execute_action(
        "create_post",
        {"space_id": 5, "name": "T", "body": "# Heading\n\nBody"},
        ctx,
    )
    assert result.result.data["post"]["id"] == "new1"
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload["space_id"] == 5
    assert payload["tiptap_body"]["body"]["type"] == "doc"
    assert payload["status"] == "published"  # default applied


async def test_create_post_missing_required_validation_error():
    ctx = make_ctx({})
    result = await circle_integration.execute_action("create_post", {"space_id": 5}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# UPDATE POST
# =============================================================================


async def test_update_post_success_only_sends_provided_fields():
    # Circle's real update response wraps the post: {"message", "post": {...}}.
    ctx = make_ctx({"message": "Post updated", "post": {"id": "p1", "name": "Renamed"}})
    result = await circle_integration.execute_action("update_post", {"post_id": "p1", "name": "Renamed"}, ctx)
    assert result.result.data["post"]["name"] == "Renamed"
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload == {"name": "Renamed"}
    assert ctx.fetch.call_args.kwargs.get("method") == "PUT"


async def test_update_post_missing_id_validation_error():
    ctx = make_ctx({})
    result = await circle_integration.execute_action("update_post", {"name": "x"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# MEMBERS
# =============================================================================


async def test_search_member_by_email_success():
    ctx = make_ctx({"id": "m1", "email": "a@b.com"})
    result = await circle_integration.execute_action("search_member_by_email", {"email": "a@b.com"}, ctx)
    assert result.result.data["member"]["email"] == "a@b.com"
    assert ctx.fetch.call_args.kwargs.get("params") == {"email": "a@b.com"}


async def test_search_member_by_email_missing_email_validation_error():
    ctx = make_ctx({})
    result = await circle_integration.execute_action("search_member_by_email", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


async def test_list_members_success():
    ctx = make_ctx({"records": [{"id": 1}, {"id": 2}], "count": 2})
    result = await circle_integration.execute_action("list_members", {}, ctx)
    assert len(result.result.data["members"]) == 2
    assert result.result.data["count"] == 2


async def test_get_member_success():
    ctx = make_ctx({"id": "m1", "name": "Jane"})
    result = await circle_integration.execute_action("get_member", {"member_id": "m1"}, ctx)
    assert result.result.data["member"]["name"] == "Jane"


async def test_get_member_missing_id_validation_error():
    ctx = make_ctx({})
    result = await circle_integration.execute_action("get_member", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# SPACES
# =============================================================================


async def test_search_spaces_success():
    ctx = make_ctx({"records": [{"id": 1, "name": "General"}], "count": 1})
    result = await circle_integration.execute_action("search_spaces", {}, ctx)
    assert result.result.data["spaces"][0]["name"] == "General"
    assert result.result.data["count"] == 1


async def test_get_space_success():
    ctx = make_ctx({"id": "s1", "name": "General"})
    result = await circle_integration.execute_action("get_space", {"space_id": "s1"}, ctx)
    assert result.result.data["space"]["id"] == "s1"


async def test_get_space_missing_id_validation_error():
    ctx = make_ctx({})
    result = await circle_integration.execute_action("get_space", {}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


# =============================================================================
# EVENTS
# =============================================================================


async def test_search_events_success():
    ctx = make_ctx({"records": [{"id": 1, "name": "Meetup"}], "count": 1})
    result = await circle_integration.execute_action("search_events", {"time_filter": "upcoming"}, ctx)
    assert result.result.data["events"][0]["name"] == "Meetup"


async def test_get_event_success():
    ctx = make_ctx({"id": "e1", "name": "Meetup"})
    result = await circle_integration.execute_action("get_event", {"event_id": "e1"}, ctx)
    assert result.result.data["event"]["id"] == "e1"


# =============================================================================
# COMMENTS
# =============================================================================


async def test_create_comment_success():
    ctx = make_ctx({"id": "c1", "body": "Nice"})
    result = await circle_integration.execute_action("create_comment", {"post_id": "p1", "body": "Nice"}, ctx)
    assert result.result.data["comment"]["id"] == "c1"
    payload = ctx.fetch.call_args.kwargs.get("json", {})
    assert payload == {"post_id": "p1", "body": "Nice"}


async def test_create_comment_missing_body_validation_error():
    ctx = make_ctx({})
    result = await circle_integration.execute_action("create_comment", {"post_id": "p1"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


async def test_get_post_comments_success():
    ctx = make_ctx({"records": [{"id": "c1"}, {"id": "c2"}], "count": 2})
    result = await circle_integration.execute_action("get_post_comments", {"post_id": "p1"}, ctx)
    assert len(result.result.data["comments"]) == 2
    assert result.result.data["count"] == 2


# =============================================================================
# COMMUNITY
# =============================================================================


async def test_get_community_info_success():
    ctx = make_ctx({"id": "comm1", "name": "Autohive"})
    result = await circle_integration.execute_action("get_community_info", {}, ctx)
    assert result.result.data["community"]["name"] == "Autohive"


# =============================================================================
# MEMBER TAGS (multi-fetch loops)
# =============================================================================


async def test_add_member_tags_success_counts_each_tag():
    ctx = make_ctx_multi([{"id": "tm1"}, {"id": "tm2"}])
    result = await circle_integration.execute_action(
        "add_member_tags", {"user_email": "a@b.com", "member_tag_ids": [1, 2]}, ctx
    )
    data = result.result.data
    assert data["tags_added"] == 2
    assert data["member"] == {"id": "tm1"}
    assert ctx.fetch.call_count == 2


async def test_add_member_tags_error_midloop_returns_action_error():
    ctx = make_ctx_multi([{"id": "tm1"}, {"error": "tag invalid"}])
    result = await circle_integration.execute_action(
        "add_member_tags", {"user_email": "a@b.com", "member_tag_ids": [1, 2]}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "tag invalid" in result.result.message


async def test_add_member_tags_missing_inputs_validation_error():
    ctx = make_ctx({})
    result = await circle_integration.execute_action("add_member_tags", {"user_email": "a@b.com"}, ctx)
    assert result.type == ResultType.VALIDATION_ERROR


async def test_remove_member_tags_success_counts_via_status():
    # DELETE typically returns 204 with an empty body
    ctx = make_ctx_multi([ok(None, status=204), ok(None, status=204)])
    result = await circle_integration.execute_action(
        "remove_member_tags", {"user_email": "a@b.com", "member_tag_ids": [1, 2]}, ctx
    )
    assert result.result.data["tags_removed"] == 2


async def test_remove_member_tags_failed_delete_returns_action_error():
    ctx = make_ctx_multi([ok(None, status=404)])
    result = await circle_integration.execute_action(
        "remove_member_tags", {"user_email": "a@b.com", "member_tag_ids": [1]}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "HTTP 404" in result.result.message


# =============================================================================
# SPACE GROUPS
# =============================================================================


async def test_add_member_to_space_groups_success():
    ctx = make_ctx_multi([{"id": "g1"}])
    result = await circle_integration.execute_action(
        "add_member_to_space_groups", {"email": "a@b.com", "space_group_ids": [10]}, ctx
    )
    assert result.result.data["groups_added"] == 1
    assert result.result.data["member"] == {"id": "g1"}


async def test_remove_member_from_space_groups_success():
    ctx = make_ctx_multi([ok({}, status=200), ok({}, status=200)])
    result = await circle_integration.execute_action(
        "remove_member_from_space_groups", {"email": "a@b.com", "space_group_ids": [10, 11]}, ctx
    )
    assert result.result.data["groups_removed"] == 2


# =============================================================================
# LISTING ACTIONS
# =============================================================================


async def test_list_tags_success_and_default_per_page():
    ctx = make_ctx({"records": [{"id": 1}], "count": 1})
    result = await circle_integration.execute_action("list_tags", {}, ctx)
    assert result.result.data["tags"][0]["id"] == 1
    assert ctx.fetch.call_args.kwargs.get("params", {})["per_page"] == 100


async def test_list_space_groups_success():
    ctx = make_ctx({"records": [{"id": 1}], "count": 1})
    result = await circle_integration.execute_action("list_space_groups", {}, ctx)
    assert result.result.data["space_groups"][0]["id"] == 1
    assert result.result.data["count"] == 1


async def test_list_access_groups_success():
    ctx = make_ctx({"records": [{"id": 1}, {"id": 2}], "count": 2})
    result = await circle_integration.execute_action("list_access_groups", {}, ctx)
    assert len(result.result.data["access_groups"]) == 2


# =============================================================================
# ACCESS GROUPS (multi-fetch loops)
# =============================================================================


async def test_add_member_to_access_groups_success():
    ctx = make_ctx_multi([{"id": "ag1"}, {"id": "ag2"}])
    result = await circle_integration.execute_action(
        "add_member_to_access_groups", {"email": "a@b.com", "access_group_ids": [1, 2]}, ctx
    )
    assert result.result.data["groups_added"] == 2
    assert result.result.data["member"] == {"id": "ag1"}


async def test_remove_member_from_access_groups_success():
    ctx = make_ctx_multi([ok(None, status=204)])
    result = await circle_integration.execute_action(
        "remove_member_from_access_groups", {"email": "a@b.com", "access_group_ids": [1]}, ctx
    )
    assert result.result.data["groups_removed"] == 1


async def test_add_member_to_access_groups_error_returns_action_error():
    ctx = make_ctx_multi([{"error": "no such group"}])
    result = await circle_integration.execute_action(
        "add_member_to_access_groups", {"email": "a@b.com", "access_group_ids": [1]}, ctx
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "no such group" in result.result.message
