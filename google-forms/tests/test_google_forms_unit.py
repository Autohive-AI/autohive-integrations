"""Unit tests for the Google Forms integration.

The integration uses Google's ``googleapiclient`` Python SDK directly rather
than ``context.fetch``, so we mock at the SDK boundary (``google_forms.build``)
to keep tests fast and offline. Every test below verifies that:

1. handlers return an ``ActionResult`` (success) or ``ActionError`` (failure),
2. snake_case inputs are translated to camelCase Forms-API params, and
3. batchUpdate requests are constructed with the correct shape for each
   question type — that's the part the Forms API is fussy about and the part
   the mocks can't catch at runtime.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from autohive_integrations_sdk import ActionError, ActionResult
from autohive_integrations_sdk.integration import ResultType

from google_forms import _resolve_append_index, build_credentials, google_forms

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_service(call_chain_result: Any = None) -> MagicMock:
    """Mock Forms service where any chain like
    ``service.forms().<method>(**kw).execute()`` returns ``call_chain_result``.
    Also wires the nested ``forms().responses()`` resource."""
    service = MagicMock(name="FormsService")
    leaf = MagicMock()
    leaf.execute.return_value = call_chain_result

    forms_resource = MagicMock()
    for method_name in ("create", "get", "batchUpdate", "setPublishSettings"):
        getattr(forms_resource, method_name).return_value = leaf

    responses_resource = MagicMock()
    for method_name in ("list", "get"):
        getattr(responses_resource, method_name).return_value = leaf

    forms_resource.responses.return_value = responses_resource
    service.forms.return_value = forms_resource
    return service


async def _invoke(
    action_name: str,
    inputs: Dict[str, Any],
    api_result: Any,
    context: MagicMock,
):
    """Run a handler with the Forms service mocked to return ``api_result``."""
    with patch("google_forms.build", return_value=_mock_service(api_result)):
        envelope = await google_forms.execute_action(action_name, inputs, context)
    return envelope


# ---------------------------------------------------------------------------
# Auth + helpers
# ---------------------------------------------------------------------------


class TestBuildCredentials:
    def test_returns_credentials_from_context(self, mock_context):
        creds = build_credentials(mock_context)
        assert creds.token == "test_access_token"  # nosec B105

    def test_raises_when_access_token_missing(self, make_context):
        ctx = make_context(auth={})
        with pytest.raises(ValueError, match="access_token"):
            build_credentials(ctx)

    def test_raises_when_credentials_missing(self, make_context):
        ctx = make_context(auth={"credentials": {}})
        with pytest.raises(ValueError, match="access_token"):
            build_credentials(ctx)


class TestAuthFailureBecomesActionError:
    """Missing credentials must surface as ``ActionError``, not a Lambda crash."""

    @pytest.mark.asyncio
    async def test_missing_access_token_returns_action_error(self, make_context):
        ctx = make_context(auth={})
        envelope = await _invoke("get_form", {"form_id": "f1"}, {}, ctx)
        assert envelope.type == ResultType.ACTION_ERROR
        assert "access_token" in envelope.result.message


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------


class TestCreateForm:
    @pytest.mark.asyncio
    async def test_happy_path_returns_published_form(self, mock_context):
        """Default behavior: the form is created with `unpublished=false` so
        the returned responder_uri accepts submissions immediately, both
        before and after Google's 2026-06-30 default-flip cutoff."""
        env = await _invoke(
            "create_form",
            {"title": "My Survey"},
            {
                "formId": "FORM123",
                "responderUri": "https://forms.gle/abc",
                "info": {"title": "My Survey"},
                "publishSettings": {"publishState": {"isPublished": True, "isAcceptingResponses": True}},
            },
            mock_context,
        )
        assert isinstance(env.result, ActionResult)
        assert env.result.data["result"] is True
        assert env.result.data["form_id"] == "FORM123"
        assert env.result.data["responder_uri"] == "https://forms.gle/abc"
        assert env.result.data["auto_published"] is True
        # publish_settings now comes off the create response, not a separate
        # API round-trip — confirm it surfaces through correctly.
        assert env.result.data["publish_settings"]["publishState"]["isPublished"] is True

    @pytest.mark.asyncio
    async def test_default_passes_unpublished_false(self, mock_context):
        """The query param is the single source of truth for publish state at
        creation time. Default = publish ⇒ unpublished=False."""
        service = _mock_service({"formId": "F1"})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action("create_form", {"title": "Hi"}, mock_context)
        call_kwargs = service.forms.return_value.create.call_args.kwargs
        assert call_kwargs["body"] == {"info": {"title": "Hi"}}
        assert call_kwargs["unpublished"] is False

    @pytest.mark.asyncio
    async def test_auto_publish_false_passes_unpublished_true(self, mock_context):
        """Opt-out path: drafts go in with unpublished=True so the form is
        created unpublished from the start — even during the transition
        window (today) where the default is still 'published'.

        Before this fix, auto_publish=false silently created a *published*
        form, contradicting the action's contract."""
        service = _mock_service({"formId": "F1"})
        with patch("google_forms.build", return_value=service):
            env = await google_forms.execute_action(
                "create_form",
                {"title": "Draft", "auto_publish": False},
                mock_context,
            )
        call_kwargs = service.forms.return_value.create.call_args.kwargs
        assert call_kwargs["unpublished"] is True
        # No separate publish step round-trip — the query param does the work.
        service.forms.return_value.setPublishSettings.assert_not_called()
        assert env.result.data["auto_published"] is False
        assert "publish_settings" not in env.result.data

    @pytest.mark.asyncio
    async def test_document_title_translated_to_camel_case(self, mock_context):
        service = _mock_service({"formId": "F1"})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "create_form",
                {"title": "Public Title", "document_title": "Internal Title"},
                mock_context,
            )
        body = service.forms.return_value.create.call_args.kwargs["body"]
        assert body["info"]["title"] == "Public Title"
        assert body["info"]["documentTitle"] == "Internal Title"

    @pytest.mark.asyncio
    async def test_create_exception_returns_action_error(self, mock_context):
        service = _mock_service(None)
        service.forms.return_value.create.return_value.execute.side_effect = RuntimeError("boom")
        with patch("google_forms.build", return_value=service):
            env = await google_forms.execute_action("create_form", {"title": "X"}, mock_context)
        assert env.type == ResultType.ACTION_ERROR
        assert "boom" in env.result.message

    @pytest.mark.asyncio
    async def test_auto_published_reflects_api_state_not_intent(self, mock_context):
        """auto_published must reflect what the API actually did, not just
        what the caller asked for. If we requested publish but the API
        response shows the form isn't published, report the truth."""
        env = await _invoke(
            "create_form",
            {"title": "X"},  # auto_publish defaults to True
            {
                "formId": "FORM_X",
                "publishSettings": {"publishState": {"isPublished": False}},
            },
            mock_context,
        )
        # Caller asked for publish, but the API came back saying "not
        # published". We report False, not True.
        assert env.result.data["auto_published"] is False
        assert "publish_settings" not in env.result.data

    @pytest.mark.asyncio
    async def test_auto_published_false_when_publish_settings_missing(self, mock_context):
        """If the API omits publishSettings entirely, treat publish state as
        unknown/false rather than assuming the caller's intent succeeded."""
        env = await _invoke(
            "create_form",
            {"title": "X"},
            {"formId": "FORM_X", "info": {"title": "X"}},
            mock_context,
        )
        assert env.result.data["form_id"] == "FORM_X"
        assert env.result.data["auto_published"] is False
        assert "publish_settings" not in env.result.data

    @pytest.mark.asyncio
    async def test_auto_published_false_when_form_id_missing(self, mock_context):
        """Defensive: if the create response somehow lacks a formId (today
        impossible without an exception, but guards against partial-success
        refactors), don't claim the form was published."""
        env = await _invoke(
            "create_form",
            {"title": "X"},
            {"info": {"title": "X"}},  # No formId in response
            mock_context,
        )
        assert env.result.data["form_id"] == ""
        assert env.result.data["auto_published"] is False
        assert "publish_settings" not in env.result.data


class TestGetForm:
    @pytest.mark.asyncio
    async def test_returns_form(self, mock_context):
        env = await _invoke(
            "get_form",
            {"form_id": "F1"},
            {"formId": "F1", "info": {"title": "T"}, "items": []},
            mock_context,
        )
        assert env.result.data["form"]["formId"] == "F1"

    @pytest.mark.asyncio
    async def test_passes_form_id(self, mock_context):
        service = _mock_service({"formId": "F1"})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action("get_form", {"form_id": "F1"}, mock_context)
        assert service.forms.return_value.get.call_args.kwargs["formId"] == "F1"


class TestUpdateFormInfo:
    @pytest.mark.asyncio
    async def test_title_only(self, mock_context):
        service = _mock_service({"form": {"info": {"title": "New"}}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "update_form_info",
                {"form_id": "F1", "title": "New"},
                mock_context,
            )
        body = service.forms.return_value.batchUpdate.call_args.kwargs["body"]
        assert body["requests"] == [{"updateFormInfo": {"info": {"title": "New"}, "updateMask": "title"}}]

    @pytest.mark.asyncio
    async def test_title_and_description(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "update_form_info",
                {"form_id": "F1", "title": "T", "description": "D"},
                mock_context,
            )
        req = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]
        assert req["updateFormInfo"]["info"] == {"title": "T", "description": "D"}
        assert req["updateFormInfo"]["updateMask"] == "title,description"

    @pytest.mark.asyncio
    async def test_rejects_empty_update(self, mock_context):
        """Neither title nor description supplied — fast-fail before hitting the API."""
        service = _mock_service(None)
        with patch("google_forms.build", return_value=service):
            env = await google_forms.execute_action(
                "update_form_info",
                {"form_id": "F1"},
                mock_context,
            )
        assert env.type == ResultType.ACTION_ERROR
        service.forms.return_value.batchUpdate.assert_not_called()


class TestSetPublishSettings:
    @pytest.mark.asyncio
    async def test_publish_only_defaults_accepting_to_match(self, mock_context):
        """Forms API rejects partial publishState updates: when caller passes
        only is_published, we must still set isAcceptingResponses on the body."""
        service = _mock_service({"publishState": {"isPublished": True}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "set_publish_settings",
                {"form_id": "F1", "is_published": True},
                mock_context,
            )
        body = service.forms.return_value.setPublishSettings.call_args.kwargs["body"]
        # Both fields present, both true (default mirrors is_published).
        assert body["publishSettings"]["publishState"] == {
            "isPublished": True,
            "isAcceptingResponses": True,
        }
        # Forms API docs only accept "publishState" or "*" for updateMask —
        # nested field paths aren't documented as valid even if they happen
        # to be accepted at runtime.
        assert body["updateMask"] == "publishState"

    @pytest.mark.asyncio
    async def test_unpublish_defaults_accepting_to_false(self, mock_context):
        service = _mock_service({})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "set_publish_settings",
                {"form_id": "F1", "is_published": False},
                mock_context,
            )
        body = service.forms.return_value.setPublishSettings.call_args.kwargs["body"]
        assert body["publishSettings"]["publishState"] == {
            "isPublished": False,
            "isAcceptingResponses": False,
        }

    @pytest.mark.asyncio
    async def test_unpublish_forces_accepting_to_false(self, mock_context):
        service = _mock_service({})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "set_publish_settings",
                {"form_id": "F1", "is_published": False, "is_accepting_responses": True},
                mock_context,
            )
        body = service.forms.return_value.setPublishSettings.call_args.kwargs["body"]
        assert body["publishSettings"]["publishState"] == {
            "isPublished": False,
            "isAcceptingResponses": False,
        }

    @pytest.mark.asyncio
    async def test_unwraps_publish_settings_from_api_envelope(self, mock_context):
        """Forms API returns ``{formId, publishSettings: {publishState: ...}}``.
        The action's ``publish_settings`` output must be the inner
        PublishSettings object, not the outer envelope."""
        api_response = {
            "formId": "F1",
            "publishSettings": {"publishState": {"isPublished": True, "isAcceptingResponses": True}},
        }
        service = _mock_service(api_response)
        with patch("google_forms.build", return_value=service):
            env = await google_forms.execute_action(
                "set_publish_settings",
                {"form_id": "F1", "is_published": True},
                mock_context,
            )
        ps = env.result.data["publish_settings"]
        # Consumers navigate ``publish_settings.publishState.isPublished`` —
        # no double-nested ``publishSettings.publishSettings`` layer.
        assert ps["publishState"]["isPublished"] is True
        assert "publishSettings" not in ps  # not double-wrapped

    @pytest.mark.asyncio
    async def test_publish_and_accepting_explicit(self, mock_context):
        """Edge case — form published but closed for new responses."""
        service = _mock_service({})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "set_publish_settings",
                {"form_id": "F1", "is_published": True, "is_accepting_responses": False},
                mock_context,
            )
        body = service.forms.return_value.setPublishSettings.call_args.kwargs["body"]
        assert body["publishSettings"]["publishState"] == {
            "isPublished": True,
            "isAcceptingResponses": False,
        }


# ---------------------------------------------------------------------------
# Question convenience wrappers — check the batchUpdate body shape
# ---------------------------------------------------------------------------


class TestAddTextQuestion:
    @pytest.mark.asyncio
    async def test_short_answer_default_appends_at_index_zero(self, mock_context):
        """When the caller omits index AND the form is empty, the resolved
        append index must be 0 — the Forms API rejects createItem requests
        without a numeric location.index."""
        service = _mock_service({"items": []})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_text_question",
                {"form_id": "F1", "title": "Your name?"},
                mock_context,
            )
        # forms.get was called to count items for append.
        service.forms.return_value.get.assert_called_once_with(formId="F1")
        req = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]
        item = req["createItem"]["item"]
        assert req["createItem"]["location"] == {"index": 0}
        assert item["title"] == "Your name?"
        assert item["questionItem"]["question"]["textQuestion"] == {"paragraph": False}
        assert item["questionItem"]["question"]["required"] is False

    @pytest.mark.asyncio
    async def test_appends_after_existing_items(self, mock_context):
        """Append must use the existing item count as the index — not 0."""
        service = _mock_service({"items": [{}, {}, {}]})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_text_question",
                {"form_id": "F1", "title": "Q4"},
                mock_context,
            )
        req = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]
        assert req["createItem"]["location"] == {"index": 3}

    @pytest.mark.asyncio
    async def test_explicit_index_skips_form_lookup(self, mock_context):
        """If the caller specifies an index, we should NOT do the extra
        forms.get round-trip."""
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_text_question",
                {"form_id": "F1", "title": "Q", "index": 5},
                mock_context,
            )
        service.forms.return_value.get.assert_not_called()
        req = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]
        assert req["createItem"]["location"] == {"index": 5}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "incoming_index, expected_index",
        [
            (1, 1),
            (1.0, 1),  # JSON number deserialized as float — SDK accepts as integer; handler coerces
            (0, 0),
        ],
    )
    async def test_index_coerced_to_int(self, mock_context, incoming_index, expected_index):
        """Forms API rejects non-integer location.index values (a float like
        1.0 would be forwarded as 1.0 and trigger HTTP 400). The handler
        coerces with int() defensively. Numeric strings like ``"1"`` are a
        different problem — the SDK's schema validation rejects them as
        VALIDATION_ERROR before the handler runs (see the test below)."""
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_text_question",
                {"form_id": "F1", "title": "Q", "index": incoming_index},
                mock_context,
            )
        req = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]
        loc = req["createItem"]["location"]
        assert loc == {"index": expected_index}
        assert type(loc["index"]) is int  # noqa: E721 — strict type check intentional

    @pytest.mark.asyncio
    async def test_non_integer_index_rejected_by_sdk_validation(self, mock_context):
        """Defense-in-depth check: the config.json schema declares ``index``
        as ``integer``, so the SDK rejects strings/garbage before the handler
        runs. Confirms callers see a clean validation error rather than a
        cryptic HTTP 400 from Forms API."""
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            env = await google_forms.execute_action(
                "add_text_question",
                {"form_id": "F1", "title": "Q", "index": "abc"},
                mock_context,
            )
        assert env.type == ResultType.VALIDATION_ERROR
        # Never reaches the handler — no batchUpdate call.
        service.forms.return_value.batchUpdate.assert_not_called()

    @pytest.mark.parametrize("incoming_index", [1.9, "2"])
    def test_resolve_append_index_rejects_non_integer_values(self, incoming_index):
        with pytest.raises(ValueError, match="index must be an integer"):
            _resolve_append_index(MagicMock(), "F1", incoming_index)

    @pytest.mark.asyncio
    async def test_paragraph_with_index_and_required(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_text_question",
                {
                    "form_id": "F1",
                    "title": "Tell us more",
                    "paragraph": True,
                    "required": True,
                    "index": 2,
                    "description": "Be specific.",
                },
                mock_context,
            )
        req = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]
        item = req["createItem"]["item"]
        assert req["createItem"]["location"] == {"index": 2}
        assert item["description"] == "Be specific."
        assert item["questionItem"]["question"]["textQuestion"] == {"paragraph": True}
        assert item["questionItem"]["question"]["required"] is True

    @pytest.mark.asyncio
    async def test_empty_description_is_preserved(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_text_question",
                {"form_id": "F1", "title": "Q", "description": "", "index": 0},
                mock_context,
            )
        item = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]["createItem"]["item"]
        assert item["description"] == ""


class TestAddMultipleChoiceQuestion:
    @pytest.mark.asyncio
    async def test_radio(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_multiple_choice_question",
                {
                    "form_id": "F1",
                    "title": "Pick one",
                    "type": "RADIO",
                    "options": ["A", "B", "C"],
                },
                mock_context,
            )
        item = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]["createItem"]["item"]
        cq = item["questionItem"]["question"]["choiceQuestion"]
        assert cq["type"] == "RADIO"
        assert cq["options"] == [{"value": "A"}, {"value": "B"}, {"value": "C"}]

    @pytest.mark.asyncio
    async def test_checkbox_with_shuffle(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_multiple_choice_question",
                {
                    "form_id": "F1",
                    "title": "Pick any",
                    "type": "CHECKBOX",
                    "options": ["X", "Y"],
                    "shuffle": True,
                    "required": True,
                },
                mock_context,
            )
        item = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]["createItem"]["item"]
        cq = item["questionItem"]["question"]["choiceQuestion"]
        assert cq["type"] == "CHECKBOX"
        assert cq["shuffle"] is True
        assert item["questionItem"]["question"]["required"] is True


class TestAddScaleQuestion:
    @pytest.mark.asyncio
    async def test_scale_with_labels(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_scale_question",
                {
                    "form_id": "F1",
                    "title": "Rate it",
                    "low": 1,
                    "high": 5,
                    "low_label": "Terrible",
                    "high_label": "Amazing",
                },
                mock_context,
            )
        item = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]["createItem"]["item"]
        sq = item["questionItem"]["question"]["scaleQuestion"]
        assert sq == {"low": 1, "high": 5, "lowLabel": "Terrible", "highLabel": "Amazing"}

    @pytest.mark.asyncio
    async def test_scale_without_labels(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_scale_question",
                {"form_id": "F1", "title": "0-10", "low": 0, "high": 10},
                mock_context,
            )
        sq = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]["createItem"]["item"][
            "questionItem"
        ]["question"]["scaleQuestion"]
        assert sq == {"low": 0, "high": 10}
        assert "lowLabel" not in sq
        assert "highLabel" not in sq

    @pytest.mark.asyncio
    async def test_empty_anchor_labels_are_preserved(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "add_scale_question",
                {"form_id": "F1", "title": "0-10", "low": 0, "high": 10, "low_label": "", "high_label": ""},
                mock_context,
            )
        sq = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]["createItem"]["item"][
            "questionItem"
        ]["question"]["scaleQuestion"]
        assert sq == {"low": 0, "high": 10, "lowLabel": "", "highLabel": ""}


class TestDeleteItem:
    @pytest.mark.asyncio
    async def test_delete_by_index(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "delete_item",
                {"form_id": "F1", "index": 3},
                mock_context,
            )
        req = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]
        assert req == {"deleteItem": {"location": {"index": 3}}}

    @pytest.mark.asyncio
    async def test_delete_index_normalizes_integer_float(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "delete_item",
                {"form_id": "F1", "index": 3.0},
                mock_context,
            )
        req = service.forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"][0]
        loc = req["deleteItem"]["location"]
        assert loc == {"index": 3}
        assert type(loc["index"]) is int  # noqa: E721 — strict type check intentional

    @pytest.mark.asyncio
    async def test_delete_index_rejects_fractional_float(self, mock_context):
        service = _mock_service({"form": {}})
        with patch("google_forms.build", return_value=service):
            env = await google_forms.execute_action(
                "delete_item",
                {"form_id": "F1", "index": 3.5},
                mock_context,
            )
        assert env.type == ResultType.VALIDATION_ERROR
        service.forms.return_value.batchUpdate.assert_not_called()


# ---------------------------------------------------------------------------
# Raw batchUpdate escape hatch
# ---------------------------------------------------------------------------


class TestBatchUpdateForm:
    @pytest.mark.asyncio
    async def test_passes_through_requests(self, mock_context):
        service = _mock_service({"replies": [{"createItem": {"itemId": "I1"}}]})
        custom_req = [{"createItem": {"item": {"title": "X"}, "location": {"index": 0}}}]
        with patch("google_forms.build", return_value=service):
            env = await google_forms.execute_action(
                "batch_update_form",
                {"form_id": "F1", "requests": custom_req},
                mock_context,
            )
        body = service.forms.return_value.batchUpdate.call_args.kwargs["body"]
        assert body["requests"] == custom_req
        assert body["includeFormInResponse"] is True
        assert env.result.data["replies"][0]["createItem"]["itemId"] == "I1"

    @pytest.mark.asyncio
    async def test_include_form_in_response_false(self, mock_context):
        service = _mock_service({"replies": []})
        with patch("google_forms.build", return_value=service):
            env = await google_forms.execute_action(
                "batch_update_form",
                {"form_id": "F1", "requests": [], "include_form_in_response": False},
                mock_context,
            )
        body = service.forms.return_value.batchUpdate.call_args.kwargs["body"]
        assert body["includeFormInResponse"] is False
        # No "form" key when the API didn't return one
        assert "form" not in env.result.data

    @pytest.mark.asyncio
    async def test_write_control_wired(self, mock_context):
        service = _mock_service({"replies": []})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "batch_update_form",
                {
                    "form_id": "F1",
                    "requests": [],
                    "write_control": {"requiredRevisionId": "rev-7"},
                },
                mock_context,
            )
        body = service.forms.return_value.batchUpdate.call_args.kwargs["body"]
        assert body["writeControl"] == {"requiredRevisionId": "rev-7"}


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class TestListResponses:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        env = await _invoke(
            "list_responses",
            {"form_id": "F1"},
            {"responses": [{"responseId": "r1"}], "nextPageToken": "tok"},
            mock_context,
        )
        assert env.result.data["responses"][0]["responseId"] == "r1"
        assert env.result.data["next_page_token"] == "tok"
        assert "nextPageToken" not in env.result.data

    @pytest.mark.asyncio
    async def test_optional_filters_wired(self, mock_context):
        service = _mock_service({"responses": []})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "list_responses",
                {
                    "form_id": "F1",
                    "page_size": 50,
                    "page_token": "tok",  # nosec B105 — pagination token, not a credential
                    "filter": "timestamp >= 2024-01-01T00:00:00Z",
                },
                mock_context,
            )
        kwargs = service.forms.return_value.responses.return_value.list.call_args.kwargs
        assert kwargs["formId"] == "F1"
        assert kwargs["pageSize"] == 50
        assert kwargs["pageToken"] == "tok"  # nosec B105
        assert kwargs["filter"] == "timestamp >= 2024-01-01T00:00:00Z"


class TestGetResponse:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_context):
        env = await _invoke(
            "get_response",
            {"form_id": "F1", "response_id": "r1"},
            {"responseId": "r1", "answers": {}},
            mock_context,
        )
        assert env.result.data["response"]["responseId"] == "r1"

    @pytest.mark.asyncio
    async def test_passes_both_ids(self, mock_context):
        service = _mock_service({"responseId": "r1"})
        with patch("google_forms.build", return_value=service):
            await google_forms.execute_action(
                "get_response",
                {"form_id": "F1", "response_id": "r1"},
                mock_context,
            )
        kwargs = service.forms.return_value.responses.return_value.get.call_args.kwargs
        assert kwargs == {"formId": "F1", "responseId": "r1"}


# ---------------------------------------------------------------------------
# Cross-cutting: every action must funnel exceptions through ActionError.
# This guards against a regression where a new action forgets the try/except.
# ---------------------------------------------------------------------------


class TestErrorContractAcrossActions:
    @pytest.mark.parametrize(
        "action, inputs, method_chain",
        [
            ("create_form", {"title": "X"}, ("forms", "create")),
            ("get_form", {"form_id": "F1"}, ("forms", "get")),
            ("update_form_info", {"form_id": "F1", "title": "T"}, ("forms", "batchUpdate")),
            (
                "set_publish_settings",
                {"form_id": "F1", "is_published": True},
                ("forms", "setPublishSettings"),
            ),
            (
                "add_text_question",
                {"form_id": "F1", "title": "Q", "index": 0},
                ("forms", "batchUpdate"),
            ),
            (
                "add_multiple_choice_question",
                {"form_id": "F1", "title": "Q", "type": "RADIO", "options": ["A"], "index": 0},
                ("forms", "batchUpdate"),
            ),
            (
                "add_scale_question",
                {"form_id": "F1", "title": "Q", "low": 1, "high": 5, "index": 0},
                ("forms", "batchUpdate"),
            ),
            ("delete_item", {"form_id": "F1", "index": 0}, ("forms", "batchUpdate")),
            ("batch_update_form", {"form_id": "F1", "requests": []}, ("forms", "batchUpdate")),
            ("list_responses", {"form_id": "F1"}, ("forms", "responses", "list")),
            ("get_response", {"form_id": "F1", "response_id": "R1"}, ("forms", "responses", "get")),
        ],
    )
    @pytest.mark.asyncio
    async def test_runtime_error_becomes_action_error(
        self,
        mock_context,
        action,
        inputs,
        method_chain,
    ):
        service = _mock_service(None)
        method = getattr(service, method_chain[0]).return_value
        for attr in method_chain[1:-1]:
            method = getattr(method, attr).return_value
        getattr(method, method_chain[-1]).return_value.execute.side_effect = RuntimeError("boom")
        with patch("google_forms.build", return_value=service):
            env = await google_forms.execute_action(action, inputs, mock_context)
        assert env.type == ResultType.ACTION_ERROR
        assert isinstance(env.result, ActionError)
        assert "boom" in env.result.message
