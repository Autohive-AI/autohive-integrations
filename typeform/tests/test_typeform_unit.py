"""
Unit tests for the Typeform integration using mocked fetch (SDK 2.0.0).

Covers every action across all six domains (user, forms, responses, workspaces,
themes, images, webhooks) plus the rate-limit helper functions. Each action is
tested for: happy path, request verification (URL + method), error path
(ActionError), and the structured rate-limit retry path that this integration
deliberately preserves instead of converting to ActionError.
"""

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType, RateLimitError

from typeform.typeform import (
    typeform,
    create_rate_limit_response,
    is_rate_limit_error,
    MAX_RATE_LIMIT_RETRIES,
    FORM_READONLY_FIELDS,
    TYPEFORM_API_BASE_URL,
)

pytestmark = pytest.mark.unit


def ok(data, status=200):
    """Build a successful FetchResponse wrapping `data`."""
    return FetchResponse(status=status, headers={}, data=data)


def url_of(call):
    """Extract the request URL from a fetch call (positional or kwarg)."""
    return call.args[0] if call.args else call.kwargs.get("url", "")


# =============================================================================
# HELPERS — is_rate_limit_error
# =============================================================================


class TestIsRateLimitError:
    def test_sdk_rate_limit_error_uses_retry_after(self):
        err = RateLimitError(30, 429, "Rate limit exceeded", "")
        is_rl, retry_after = is_rate_limit_error(err)
        assert is_rl is True
        assert retry_after == 30

    def test_429_in_message_defaults_to_60(self):
        is_rl, retry_after = is_rate_limit_error(Exception("HTTP 429: Too Many Requests"))
        assert is_rl is True
        assert retry_after == 60

    def test_rate_limit_phrase_detected(self):
        is_rl, retry_after = is_rate_limit_error(Exception("Rate limit exceeded"))
        assert is_rl is True
        assert retry_after == 60

    def test_too_many_requests_phrase_detected(self):
        is_rl, _ = is_rate_limit_error(Exception("Too Many Requests"))
        assert is_rl is True

    def test_non_rate_limit_error(self):
        is_rl, retry_after = is_rate_limit_error(Exception("Connection timeout"))
        assert is_rl is False
        assert retry_after == 0


# =============================================================================
# HELPERS — create_rate_limit_response
# =============================================================================


class TestCreateRateLimitResponse:
    def test_has_all_contract_fields(self):
        result = create_rate_limit_response(
            retry_after_seconds=37,
            retry_attempt=0,
            action_name="list_forms",
            empty_data={"forms": [], "total_items": 0},
        )
        data = result.data
        for field in (
            "result",
            "error",
            "error_type",
            "retry_after_seconds",
            "retry_attempt",
            "max_retries",
            "can_retry",
            "retry_instructions",
        ):
            assert field in data
        assert data["result"] is False
        assert data["error_type"] == "rate_limit"
        assert data["retry_after_seconds"] == 37
        assert data["can_retry"] is True

    def test_empty_data_merged(self):
        result = create_rate_limit_response(retry_after_seconds=10, empty_data={"forms": [], "total_items": 0})
        assert result.data["forms"] == []
        assert result.data["total_items"] == 0

    def test_action_name_included(self):
        result = create_rate_limit_response(retry_after_seconds=10, action_name="get_form")
        assert result.data["action"] == "get_form"

    def test_action_name_omitted_when_blank(self):
        result = create_rate_limit_response(retry_after_seconds=10)
        assert "action" not in result.data

    def test_can_retry_false_at_max(self):
        result = create_rate_limit_response(retry_after_seconds=60, retry_attempt=MAX_RATE_LIMIT_RETRIES)
        assert result.data["can_retry"] is False
        assert "do not retry" in result.data["retry_instructions"].lower()

    def test_can_retry_true_below_max(self):
        result = create_rate_limit_response(retry_after_seconds=60, retry_attempt=MAX_RATE_LIMIT_RETRIES - 1)
        assert result.data["can_retry"] is True


# =============================================================================
# USER — get_current_user
# =============================================================================


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"user_id": "u1", "email": "a@b.com", "alias": "me"})
        result = await typeform.execute_action("get_current_user", {}, mock_context)
        assert result.result.data["result"] is True
        assert result.result.data["user"]["email"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"user_id": "u1"})
        await typeform.execute_action("get_current_user", {}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/me"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Boom")
        result = await typeform.execute_action("get_current_user", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "Boom" in result.result.message

    @pytest.mark.asyncio
    async def test_rate_limit_returns_structured_result(self, mock_context):
        mock_context.fetch.side_effect = RateLimitError(45, 429, "Rate limit exceeded", "")
        result = await typeform.execute_action("get_current_user", {}, mock_context)
        # Rate-limit path is intentionally a structured ActionResult, not ActionError.
        assert result.type != ResultType.ACTION_ERROR
        data = result.result.data
        assert data["error_type"] == "rate_limit"
        assert data["retry_after_seconds"] == 45
        assert data["can_retry"] is True


# =============================================================================
# FORMS
# =============================================================================


class TestListForms:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"items": [{"id": "f1"}, {"id": "f2"}], "total_items": 2})
        result = await typeform.execute_action("list_forms", {}, mock_context)
        data = result.result.data
        assert data["result"] is True
        assert len(data["forms"]) == 2
        assert data["total_items"] == 2

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action("list_forms", {}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/forms"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_filters_forwarded_as_params(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action(
            "list_forms", {"workspace_id": "w1", "search": "abc", "page": 2, "page_size": 50}, mock_context
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params == {"workspace_id": "w1", "search": "abc", "page": 2, "page_size": 50}

    @pytest.mark.asyncio
    async def test_no_params_sends_none(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action("list_forms", {}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"] is None

    @pytest.mark.asyncio
    async def test_empty_when_items_missing(self, mock_context):
        mock_context.fetch.return_value = ok({})
        result = await typeform.execute_action("list_forms", {}, mock_context)
        assert result.result.data["forms"] == []
        assert result.result.data["total_items"] == 0

    @pytest.mark.asyncio
    async def test_non_dict_body_yields_empty(self, mock_context):
        mock_context.fetch.return_value = ok([1, 2, 3])
        result = await typeform.execute_action("list_forms", {}, mock_context)
        assert result.result.data["forms"] == []

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("network down")
        result = await typeform.execute_action("list_forms", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "network down" in result.result.message

    @pytest.mark.asyncio
    async def test_rate_limit_structured(self, mock_context):
        mock_context.fetch.side_effect = Exception("HTTP 429: Too Many Requests")
        result = await typeform.execute_action("list_forms", {}, mock_context)
        assert result.result.data["error_type"] == "rate_limit"
        assert result.result.data["forms"] == []


class TestGetForm:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "f1", "title": "My Form"})
        result = await typeform.execute_action("get_form", {"form_id": "f1"}, mock_context)
        assert result.result.data["result"] is True
        assert result.result.data["form"]["title"] == "My Form"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "f1"})
        await typeform.execute_action("get_form", {"form_id": "f1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/forms/f1"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_missing_form_id_is_validation_error(self, mock_context):
        result = await typeform.execute_action("get_form", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("404 not found")
        result = await typeform.execute_action("get_form", {"form_id": "f1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "404" in result.result.message


class TestCreateForm:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "new", "title": "T"})
        result = await typeform.execute_action("create_form", {"title": "T"}, mock_context)
        assert result.result.data["result"] is True
        assert result.result.data["form"]["id"] == "new"

    @pytest.mark.asyncio
    async def test_request_url_method_and_title(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "new"})
        await typeform.execute_action("create_form", {"title": "T"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/forms"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"]["title"] == "T"

    @pytest.mark.asyncio
    async def test_optional_fields_built_into_body(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "new"})
        await typeform.execute_action(
            "create_form",
            {
                "title": "T",
                "workspace_id": "w1",
                "theme_id": "t1",
                "fields": [{"type": "short_text"}],
                "settings": {"is_public": True},
            },
            mock_context,
        )
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["workspace"]["href"].endswith("/workspaces/w1")
        assert body["theme"]["href"].endswith("/themes/t1")
        assert body["fields"] == [{"type": "short_text"}]
        assert body["settings"] == {"is_public": True}

    @pytest.mark.asyncio
    async def test_missing_title_is_validation_error(self, mock_context):
        result = await typeform.execute_action("create_form", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR
        mock_context.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("bad request")
        result = await typeform.execute_action("create_form", {"title": "T"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestUpdateForm:
    @pytest.mark.asyncio
    async def test_happy_path_fetches_then_puts(self, mock_context):
        mock_context.fetch.side_effect = [
            ok({"id": "f1", "title": "Old", "fields": [{"id": "q1"}], "_links": {"x": 1}}),
            ok({"id": "f1", "title": "New"}),
        ]
        result = await typeform.execute_action("update_form", {"form_id": "f1", "title": "New"}, mock_context)
        assert result.result.data["result"] is True
        assert result.result.data["form"]["title"] == "New"
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_readonly_fields_stripped_from_put_body(self, mock_context):
        existing = {k: "x" for k in FORM_READONLY_FIELDS}
        existing.update({"title": "Old", "fields": [{"id": "q1"}]})
        mock_context.fetch.side_effect = [ok(existing), ok({"id": "f1"})]
        await typeform.execute_action("update_form", {"form_id": "f1", "title": "New"}, mock_context)
        put_call = mock_context.fetch.call_args_list[1]
        body = put_call.kwargs["json"]
        assert put_call.kwargs["method"] == "PUT"
        for ro in FORM_READONLY_FIELDS:
            assert ro not in body
        assert body["title"] == "New"  # input override applied
        assert body["fields"] == [{"id": "q1"}]  # preserved from existing

    @pytest.mark.asyncio
    async def test_error_on_first_fetch_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("cannot read form")
        result = await typeform.execute_action("update_form", {"form_id": "f1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
        assert "cannot read form" in result.result.message

    @pytest.mark.asyncio
    async def test_missing_form_id_is_validation_error(self, mock_context):
        result = await typeform.execute_action("update_form", {"title": "x"}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_non_dict_existing_form_returns_action_error(self, mock_context):
        # v2 fetch may yield non-dict data (e.g. empty body -> None); guard before .items()
        mock_context.fetch.return_value = ok(None)
        result = await typeform.execute_action("update_form", {"form_id": "f1", "title": "x"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_rate_limit_on_fetch_returns_structured_result(self, mock_context):
        mock_context.fetch.side_effect = RateLimitError(50, 429, "Rate limit exceeded", "")
        result = await typeform.execute_action("update_form", {"form_id": "f1", "title": "x"}, mock_context)
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["error_type"] == "rate_limit"
        assert result.result.data["retry_after_seconds"] == 50


class TestDeleteForm:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        result = await typeform.execute_action("delete_form", {"form_id": "f1"}, mock_context)
        assert result.result.data["deleted"] is True
        assert result.result.data["result"] is True

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        await typeform.execute_action("delete_form", {"form_id": "f1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/forms/f1"
        assert call.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("forbidden")
        result = await typeform.execute_action("delete_form", {"form_id": "f1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# RESPONSES
# =============================================================================


class TestListResponses:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"items": [{"response_id": "r1"}], "total_items": 1, "page_count": 1})
        result = await typeform.execute_action("list_responses", {"form_id": "f1"}, mock_context)
        data = result.result.data
        assert data["result"] is True
        assert data["responses"][0]["response_id"] == "r1"
        assert data["total_items"] == 1
        assert data["page_count"] == 1

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action("list_responses", {"form_id": "f1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/forms/f1/responses"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_completed_bool_stringified_lowercase(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action(
            "list_responses", {"form_id": "f1", "completed": True, "page_size": 25}, mock_context
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["completed"] == "true"
        assert params["page_size"] == 25

    @pytest.mark.asyncio
    async def test_text_params_forwarded(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action(
            "list_responses", {"form_id": "f1", "since": "2024-01-01", "sort": "submitted_at,desc"}, mock_context
        )
        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["since"] == "2024-01-01"
        assert params["sort"] == "submitted_at,desc"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("list_responses", {"form_id": "f1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestDeleteResponses:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        result = await typeform.execute_action(
            "delete_responses", {"form_id": "f1", "included_response_ids": "r1,r2"}, mock_context
        )
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_request_params_and_method(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        await typeform.execute_action(
            "delete_responses", {"form_id": "f1", "included_response_ids": "r1,r2"}, mock_context
        )
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/forms/f1/responses"
        assert call.kwargs["method"] == "DELETE"
        assert call.kwargs["params"]["included_response_ids"] == "r1,r2"

    @pytest.mark.asyncio
    async def test_missing_required_is_validation_error(self, mock_context):
        result = await typeform.execute_action("delete_responses", {"form_id": "f1"}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action(
            "delete_responses", {"form_id": "f1", "included_response_ids": "r1"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# WORKSPACES
# =============================================================================


class TestListWorkspaces:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"items": [{"id": "w1"}], "total_items": 1})
        result = await typeform.execute_action("list_workspaces", {}, mock_context)
        assert result.result.data["workspaces"][0]["id"] == "w1"
        assert result.result.data["total_items"] == 1

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action("list_workspaces", {}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/workspaces"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_total_items_defaults_to_len(self, mock_context):
        mock_context.fetch.return_value = ok({"items": [{"id": "w1"}, {"id": "w2"}]})
        result = await typeform.execute_action("list_workspaces", {}, mock_context)
        assert result.result.data["total_items"] == 2

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("list_workspaces", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetWorkspace:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "w1", "name": "Main"})
        result = await typeform.execute_action("get_workspace", {"workspace_id": "w1"}, mock_context)
        assert result.result.data["workspace"]["name"] == "Main"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "w1"})
        await typeform.execute_action("get_workspace", {"workspace_id": "w1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/workspaces/w1"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("get_workspace", {"workspace_id": "w1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateWorkspace:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "w_new", "name": "New"})
        result = await typeform.execute_action("create_workspace", {"name": "New"}, mock_context)
        assert result.result.data["workspace"]["id"] == "w_new"

    @pytest.mark.asyncio
    async def test_request_url_method_and_body(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "w_new"})
        await typeform.execute_action("create_workspace", {"name": "New"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/workspaces"
        assert call.kwargs["method"] == "POST"
        assert call.kwargs["json"] == {"name": "New"}

    @pytest.mark.asyncio
    async def test_missing_name_is_validation_error(self, mock_context):
        result = await typeform.execute_action("create_workspace", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("create_workspace", {"name": "New"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestUpdateWorkspace:
    @pytest.mark.asyncio
    async def test_happy_path_patches_then_gets(self, mock_context):
        mock_context.fetch.side_effect = [ok(None, status=204), ok({"id": "w1", "name": "Renamed"})]
        result = await typeform.execute_action(
            "update_workspace", {"workspace_id": "w1", "name": "Renamed"}, mock_context
        )
        assert result.result.data["workspace"]["name"] == "Renamed"
        assert mock_context.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_patch_uses_json_patch_body(self, mock_context):
        mock_context.fetch.side_effect = [ok(None, status=204), ok({"id": "w1"})]
        await typeform.execute_action("update_workspace", {"workspace_id": "w1", "name": "Renamed"}, mock_context)
        patch_call = mock_context.fetch.call_args_list[0]
        assert patch_call.kwargs["method"] == "PATCH"
        assert patch_call.kwargs["json"] == [{"op": "replace", "path": "/name", "value": "Renamed"}]

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action(
            "update_workspace", {"workspace_id": "w1", "name": "Renamed"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_non_dict_refetch_returns_action_error(self, mock_context):
        # PATCH 204 then GET yields a non-dict body -> guard returns ActionError, not a None workspace
        mock_context.fetch.side_effect = [ok(None, status=204), ok(None)]
        result = await typeform.execute_action(
            "update_workspace", {"workspace_id": "w1", "name": "Renamed"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR

    @pytest.mark.asyncio
    async def test_rate_limit_on_patch_returns_structured_result(self, mock_context):
        mock_context.fetch.side_effect = RateLimitError(50, 429, "Rate limit exceeded", "")
        result = await typeform.execute_action(
            "update_workspace", {"workspace_id": "w1", "name": "Renamed"}, mock_context
        )
        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["error_type"] == "rate_limit"


class TestDeleteWorkspace:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        result = await typeform.execute_action("delete_workspace", {"workspace_id": "w1"}, mock_context)
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        await typeform.execute_action("delete_workspace", {"workspace_id": "w1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/workspaces/w1"
        assert call.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("delete_workspace", {"workspace_id": "w1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# THEMES
# =============================================================================


class TestListThemes:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"items": [{"id": "t1"}], "total_items": 1})
        result = await typeform.execute_action("list_themes", {}, mock_context)
        assert result.result.data["themes"][0]["id"] == "t1"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action("list_themes", {}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/themes"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_pagination_params_forwarded(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action("list_themes", {"page": 1, "page_size": 10}, mock_context)
        assert mock_context.fetch.call_args.kwargs["params"] == {"page": 1, "page_size": 10}

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("list_themes", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetTheme:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "t1", "name": "Dark"})
        result = await typeform.execute_action("get_theme", {"theme_id": "t1"}, mock_context)
        assert result.result.data["theme"]["name"] == "Dark"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "t1"})
        await typeform.execute_action("get_theme", {"theme_id": "t1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/themes/t1"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("get_theme", {"theme_id": "t1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateTheme:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "t_new", "name": "Brand"})
        result = await typeform.execute_action("create_theme", {"name": "Brand"}, mock_context)
        assert result.result.data["theme"]["id"] == "t_new"

    @pytest.mark.asyncio
    async def test_optional_fields_in_body(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "t_new"})
        await typeform.execute_action(
            "create_theme",
            {"name": "Brand", "colors": {"button": "#fff"}, "font": "Arial", "has_transparent_button": False},
            mock_context,
        )
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["name"] == "Brand"
        assert body["colors"] == {"button": "#fff"}
        assert body["font"] == "Arial"
        assert body["has_transparent_button"] is False

    @pytest.mark.asyncio
    async def test_missing_name_is_validation_error(self, mock_context):
        result = await typeform.execute_action("create_theme", {}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("create_theme", {"name": "Brand"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestDeleteTheme:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        result = await typeform.execute_action("delete_theme", {"theme_id": "t1"}, mock_context)
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        await typeform.execute_action("delete_theme", {"theme_id": "t1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/themes/t1"
        assert call.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("delete_theme", {"theme_id": "t1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# IMAGES
# =============================================================================


class TestListImages:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"items": [{"id": "i1"}], "total_items": 1})
        result = await typeform.execute_action("list_images", {}, mock_context)
        assert result.result.data["images"][0]["id"] == "i1"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action("list_images", {}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/images"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("list_images", {}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetImage:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "i1", "file_name": "logo.png"})
        result = await typeform.execute_action("get_image", {"image_id": "i1"}, mock_context)
        assert result.result.data["image"]["file_name"] == "logo.png"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "i1"})
        await typeform.execute_action("get_image", {"image_id": "i1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/images/i1"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("get_image", {"image_id": "i1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestDeleteImage:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        result = await typeform.execute_action("delete_image", {"image_id": "i1"}, mock_context)
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        await typeform.execute_action("delete_image", {"image_id": "i1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/images/i1"
        assert call.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("delete_image", {"image_id": "i1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


# =============================================================================
# WEBHOOKS
# =============================================================================


class TestListWebhooks:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"items": [{"tag": "wh1"}]})
        result = await typeform.execute_action("list_webhooks", {"form_id": "f1"}, mock_context)
        assert result.result.data["webhooks"][0]["tag"] == "wh1"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"items": []})
        await typeform.execute_action("list_webhooks", {"form_id": "f1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/forms/f1/webhooks"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_empty_when_items_missing(self, mock_context):
        mock_context.fetch.return_value = ok({})
        result = await typeform.execute_action("list_webhooks", {"form_id": "f1"}, mock_context)
        assert result.result.data["webhooks"] == []

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("list_webhooks", {"form_id": "f1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestGetWebhook:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"tag": "wh1", "url": "https://x.com/hook"})
        result = await typeform.execute_action("get_webhook", {"form_id": "f1", "tag": "wh1"}, mock_context)
        assert result.result.data["webhook"]["url"] == "https://x.com/hook"

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok({"tag": "wh1"})
        await typeform.execute_action("get_webhook", {"form_id": "f1", "tag": "wh1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/forms/f1/webhooks/wh1"
        assert call.kwargs["method"] == "GET"

    @pytest.mark.asyncio
    async def test_missing_tag_is_validation_error(self, mock_context):
        result = await typeform.execute_action("get_webhook", {"form_id": "f1"}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("get_webhook", {"form_id": "f1", "tag": "wh1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR


class TestCreateWebhook:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok({"tag": "wh1", "url": "https://x.com/hook", "enabled": True})
        result = await typeform.execute_action(
            "create_webhook", {"form_id": "f1", "tag": "wh1", "url": "https://x.com/hook"}, mock_context
        )
        assert result.result.data["webhook"]["tag"] == "wh1"

    @pytest.mark.asyncio
    async def test_request_url_method_and_body(self, mock_context):
        mock_context.fetch.return_value = ok({"tag": "wh1"})
        await typeform.execute_action(
            "create_webhook",
            {"form_id": "f1", "tag": "wh1", "url": "https://x.com/hook", "enabled": True, "secret": "s3cr3t"},  # nosec B105
            mock_context,
        )
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/forms/f1/webhooks/wh1"
        assert call.kwargs["method"] == "PUT"
        body = call.kwargs["json"]
        assert body["url"] == "https://x.com/hook"
        assert body["enabled"] is True
        assert body["secret"] == "s3cr3t"

    @pytest.mark.asyncio
    async def test_missing_url_is_validation_error(self, mock_context):
        result = await typeform.execute_action("create_webhook", {"form_id": "f1", "tag": "wh1"}, mock_context)
        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action(
            "create_webhook", {"form_id": "f1", "tag": "wh1", "url": "https://x.com/hook"}, mock_context
        )
        assert result.type == ResultType.ACTION_ERROR


class TestDeleteWebhook:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        result = await typeform.execute_action("delete_webhook", {"form_id": "f1", "tag": "wh1"}, mock_context)
        assert result.result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_request_url_and_method(self, mock_context):
        mock_context.fetch.return_value = ok(None, status=204)
        await typeform.execute_action("delete_webhook", {"form_id": "f1", "tag": "wh1"}, mock_context)
        call = mock_context.fetch.call_args
        assert url_of(call) == f"{TYPEFORM_API_BASE_URL}/forms/f1/webhooks/wh1"
        assert call.kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")
        result = await typeform.execute_action("delete_webhook", {"form_id": "f1", "tag": "wh1"}, mock_context)
        assert result.type == ResultType.ACTION_ERROR
