import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402
from urllib.parse import parse_qs, urlparse  # noqa: E402

from autohive_integrations_sdk import ActionError, FetchResponse, ResultType  # noqa: E402

from guidecx.guidecx import (  # noqa: E402
    guidecx,
    API_BASE_URL,
    DEFAULT_LIMIT,
    MAX_LIMIT,
    clamp_limit,
    get_api_token,
    get_headers,
    paged_result,
    prune,
    prune_body,
    page_args,
    first_record,
    time_record_body,
    placement_body,
    build_query,
    path_id,
)

pytestmark = pytest.mark.unit

# Path-bound IDs must be canonical UUIDs; the handlers reject anything else
# because a non-UUID segment can rewrite the request path. Query-only and
# response-payload IDs stay as short readable placeholders.
PROJECT_ID = "11111111-1111-4111-8111-111111111111"
TASK_ID = "22222222-2222-4222-8222-222222222222"
CUSTOMER_ID = "33333333-3333-4333-8333-333333333333"
MEMBER_ID = "44444444-4444-4444-8444-444444444444"
WEBHOOK_ID = "55555555-5555-4555-8555-555555555555"
MISSING_ID = "66666666-6666-4666-8666-666666666666"


def ok(data, status=200):
    """Build a FetchResponse like the SDK returns from context.fetch."""
    return FetchResponse(status=status, headers={}, data=data)


def fetch_url(mock_context, index=0):
    """The request URL passed to context.fetch, as a string."""
    return str(mock_context.fetch.call_args_list[index].args[0])


def fetch_kwargs(mock_context, index=0):
    """The keyword arguments passed to context.fetch."""
    return mock_context.fetch.call_args_list[index].kwargs


def fetch_path(mock_context, index=0):
    """The request URL without its query string."""
    return urlparse(fetch_url(mock_context, index)).path


def fetch_params(mock_context, index=0):
    """Query parameters parsed back out of the request URL.

    The integration builds the query string itself rather than passing params
    to context.fetch, because the SDK JSON-encodes list values and GUIDEcx
    rejects that. Values are always lists here, so a filter sent as repeated
    parameters is distinguishable from one sent once.
    """
    return parse_qs(urlparse(fetch_url(mock_context, index)).query)


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "Custom",
        "credentials": {"api_token": "test_token"},  # nosec B105
    }
    return ctx


# ---- Helper / utility functions ----


class TestGetApiToken:
    def test_reads_from_credentials(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"api_token": "abc"}}  # nosec B105 - test fixture, not a real credential
        assert get_api_token(ctx) == "abc"

    def test_falls_back_to_top_level(self):
        ctx = MagicMock()
        ctx.auth = {"api_token": "abc"}  # nosec B105 - test fixture, not a real credential
        assert get_api_token(ctx) == "abc"

    def test_raises_when_missing(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {}}
        with pytest.raises(ValueError, match="api_token"):
            get_api_token(ctx)

    def test_raises_when_empty_string(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"api_token": ""}}  # nosec B105 - test fixture, not a real credential
        with pytest.raises(ValueError):
            get_api_token(ctx)


class TestGetHeaders:
    def test_builds_bearer_header(self):
        ctx = MagicMock()
        ctx.auth = {"credentials": {"api_token": "abc"}}  # nosec B105 - test fixture, not a real credential
        headers = get_headers(ctx)
        assert headers["Authorization"] == "Bearer abc"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"


class TestClampLimit:
    def test_passes_through_valid_value(self):
        assert clamp_limit(25) == 25

    def test_caps_at_max(self):
        assert clamp_limit(5000) == MAX_LIMIT

    def test_floors_at_one(self):
        assert clamp_limit(0) == 1
        assert clamp_limit(-10) == 1

    def test_defaults_on_garbage(self):
        assert clamp_limit(None) == DEFAULT_LIMIT
        assert clamp_limit("abc") == DEFAULT_LIMIT

    def test_accepts_numeric_string(self):
        assert clamp_limit("30") == 30


class TestPrune:
    def test_keeps_set_values(self):
        assert prune({"projectId": "p1"}) == {"projectId": "p1"}

    def test_drops_none_empty_string_and_empty_list(self):
        assert prune({"a": None, "b": "", "c": [], "d": "keep"}) == {"d": "keep"}

    def test_preserves_lists_for_repeatable_filters(self):
        assert prune({"statusCategory": ["DONE", "LATE"]}) == {"statusCategory": ["DONE", "LATE"]}

    def test_keeps_zero(self):
        # offset=0 is meaningful and must survive pruning.
        assert prune({"offset": 0}) == {"offset": 0}

    def test_keeps_false(self):
        assert prune({"flag": False}) == {"flag": False}


class TestPagedResult:
    def test_derives_has_more_from_total(self):
        body = {"data": [{"id": "1"}], "metadata": {"total": 10, "offset": 0, "limit": 1}}
        result = paged_result(body, "projects", 1, 0)
        assert result["projects"] == [{"id": "1"}]
        assert result["total"] == 10
        assert result["has_more"] is True

    def test_has_more_false_on_last_page(self):
        body = {"data": [{"id": "9"}, {"id": "10"}], "metadata": {"total": 10, "offset": 8, "limit": 2}}
        assert paged_result(body, "projects", 2, 8)["has_more"] is False

    def test_falls_back_when_total_missing(self):
        body = {"data": [{"id": "1"}, {"id": "2"}], "metadata": {}}
        # A full page with no total means there is probably another page.
        assert paged_result(body, "tasks", 2, 0)["has_more"] is True

    def test_partial_page_without_total_is_last(self):
        body = {"data": [{"id": "1"}], "metadata": {}}
        assert paged_result(body, "tasks", 5, 0)["has_more"] is False

    def test_handles_empty_body(self):
        result = paged_result(None, "tasks", 50, 0)
        assert result["tasks"] == []
        assert result["has_more"] is False


class TestApiConfiguration:
    def test_targets_v3(self):
        # v2 is superseded and only accepts the deprecated workspace tokens.
        assert API_BASE_URL == "https://api.guidecx.com/api/v3"


# ---- path-bound ID validation ----


class TestPathId:
    """Path segments must be canonical UUIDs.

    A non-UUID value is not merely invalid: the URL library resolves dot
    segments before the request is sent, so a crafted "id" rewrites the path
    and reaches a different endpoint than the action intends.
    """

    def test_accepts_a_canonical_uuid(self):
        assert path_id(PROJECT_ID, "project_id") == PROJECT_ID

    def test_accepts_uppercase_hex(self):
        assert path_id(PROJECT_ID.upper(), "project_id") == PROJECT_ID.upper()

    @pytest.mark.parametrize(
        "value",
        [
            "p1",
            "",
            "   ",
            "../projects/other",
            "11111111-1111-4111-8111-111111111111/../../members",
            "11111111-1111-4111-8111-11111111111",  # one digit short
            "11111111111141118111111111111111",  # no hyphens
            "gggggggg-1111-4111-8111-111111111111",  # non-hex
            None,
            42,
        ],
    )
    def test_rejects_anything_else(self, value):
        with pytest.raises(ValueError, match="must be a GUIDEcx UUID"):
            path_id(value, "project_id")

    def test_error_names_the_field(self):
        with pytest.raises(ValueError, match="webhook_id"):
            path_id("nope", "webhook_id")


class TestPathTraversalIsRefused:
    """The concrete attack: a crafted webhook_id reaching the members endpoint."""

    TRAVERSAL = f"../projects/{PROJECT_ID}/members/{MEMBER_ID}"

    def test_url_library_would_rewrite_the_path(self):
        """Why this matters, pinned so the risk is not theoretical."""
        from yarl import URL

        rewritten = URL(f"{API_BASE_URL}/webhooks/{self.TRAVERSAL}").path
        assert rewritten == f"/api/v3/projects/{PROJECT_ID}/members/{MEMBER_ID}"
        assert "/webhooks/" not in rewritten

    @pytest.mark.asyncio
    async def test_delete_webhook_refuses_a_traversal_id(self, mock_context):
        result = await guidecx.execute_action("delete_webhook", {"webhook_id": self.TRAVERSAL}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_handler_refuses_it_even_without_schema_validation(self, mock_context):
        """The schema pattern is a second line of defence, not the only one."""
        from guidecx.guidecx import DeleteWebhookAction

        result = await DeleteWebhookAction().execute({"webhook_id": self.TRAVERSAL}, mock_context)

        assert isinstance(result, ActionError)
        assert "webhook_id" in result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "action,inputs",
        [
            ("get_customer", {"customer_id": TRAVERSAL}),
            ("remove_project_member", {"project_id": TRAVERSAL, "member_id": MEMBER_ID}),
            ("remove_project_member", {"project_id": PROJECT_ID, "member_id": TRAVERSAL}),
            ("create_phase", {"project_id": TRAVERSAL, "name": "Phase"}),
            ("add_task_note", {"task_id": TRAVERSAL, "note": "hi"}),
            ("list_project_members", {"project_id": TRAVERSAL}),
        ],
    )
    async def test_every_path_bound_action_refuses_traversal(self, action, inputs, mock_context):
        result = await guidecx.execute_action(action, inputs, mock_context)

        assert result.type in (ResultType.VALIDATION_ERROR, ResultType.ACTION_ERROR)
        mock_context.fetch.assert_not_called()


# ---- query string serialization ----


class TestBuildQuery:
    """GUIDEcx declares its list filters collectionFormat: multi.

    The SDK's context.fetch(params=...) JSON-encodes list values, which GUIDEcx
    rejects with HTTP 400, so the query string is built by the integration.
    """

    def test_list_becomes_repeated_parameters(self):
        assert build_query({"statusCategory": ["IN_PROGRESS", "LATE"]}) == (
            "statusCategory=IN_PROGRESS&statusCategory=LATE"
        )

    def test_single_element_list_is_still_a_bare_value(self):
        assert build_query({"id": ["p1"]}) == "id=p1"

    def test_scalars_pass_through(self):
        assert build_query({"limit": 50, "offset": 0}) == "limit=50&offset=0"

    def test_booleans_are_lowercased(self):
        # str(True) would send "True", which is not a JSON boolean literal.
        assert build_query({"hasCustomer": True}) == "hasCustomer=true"
        assert build_query({"hasCustomer": False}) == "hasCustomer=false"

    def test_values_are_url_encoded(self):
        assert build_query({"email": ["a@b.com"]}) == "email=a%40b.com"

    def test_never_emits_a_json_array(self):
        """Regression: the failure mode was id=%5B%22p1%22%5D."""
        query = build_query({"id": ["p1", "p2"], "tag": ["x"]})
        assert "%5B" not in query and "[" not in query
        assert query == "id=p1&id=p2&tag=x"


class TestQueryReachesTheUrl:
    """The query has to be in the URL, not handed to context.fetch as params."""

    @pytest.mark.asyncio
    async def test_params_are_not_delegated_to_the_sdk(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action("list_projects", {"status_category": ["IN_PROGRESS", "LATE"]}, mock_context)

        # Passing params= would let the SDK JSON-encode the list again.
        assert "params" not in fetch_kwargs(mock_context)
        assert "statusCategory=IN_PROGRESS&statusCategory=LATE" in fetch_url(mock_context)

    @pytest.mark.asyncio
    async def test_get_project_sends_a_bare_id_filter(self, mock_context):
        """This is the call that returned HTTP 400 in production."""
        mock_context.fetch.return_value = ok({"data": [{"id": PROJECT_ID}]})

        await guidecx.execute_action("get_project", {"project_id": PROJECT_ID}, mock_context)

        url = fetch_url(mock_context)
        assert f"id={PROJECT_ID}" in url
        assert "%5B" not in url


# ---- list_projects ----


class TestListProjects:
    @pytest.mark.asyncio
    async def test_success_returns_projects_and_pagination(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "data": [{"id": "p1", "name": "Acme Onboarding", "statusCategory": "IN_PROGRESS"}],
                "metadata": {"total": 3, "offset": 0, "limit": 50},
            }
        )

        result = await guidecx.execute_action("list_projects", {}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["projects"][0]["name"] == "Acme Onboarding"
        assert data["total"] == 3
        assert data["has_more"] is True
        assert fetch_path(mock_context).endswith("/projects")

    @pytest.mark.asyncio
    async def test_sends_default_pagination(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action("list_projects", {}, mock_context)

        params = fetch_params(mock_context)
        assert params["limit"] == [str(DEFAULT_LIMIT)]
        assert params["offset"] == ["0"]

    @pytest.mark.asyncio
    async def test_sends_filters_with_api_names(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action(
            "list_projects",
            {
                "status_category": ["IN_PROGRESS", "LATE"],
                "customer_id": ["c1"],
                "updated_after": "2026-01-01T00:00:00Z",
            },
            mock_context,
        )

        params = fetch_params(mock_context)
        assert params["statusCategory"] == ["IN_PROGRESS", "LATE"]
        assert params["customerId"] == ["c1"]
        assert params["updatedAfter"] == ["2026-01-01T00:00:00Z"]

    @pytest.mark.asyncio
    async def test_limit_above_the_cap_is_rejected(self, mock_context):
        # config.json declares maximum: 500, matching the server-side cap, so an
        # over-large page size fails validation instead of silently returning
        # fewer records than the caller asked for.
        result = await guidecx.execute_action("list_projects", {"limit": 9999}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_limit_is_accepted(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action("list_projects", {"limit": MAX_LIMIT}, mock_context)

        assert fetch_params(mock_context)["limit"] == [str(MAX_LIMIT)]

    @pytest.mark.asyncio
    async def test_sends_bearer_token(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action("list_projects", {}, mock_context)

        assert fetch_kwargs(mock_context)["headers"]["Authorization"] == "Bearer test_token"

    @pytest.mark.asyncio
    async def test_missing_token_is_rejected_before_the_handler_runs(self, mock_context):
        # config.json marks api_token as required, so the SDK rejects the call
        # during auth validation and no request is ever made.
        mock_context.auth = {"auth_type": "Custom", "credentials": {}}

        result = await guidecx.execute_action("list_projects", {}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        assert "api_token" in result.result["message"]
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_http_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 401: unauthorized")

        result = await guidecx.execute_action("list_projects", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "unauthorized" in result.result.message


# ---- get_project ----


class TestGetProject:
    @pytest.mark.asyncio
    async def test_success_returns_single_project(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": PROJECT_ID, "name": "Acme"}], "metadata": {"total": 1}})

        result = await guidecx.execute_action("get_project", {"project_id": PROJECT_ID}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["project"]["id"] == PROJECT_ID

    @pytest.mark.asyncio
    async def test_queries_search_endpoint_by_id(self, mock_context):
        # There is no GET /projects/{id}; the id filter on search is used instead.
        mock_context.fetch.return_value = ok({"data": [{"id": PROJECT_ID}], "metadata": {"total": 1}})

        await guidecx.execute_action("get_project", {"project_id": PROJECT_ID}, mock_context)

        assert fetch_path(mock_context).endswith("/projects")
        assert fetch_params(mock_context) == {"id": [PROJECT_ID], "limit": ["1"]}

    @pytest.mark.asyncio
    async def test_not_found_returns_error(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        result = await guidecx.execute_action("get_project", {"project_id": MISSING_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert MISSING_ID in result.result.message


# ---- list_milestones ----


class TestListMilestones:
    @pytest.mark.asyncio
    async def test_success_returns_milestones(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "data": [{"id": "m1", "name": "Kickoff", "sortOrder": 1}],
                "metadata": {"total": 1, "offset": 0, "limit": 50},
            }
        )

        result = await guidecx.execute_action("list_milestones", {"project_id": PROJECT_ID}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["milestones"][0]["name"] == "Kickoff"
        assert result.result.data["has_more"] is False

    @pytest.mark.asyncio
    async def test_scopes_to_project(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action("list_milestones", {"project_id": PROJECT_ID, "phase_id": "ph1"}, mock_context)

        params = fetch_params(mock_context)
        assert params["projectId"] == [PROJECT_ID]
        assert params["phaseId"] == ["ph1"]
        assert fetch_path(mock_context).endswith("/milestones")


# ---- list_tasks ----


class TestListTasks:
    @pytest.mark.asyncio
    async def test_success_returns_tasks(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "data": [{"id": TASK_ID, "name": "Send contract", "statusCategory": "NOT_STARTED"}],
                "metadata": {"total": 1, "offset": 0, "limit": 50},
            }
        )

        result = await guidecx.execute_action("list_tasks", {"project_id": PROJECT_ID}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["tasks"][0]["id"] == TASK_ID

    @pytest.mark.asyncio
    async def test_sends_all_filters(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action(
            "list_tasks",
            {
                "project_id": PROJECT_ID,
                "milestone_id": "m1",
                "assignee_id": "u1",
                "status_category": ["STUCK"],
                "name": "contract",
                "type_filter": "TASK",
            },
            mock_context,
        )

        params = fetch_params(mock_context)
        assert params["projectId"] == [PROJECT_ID]
        assert params["milestoneId"] == ["m1"]
        assert params["assigneeId"] == ["u1"]
        assert params["statusCategory"] == ["STUCK"]
        assert params["name"] == ["contract"]
        assert params["typeFilter"] == ["TASK"]

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 429: rate limited")

        result = await guidecx.execute_action("list_tasks", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "rate limited" in result.result.message


# ---- update_task ----


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_success_returns_updated_task(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": TASK_ID, "status": "Complete"}]})

        result = await guidecx.execute_action(
            "update_task", {"project_id": PROJECT_ID, "task_id": TASK_ID, "status": "Complete"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["task"]["status"] == "Complete"

    @pytest.mark.asyncio
    async def test_sends_project_scoped_patch(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": TASK_ID}]})

        await guidecx.execute_action(
            "update_task", {"project_id": PROJECT_ID, "task_id": TASK_ID, "status": "Complete"}, mock_context
        )

        assert fetch_path(mock_context).endswith(f"/projects/{PROJECT_ID}/tasks")
        kwargs = fetch_kwargs(mock_context)
        assert kwargs["method"] == "PATCH"
        assert kwargs["json"] == {"tasks": [{"id": TASK_ID, "status": "Complete"}]}

    @pytest.mark.asyncio
    async def test_maps_optional_fields_to_api_names(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": TASK_ID}]})

        await guidecx.execute_action(
            "update_task",
            {
                "project_id": PROJECT_ID,
                "task_id": TASK_ID,
                "end_date": "2026-09-01T00:00:00Z",
                "assignee_id": "u1",
                "priority": "HIGH",
            },
            mock_context,
        )

        task = fetch_kwargs(mock_context)["json"]["tasks"][0]
        assert task["endDate"] == "2026-09-01T00:00:00Z"
        assert task["assigneeId"] == "u1"
        assert task["priority"] == "HIGH"

    @pytest.mark.asyncio
    async def test_no_fields_returns_error_without_calling_api(self, mock_context):
        result = await guidecx.execute_action(
            "update_task", {"project_id": PROJECT_ID, "task_id": TASK_ID}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "No update fields" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_response_returns_error(self, mock_context):
        mock_context.fetch.return_value = ok({"data": []})

        result = await guidecx.execute_action(
            "update_task", {"project_id": PROJECT_ID, "task_id": TASK_ID, "status": "Complete"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert TASK_ID in result.result.message


# ---- add_task_note ----


class TestAddTaskNote:
    @pytest.mark.asyncio
    async def test_success_returns_messages(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": "msg1", "formattedContent": "Hello"}]})

        result = await guidecx.execute_action("add_task_note", {"task_id": TASK_ID, "content": "Hello"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["messages"][0]["id"] == "msg1"

    @pytest.mark.asyncio
    async def test_wraps_single_note_in_bulk_body(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": "msg1"}]})

        await guidecx.execute_action("add_task_note", {"task_id": TASK_ID, "content": "Hello"}, mock_context)

        assert fetch_path(mock_context).endswith(f"/tasks/{TASK_ID}/messages")
        kwargs = fetch_kwargs(mock_context)
        assert kwargs["method"] == "POST"
        assert kwargs["json"] == {"messages": [{"formattedContent": "Hello", "internalOnly": False}]}

    @pytest.mark.asyncio
    async def test_internal_only_flag_is_forwarded(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": "msg1"}]})

        await guidecx.execute_action(
            "add_task_note", {"task_id": TASK_ID, "content": "Internal", "internal_only": True}, mock_context
        )

        assert fetch_kwargs(mock_context)["json"]["messages"][0]["internalOnly"] is True

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 404: task not found")

        result = await guidecx.execute_action("add_task_note", {"task_id": TASK_ID, "content": "y"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "not found" in result.result.message


# ---- get_customer ----


class TestGetCustomer:
    @pytest.mark.asyncio
    async def test_success_returns_customer(self, mock_context):
        mock_context.fetch.return_value = ok({"data": {"id": CUSTOMER_ID, "name": "Acme", "domain": "acme.com"}})

        result = await guidecx.execute_action("get_customer", {"customer_id": CUSTOMER_ID}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["customer"]["domain"] == "acme.com"
        assert fetch_path(mock_context).endswith(f"/customers/{CUSTOMER_ID}")

    @pytest.mark.asyncio
    async def test_missing_data_returns_error(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await guidecx.execute_action("get_customer", {"customer_id": CUSTOMER_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert CUSTOMER_ID in result.result.message


# ---- config / code sync ----


class TestConfigSync:
    def test_every_config_action_has_a_handler(self):
        import json
        from pathlib import Path

        config = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))
        for action_key in config["actions"]:
            assert action_key in guidecx._action_handlers, f"config.json declares '{action_key}' with no handler"

    def test_every_handler_is_declared_in_config(self):
        import json
        from pathlib import Path

        config = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))
        for action_key in guidecx._action_handlers:
            assert action_key in config["actions"], f"handler '{action_key}' is missing from config.json"


# ---- Shared helpers added with the tranche-1 actions ----


class TestPageArgs:
    def test_defaults(self):
        assert page_args({}) == (DEFAULT_LIMIT, 0)

    def test_reads_and_clamps(self):
        assert page_args({"limit": 5000, "offset": 7}) == (MAX_LIMIT, 7)

    def test_offset_none_becomes_zero(self):
        assert page_args({"offset": None}) == (DEFAULT_LIMIT, 0)


class TestFirstRecord:
    def test_returns_first(self):
        assert first_record({"data": [{"id": "a"}, {"id": "b"}]}) == {"id": "a"}

    def test_none_on_empty_list(self):
        assert first_record({"data": []}) is None

    def test_none_on_empty_body(self):
        assert first_record(None) is None
        assert first_record({}) is None


class TestTimeRecordBody:
    def test_maps_required_fields_to_api_names(self):
        body = time_record_body({"member_id": MEMBER_ID, "date_of_work": "2026-08-03T00:00:00Z", "hours_worked": 1.5})
        assert body == {
            "timeRecords": [{"memberId": MEMBER_ID, "dateOfWork": "2026-08-03T00:00:00Z", "hoursWorked": 1.5}]
        }

    def test_includes_optional_fields_when_set(self):
        record = time_record_body(
            {
                "member_id": MEMBER_ID,
                "date_of_work": "2026-08-03T00:00:00Z",
                "hours_worked": 2,
                "comment": "worked",
                "time_category_id": "c1",
            }
        )["timeRecords"][0]
        assert record["comment"] == "worked"
        assert record["timeCategoryId"] == "c1"

    def test_omits_optional_fields_when_blank(self):
        record = time_record_body(
            {
                "member_id": MEMBER_ID,
                "date_of_work": "2026-08-03T00:00:00Z",
                "hours_worked": 2,
                "comment": "",
                "time_category_id": None,
            }
        )["timeRecords"][0]
        assert "comment" not in record
        assert "timeCategoryId" not in record


# ---- list_phases ----


class TestListPhases:
    @pytest.mark.asyncio
    async def test_success_and_scoping(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "data": [{"id": "ph1", "name": "Kickoff", "sortOrder": 1}],
                "metadata": {"total": 1, "offset": 0, "limit": 50},
            }
        )

        result = await guidecx.execute_action("list_phases", {"project_id": PROJECT_ID}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["phases"][0]["name"] == "Kickoff"
        assert fetch_path(mock_context).endswith("/phases")
        assert fetch_params(mock_context)["projectId"] == [PROJECT_ID]

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 500: boom")

        result = await guidecx.execute_action("list_phases", {"project_id": PROJECT_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "boom" in result.result.message


# ---- list_project_members ----


class TestListProjectMembers:
    @pytest.mark.asyncio
    async def test_uses_project_scoped_path(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action("list_project_members", {"project_id": PROJECT_ID}, mock_context)

        assert fetch_path(mock_context).endswith(f"/projects/{PROJECT_ID}/members")

    @pytest.mark.asyncio
    async def test_sends_filters(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action(
            "list_project_members",
            {"project_id": PROJECT_ID, "email": ["a@b.com"], "project_role": ["PROJECT_MANAGER"]},
            mock_context,
        )

        params = fetch_params(mock_context)
        assert params["email"] == ["a@b.com"]
        assert params["projectRole"] == ["PROJECT_MANAGER"]

    @pytest.mark.asyncio
    async def test_returns_members(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "data": [{"id": "m1", "email": "pm@example.com", "projectRole": "PROJECT_MANAGER"}],
                "metadata": {"total": 1, "offset": 0, "limit": 50},
            }
        )

        result = await guidecx.execute_action("list_project_members", {"project_id": PROJECT_ID}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["members"][0]["projectRole"] == "PROJECT_MANAGER"


# ---- remove_project_member ----


class TestRemoveProjectMember:
    @pytest.mark.asyncio
    async def test_sends_delete_to_member_path(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await guidecx.execute_action(
            "remove_project_member", {"project_id": PROJECT_ID, "member_id": MEMBER_ID}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data == {"removed": True, "member_id": MEMBER_ID}
        assert fetch_path(mock_context).endswith(f"/projects/{PROJECT_ID}/members/{MEMBER_ID}")
        assert fetch_kwargs(mock_context)["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 404: member not on project")

        result = await guidecx.execute_action(
            "remove_project_member", {"project_id": PROJECT_ID, "member_id": MISSING_ID}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not on project" in result.result.message


# ---- list_members / list_roles ----


class TestListMembers:
    @pytest.mark.asyncio
    async def test_sends_filters(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action(
            "list_members", {"email": ["a@b.com"], "status": ["ACTIVE"], "role": ["ADMIN"]}, mock_context
        )

        params = fetch_params(mock_context)
        assert params["email"] == ["a@b.com"]
        assert params["status"] == ["ACTIVE"]
        assert params["role"] == ["ADMIN"]
        assert fetch_path(mock_context).endswith("/members")

    @pytest.mark.asyncio
    async def test_returns_members(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "data": [{"id": "m1", "email": "a@b.com", "status": "ACTIVE"}],
                "metadata": {"total": 1, "limit": 50, "offset": 0},
            }
        )

        result = await guidecx.execute_action("list_members", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["members"][0]["email"] == "a@b.com"


class TestListRoles:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "data": [{"id": "r1", "name": "Admin", "category": "INTERNAL"}],
                "metadata": {"total": 1, "limit": 50, "offset": 0},
            }
        )

        result = await guidecx.execute_action("list_roles", {"name": "Admin"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["roles"][0]["category"] == "INTERNAL"
        assert fetch_params(mock_context)["name"] == ["Admin"]


# ---- webhooks ----


class TestListWebhooks:
    @pytest.mark.asyncio
    async def test_forwards_snake_case_include_disabled_as_string(self, mock_context):
        # This endpoint is the one place the API expects snake_case params, and
        # the SDK rejects bool query values, so the flag goes out as a string.
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action("list_webhooks", {"include_disabled": True}, mock_context)

        assert fetch_params(mock_context)["include_disabled"] == ["true"]

    @pytest.mark.asyncio
    async def test_include_disabled_false_is_still_sent(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action("list_webhooks", {"include_disabled": False}, mock_context)

        assert fetch_params(mock_context)["include_disabled"] == ["false"]

    @pytest.mark.asyncio
    async def test_omits_include_disabled_when_unset(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action("list_webhooks", {}, mock_context)

        assert "include_disabled" not in fetch_params(mock_context)

    @pytest.mark.asyncio
    async def test_returns_snake_case_fields(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "data": [{"id": "w1", "event_type": "task.updated", "url": "https://e.com"}],
                "metadata": {"total": 1, "limit": 50, "offset": 0},
            }
        )

        result = await guidecx.execute_action("list_webhooks", {}, mock_context)

        assert result.result.data["webhooks"][0]["event_type"] == "task.updated"


class TestUpsertWebhook:
    @pytest.mark.asyncio
    async def test_create_sends_camel_case_event_type(self, mock_context):
        # Request field is camelCase eventType; response field is snake_case.
        mock_context.fetch.return_value = ok({"data": [{"id": WEBHOOK_ID, "event_type": None}]})

        result = await guidecx.execute_action(
            "upsert_webhook", {"event_type": "task.updated", "url": "https://e.com/hook"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["webhook"]["id"] == WEBHOOK_ID
        kwargs = fetch_kwargs(mock_context)
        assert kwargs["method"] == "PATCH"
        assert kwargs["json"] == {"webhooks": [{"eventType": "task.updated", "url": "https://e.com/hook"}]}

    @pytest.mark.asyncio
    async def test_update_includes_id(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": WEBHOOK_ID}]})

        await guidecx.execute_action(
            "upsert_webhook",
            {"webhook_id": WEBHOOK_ID, "event_type": "task.updated", "url": "https://e.com/hook", "description": "d"},
            mock_context,
        )

        sent = fetch_kwargs(mock_context)["json"]["webhooks"][0]
        assert sent["id"] == WEBHOOK_ID
        assert sent["description"] == "d"

    @pytest.mark.asyncio
    async def test_empty_response_returns_error(self, mock_context):
        mock_context.fetch.return_value = ok({"data": []})

        result = await guidecx.execute_action(
            "upsert_webhook", {"event_type": "task.updated", "url": "https://e.com"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "no webhook record" in result.result.message

    @pytest.mark.asyncio
    async def test_invalid_event_type_rejected_by_schema(self, mock_context):
        # The enum is declared in config.json, so the SDK rejects bad values
        # before the handler runs and no request is made.
        result = await guidecx.execute_action(
            "upsert_webhook", {"event_type": "TASK_UPDATED_EVENT", "url": "https://e.com"}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


class TestDeleteWebhook:
    @pytest.mark.asyncio
    async def test_sends_delete(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await guidecx.execute_action("delete_webhook", {"webhook_id": WEBHOOK_ID}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {"deleted": True, "webhook_id": WEBHOOK_ID}
        assert fetch_path(mock_context).endswith(f"/webhooks/{WEBHOOK_ID}")
        assert fetch_kwargs(mock_context)["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 404: not found")

        result = await guidecx.execute_action("delete_webhook", {"webhook_id": MISSING_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- time tracking ----


class TestListTimeCategories:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "data": [{"id": "c1", "name": "Billable", "billable": True, "billableRate": 150}],
                "metadata": {"total": 1, "limit": 50, "offset": 0},
            }
        )

        result = await guidecx.execute_action("list_time_categories", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["time_categories"][0]["billable"] is True
        assert fetch_path(mock_context).endswith("/time-categories")


class TestListTimeRecords:
    @pytest.mark.asyncio
    async def test_sends_all_filters(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [], "metadata": {"total": 0}})

        await guidecx.execute_action(
            "list_time_records",
            {
                "project_id": PROJECT_ID,
                "task_id": TASK_ID,
                "member_id": ["m1"],
                "time_category_id": ["c1"],
                "worked_after": "2026-01-01T00:00:00Z",
                "worked_before": "2026-12-31T00:00:00Z",
            },
            mock_context,
        )

        params = fetch_params(mock_context)
        assert params["projectId"] == [PROJECT_ID]
        assert params["taskId"] == [TASK_ID]
        assert params["memberId"] == ["m1"]
        assert params["timeCategoryId"] == ["c1"]
        assert params["workedAfter"] == ["2026-01-01T00:00:00Z"]
        assert params["workedBefore"] == ["2026-12-31T00:00:00Z"]

    @pytest.mark.asyncio
    async def test_returns_records(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"data": [{"id": "tr1", "hoursWorked": 1.5}], "metadata": {"total": 1, "limit": 50, "offset": 0}}
        )

        result = await guidecx.execute_action("list_time_records", {}, mock_context)

        assert result.result.data["time_records"][0]["hoursWorked"] == 1.5


class TestLogTaskTime:
    @pytest.mark.asyncio
    async def test_posts_one_item_batch_to_task(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": "tr1", "hoursWorked": 0.5}]})

        result = await guidecx.execute_action(
            "log_task_time",
            {"task_id": TASK_ID, "member_id": MEMBER_ID, "hours_worked": 0.5, "date_of_work": "2026-08-03T00:00:00Z"},
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert result.result.data["time_record"]["id"] == "tr1"
        assert fetch_path(mock_context).endswith(f"/tasks/{TASK_ID}/time-records")
        kwargs = fetch_kwargs(mock_context)
        assert kwargs["method"] == "POST"
        assert kwargs["json"]["timeRecords"][0]["memberId"] == MEMBER_ID

    @pytest.mark.asyncio
    async def test_empty_response_returns_error(self, mock_context):
        mock_context.fetch.return_value = ok({"data": []})

        result = await guidecx.execute_action(
            "log_task_time",
            {"task_id": TASK_ID, "member_id": MEMBER_ID, "hours_worked": 1, "date_of_work": "2026-08-03T00:00:00Z"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert TASK_ID in result.result.message


class TestLogProjectTime:
    @pytest.mark.asyncio
    async def test_posts_one_item_batch_to_project(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": "tr2", "hoursWorked": 2}]})

        result = await guidecx.execute_action(
            "log_project_time",
            {
                "project_id": PROJECT_ID,
                "member_id": MEMBER_ID,
                "hours_worked": 2,
                "date_of_work": "2026-08-03T00:00:00Z",
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION
        assert fetch_path(mock_context).endswith(f"/projects/{PROJECT_ID}/time-records")
        assert fetch_kwargs(mock_context)["json"]["timeRecords"][0]["hoursWorked"] == 2

    @pytest.mark.asyncio
    async def test_missing_required_input_is_rejected(self, mock_context):
        # member_id is required in the schema, so the SDK rejects the call.
        result = await guidecx.execute_action(
            "log_project_time",
            {"project_id": PROJECT_ID, "hours_worked": 2, "date_of_work": "2026-08-03T00:00:00Z"},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


# ---- Structural-write helpers ----


class TestPlacementBody:
    def test_defaults_to_at_end(self):
        assert placement_body({}) == {"atEnd": True}

    def test_at_start(self):
        assert placement_body({"placement": "at_start"}) == {"atStart": True}

    def test_at_end(self):
        assert placement_body({"placement": "at_end"}) == {"atEnd": True}

    def test_unknown_value_falls_back_to_at_end(self):
        assert placement_body({"placement": "sideways"}) == {"atEnd": True}


# ---- create_project ----


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_minimal_create(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": PROJECT_ID, "name": "Acme"}]})

        result = await guidecx.execute_action("create_project", {"name": "Acme"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["project"]["id"] == PROJECT_ID
        assert fetch_path(mock_context).endswith("/projects")
        kwargs = fetch_kwargs(mock_context)
        assert kwargs["method"] == "PATCH"
        assert kwargs["json"] == {"projects": [{"name": "Acme"}]}

    @pytest.mark.asyncio
    async def test_existing_customer_is_referenced_by_id(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": PROJECT_ID}]})

        await guidecx.execute_action(
            "create_project", {"name": "Acme", "customer_id": CUSTOMER_ID, "customer_name": "ignored"}, mock_context
        )

        sent = fetch_kwargs(mock_context)["json"]["projects"][0]
        assert sent["customer"] == {"id": CUSTOMER_ID}

    @pytest.mark.asyncio
    async def test_inline_customer_is_created_from_name_and_domain(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": PROJECT_ID}]})

        await guidecx.execute_action(
            "create_project",
            {"name": "Acme", "customer_name": "Acme Co", "customer_domain": "acme.com"},
            mock_context,
        )

        sent = fetch_kwargs(mock_context)["json"]["projects"][0]
        assert sent["customer"] == {"name": "Acme Co", "domain": "acme.com"}

    @pytest.mark.asyncio
    async def test_customer_name_without_domain_is_rejected(self, mock_context):
        """The spec requires name and domain together when no id is given."""
        result = await guidecx.execute_action(
            "create_project", {"name": "Acme", "customer_name": "Acme Co"}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_customer_domain_without_name_is_rejected(self, mock_context):
        """Previously a lone domain was silently dropped instead of erroring."""
        result = await guidecx.execute_action(
            "create_project", {"name": "Acme", "customer_domain": "acme.com"}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_customer_id_still_allows_a_stray_name(self, mock_context):
        """The pairing rule only applies when customer_id is absent."""
        mock_context.fetch.return_value = ok({"data": [{"id": PROJECT_ID}]})

        result = await guidecx.execute_action(
            "create_project", {"name": "Acme", "customer_id": CUSTOMER_ID, "customer_name": "ignored"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert fetch_kwargs(mock_context)["json"]["projects"][0]["customer"] == {"id": CUSTOMER_ID}

    @pytest.mark.asyncio
    async def test_handler_rejects_half_a_customer_even_if_schema_is_bypassed(self, mock_context):
        """The handler repeats the check, so the contract does not rest on the schema alone."""
        from guidecx.guidecx import CreateProjectAction

        result = await CreateProjectAction().execute({"name": "Acme", "customer_name": "Acme Co"}, mock_context)

        assert isinstance(result, ActionError)
        assert "customer_domain" in result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_project_manager_becomes_internal_team_entry(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": PROJECT_ID}]})

        await guidecx.execute_action("create_project", {"name": "Acme", "project_manager_id": "m1"}, mock_context)

        sent = fetch_kwargs(mock_context)["json"]["projects"][0]
        assert sent["internalTeam"] == [{"id": "m1", "role": "PROJECT_MANAGER"}]

    @pytest.mark.asyncio
    async def test_customer_id_extracted_from_links(self, mock_context):
        mock_context.fetch.return_value = ok(
            {"data": [{"id": PROJECT_ID, "_links": {"customer": "/api/v3/customers/c9"}}]}
        )

        result = await guidecx.execute_action("create_project", {"name": "Acme"}, mock_context)

        assert result.result.data["customer_id"] == "c9"

    @pytest.mark.asyncio
    async def test_customer_id_is_none_without_a_link(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": PROJECT_ID, "_links": {}}]})

        result = await guidecx.execute_action("create_project", {"name": "Acme"}, mock_context)

        assert result.result.data["customer_id"] is None

    @pytest.mark.asyncio
    async def test_empty_response_returns_error(self, mock_context):
        mock_context.fetch.return_value = ok({"data": []})

        result = await guidecx.execute_action("create_project", {"name": "Acme"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "no project record" in result.result.message


# ---- update_project ----


class TestUpdateProject:
    @pytest.mark.asyncio
    async def test_sends_id_with_changed_fields(self, mock_context):
        # First fetch is the existence check, second is the upsert itself.
        mock_context.fetch.side_effect = [
            ok({"data": [{"id": PROJECT_ID}]}),
            ok({"data": [{"id": PROJECT_ID, "name": "New"}]}),
        ]

        result = await guidecx.execute_action(
            "update_project", {"project_id": PROJECT_ID, "name": "New", "cash_value": 100}, mock_context
        )

        assert result.type == ResultType.ACTION
        sent = fetch_kwargs(mock_context, 1)["json"]["projects"][0]
        assert sent["id"] == PROJECT_ID
        assert sent["name"] == "New"
        assert sent["cashValue"] == 100

    @pytest.mark.asyncio
    async def test_checks_the_project_exists_before_upserting(self, mock_context):
        """The pre-flight lookup filters on the exact ID and is sent first."""
        mock_context.fetch.side_effect = [
            ok({"data": [{"id": PROJECT_ID}]}),
            ok({"data": [{"id": PROJECT_ID, "name": "New"}]}),
        ]

        await guidecx.execute_action("update_project", {"project_id": PROJECT_ID, "name": "New"}, mock_context)

        assert mock_context.fetch.call_count == 2
        assert fetch_path(mock_context, 0).endswith("/projects")
        assert fetch_params(mock_context, 0) == {"id": [PROJECT_ID], "limit": ["1"]}
        assert fetch_kwargs(mock_context, 1)["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_unknown_project_id_is_refused_without_upserting(self, mock_context):
        """PATCH /projects is an upsert, so an unknown ID must not be sent."""
        mock_context.fetch.return_value = ok({"data": []})

        result = await guidecx.execute_action("update_project", {"project_id": MISSING_ID, "name": "New"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert MISSING_ID in result.result.message
        assert "upsert" in result.result.message
        # Only the lookup happened, no PATCH was sent.
        assert mock_context.fetch.call_count == 1
        assert all(call.kwargs.get("method") != "PATCH" for call in mock_context.fetch.call_args_list)

    @pytest.mark.asyncio
    async def test_id_mismatch_in_lookup_is_treated_as_missing(self, mock_context):
        """A record whose ID differs is not a match, even though the API returned one."""
        mock_context.fetch.return_value = ok({"data": [{"id": "some-other-project"}]})

        result = await guidecx.execute_action("update_project", {"project_id": PROJECT_ID, "name": "New"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert mock_context.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_no_fields_returns_error_without_calling_api(self, mock_context):
        result = await guidecx.execute_action("update_project", {"project_id": PROJECT_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "No update fields" in result.result.message
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_response_returns_error(self, mock_context):
        mock_context.fetch.side_effect = [ok({"data": [{"id": PROJECT_ID}]}), ok({"data": []})]

        result = await guidecx.execute_action("update_project", {"project_id": PROJECT_ID, "name": "x"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert PROJECT_ID in result.result.message


# ---- create_phase / create_milestone ----


class TestCreatePhase:
    @pytest.mark.asyncio
    async def test_posts_to_project_scoped_path_with_placement(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": "ph1", "name": "Phase"}]})

        result = await guidecx.execute_action(
            "create_phase", {"project_id": PROJECT_ID, "name": "Phase", "placement": "at_start"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert fetch_path(mock_context).endswith(f"/projects/{PROJECT_ID}/phases")
        assert fetch_kwargs(mock_context)["json"] == {
            "phases": [{"name": "Phase"}],
            "placement": {"atStart": True},
        }

    @pytest.mark.asyncio
    async def test_description_is_never_sent(self, mock_context):
        """Phases have no description field in the v3 API.

        phaseUpsertPhaseInput defines only id, name, templateId and position.
        The endpoint returns 200 for unknown fields and silently drops them, so
        forwarding a description would look like it worked while doing nothing.
        """
        mock_context.fetch.return_value = ok({"data": [{"id": "ph1"}]})

        result = await guidecx.execute_action(
            "create_phase", {"project_id": PROJECT_ID, "name": "Phase", "description": "<p>d</p>"}, mock_context
        )

        assert result.type == ResultType.ACTION
        sent = fetch_kwargs(mock_context)["json"]["phases"][0]
        assert "formattedDescription" not in sent
        assert "description" not in sent
        assert sent == {"name": "Phase"}

    @pytest.mark.asyncio
    async def test_description_is_not_in_the_input_schema(self):
        """The action must not advertise a field the API ignores."""
        import json
        import os

        config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        with open(config_path, encoding="utf-8") as handle:
            config = json.load(handle)

        properties = config["actions"]["create_phase"]["input_schema"]["properties"]
        assert "description" not in properties


class TestCreateMilestone:
    @pytest.mark.asyncio
    async def test_requires_phase_and_posts_to_project(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": "m1", "name": "MS"}]})

        result = await guidecx.execute_action(
            "create_milestone", {"project_id": PROJECT_ID, "phase_id": "ph1", "name": "MS"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert fetch_path(mock_context).endswith(f"/projects/{PROJECT_ID}/milestones")
        sent = fetch_kwargs(mock_context)["json"]["milestones"][0]
        assert sent == {"name": "MS", "phaseId": "ph1"}

    @pytest.mark.asyncio
    async def test_missing_phase_id_is_rejected(self, mock_context):
        result = await guidecx.execute_action(
            "create_milestone", {"project_id": PROJECT_ID, "name": "MS"}, mock_context
        )

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()


# ---- create_task ----


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_milestone_id_becomes_parent_id(self, mock_context):
        # GUIDEcx rejects a task whose parentId is not a milestone.
        mock_context.fetch.return_value = ok({"data": [{"id": "t1", "name": "T"}]})

        result = await guidecx.execute_action(
            "create_task", {"project_id": PROJECT_ID, "milestone_id": "m1", "name": "T"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert fetch_path(mock_context).endswith(f"/projects/{PROJECT_ID}/tasks")
        sent = fetch_kwargs(mock_context)["json"]["tasks"][0]
        assert sent["parentId"] == "m1"
        assert "milestone_id" not in sent

    @pytest.mark.asyncio
    async def test_maps_optional_fields(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": TASK_ID}]})

        await guidecx.execute_action(
            "create_task",
            {
                "project_id": PROJECT_ID,
                "milestone_id": "m1",
                "name": "T",
                "description": "<p>d</p>",
                "start_date": "2026-08-01T00:00:00Z",
                "end_date": "2026-08-09T00:00:00Z",
                "assignee_id": "u1",
                "priority": "HIGH",
                "responsibility": "CUSTOMER",
                "visibility": "HIDDEN",
                "estimated_hours": 3.5,
                "tags": ["a"],
            },
            mock_context,
        )

        sent = fetch_kwargs(mock_context)["json"]["tasks"][0]
        assert sent["formattedDescription"] == "<p>d</p>"
        assert sent["startDate"] == "2026-08-01T00:00:00Z"
        assert sent["endDate"] == "2026-08-09T00:00:00Z"
        assert sent["assigneeId"] == "u1"
        assert sent["priority"] == "HIGH"
        assert sent["responsibility"] == "CUSTOMER"
        assert sent["visibility"] == "HIDDEN"
        assert sent["estimatedHours"] == 3.5
        assert sent["tags"] == ["a"]

    @pytest.mark.asyncio
    async def test_missing_milestone_id_is_rejected(self, mock_context):
        result = await guidecx.execute_action("create_task", {"project_id": PROJECT_ID, "name": "T"}, mock_context)

        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_priority_is_rejected(self, mock_context):
        result = await guidecx.execute_action(
            "create_task",
            {"project_id": PROJECT_ID, "milestone_id": "m1", "name": "T", "priority": "URGENT"},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR


# ---- dependencies ----


class TestListDependencies:
    @pytest.mark.asyncio
    async def test_returns_list_and_count_without_pagination(self, mock_context):
        # /dependencies has no limit/offset and returns no metadata block.
        mock_context.fetch.return_value = ok({"data": [{"parentId": "a", "dependentId": "b"}]})

        result = await guidecx.execute_action("list_dependencies", {"project_id": PROJECT_ID}, mock_context)

        assert result.type == ResultType.ACTION
        data = result.result.data
        assert data["count"] == 1
        assert data["dependencies"][0]["parentId"] == "a"
        assert "has_more" not in data
        assert fetch_params(mock_context) == {"projectId": [PROJECT_ID]}

    @pytest.mark.asyncio
    async def test_sends_id_filters(self, mock_context):
        mock_context.fetch.return_value = ok({"data": []})

        await guidecx.execute_action("list_dependencies", {"parent_id": ["a"], "dependent_id": ["b"]}, mock_context)

        params = fetch_params(mock_context)
        assert params == {"parentId": ["a"], "dependentId": ["b"]}

    @pytest.mark.asyncio
    async def test_empty_result_is_a_success(self, mock_context):
        mock_context.fetch.return_value = ok({"data": []})

        result = await guidecx.execute_action("list_dependencies", {}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data == {"dependencies": [], "count": 0}


class TestAddDependency:
    @pytest.mark.asyncio
    async def test_posts_one_item_batch(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"parentId": "a", "dependentId": "b"}]})

        result = await guidecx.execute_action("add_dependency", {"parent_id": "a", "dependent_id": "b"}, mock_context)

        assert result.type == ResultType.ACTION
        assert result.result.data["dependency"]["parentId"] == "a"
        kwargs = fetch_kwargs(mock_context)
        assert kwargs["method"] == "POST"
        assert kwargs["json"] == {"dependencies": [{"parentId": "a", "dependentId": "b"}]}

    @pytest.mark.asyncio
    async def test_empty_response_returns_error(self, mock_context):
        mock_context.fetch.return_value = ok({"data": []})

        result = await guidecx.execute_action("add_dependency", {"parent_id": "a", "dependent_id": "b"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "no dependency record" in result.result.message


class TestRemoveDependency:
    @pytest.mark.asyncio
    async def test_identifies_dependency_by_both_ends_in_query(self, mock_context):
        # The delete takes query parameters, not a dependency ID in the path.
        mock_context.fetch.return_value = ok({})

        result = await guidecx.execute_action(
            "remove_dependency", {"parent_id": "a", "dependent_id": "b"}, mock_context
        )

        assert result.type == ResultType.ACTION
        assert result.result.data == {"removed": True, "parent_id": "a", "dependent_id": "b"}
        kwargs = fetch_kwargs(mock_context)
        assert kwargs["method"] == "DELETE"
        assert fetch_params(mock_context) == {"parentId": ["a"], "dependentId": ["b"]}

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 404: dependency not found")

        result = await guidecx.execute_action(
            "remove_dependency", {"parent_id": "a", "dependent_id": "b"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- prune_body vs prune ----


class TestPruneBody:
    def test_keeps_empty_list_unlike_prune(self):
        # An empty list in a query string means "no filter" and is dropped, but
        # in a request body it is how a caller clears a collection.
        assert prune_body({"tags": []}) == {"tags": []}
        assert prune({"tags": []}) == {}

    def test_drops_none_and_empty_string(self):
        assert prune_body({"a": None, "b": "", "c": "keep"}) == {"c": "keep"}

    def test_keeps_zero_and_false(self):
        assert prune_body({"hours": 0, "flag": False}) == {"hours": 0, "flag": False}

    def test_keeps_populated_list(self):
        assert prune_body({"tags": ["a"]}) == {"tags": ["a"]}


class TestClearTagsViaUpdateProject:
    """update_project sends the existence check first, so the upsert is call 1."""

    @staticmethod
    def upsert_responses(upsert_data):
        return [ok({"data": [{"id": PROJECT_ID}]}), ok({"data": upsert_data})]

    @pytest.mark.asyncio
    async def test_empty_tags_are_sent_so_tags_can_be_cleared(self, mock_context):
        # Regression: prune() stripped `tags: []` out of the body, which made
        # clearing a project's tags impossible. The API honours an empty array.
        mock_context.fetch.side_effect = self.upsert_responses([{"id": PROJECT_ID, "tags": []}])

        result = await guidecx.execute_action("update_project", {"project_id": PROJECT_ID, "tags": []}, mock_context)

        assert result.type == ResultType.ACTION
        sent = fetch_kwargs(mock_context, 1)["json"]["projects"][0]
        assert sent["tags"] == []
        assert sent["id"] == PROJECT_ID

    @pytest.mark.asyncio
    async def test_empty_tags_alone_counts_as_an_update(self, mock_context):
        # Previously this fell through to "No update fields provided" because
        # the only field had been pruned away.
        mock_context.fetch.side_effect = self.upsert_responses([{"id": PROJECT_ID}])

        result = await guidecx.execute_action("update_project", {"project_id": PROJECT_ID, "tags": []}, mock_context)

        assert result.type == ResultType.ACTION
        assert fetch_kwargs(mock_context, 1)["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_clearing_tags_alongside_another_field(self, mock_context):
        # Previously the rename succeeded while the tags were silently retained.
        mock_context.fetch.side_effect = self.upsert_responses([{"id": PROJECT_ID}])

        await guidecx.execute_action(
            "update_project", {"project_id": PROJECT_ID, "name": "New", "tags": []}, mock_context
        )

        sent = fetch_kwargs(mock_context, 1)["json"]["projects"][0]
        assert sent["name"] == "New"
        assert sent["tags"] == []

    @pytest.mark.asyncio
    async def test_omitting_tags_leaves_them_out_of_the_body(self, mock_context):
        # Omitted means "leave untouched", which is distinct from clearing.
        mock_context.fetch.side_effect = self.upsert_responses([{"id": PROJECT_ID}])

        await guidecx.execute_action("update_project", {"project_id": PROJECT_ID, "name": "New"}, mock_context)

        assert "tags" not in fetch_kwargs(mock_context, 1)["json"]["projects"][0]

    @pytest.mark.asyncio
    async def test_no_fields_still_errors(self, mock_context):
        result = await guidecx.execute_action("update_project", {"project_id": PROJECT_ID}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_tags_on_create_task_are_preserved(self, mock_context):
        mock_context.fetch.return_value = ok({"data": [{"id": TASK_ID}]})

        await guidecx.execute_action(
            "create_task", {"project_id": PROJECT_ID, "milestone_id": "m1", "name": "T", "tags": []}, mock_context
        )

        assert fetch_kwargs(mock_context)["json"]["tasks"][0]["tags"] == []
