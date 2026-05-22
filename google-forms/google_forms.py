from autohive_integrations_sdk import (
    ActionError,
    ActionHandler,
    ActionResult,
    ExecutionContext,
    Integration,
)
from typing import Any, Dict, List
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

google_forms = Integration.load()


def build_credentials(context: ExecutionContext) -> Credentials:
    """Build Google credentials from ExecutionContext.

    Raises:
        ValueError if ``context.auth.credentials.access_token`` is missing — the
        caller wraps this in ``ActionError`` so the platform surfaces a clean
        auth error instead of a Lambda crash.
    """
    access_token = context.auth.get("credentials", {}).get("access_token", "")
    if not access_token:
        raise ValueError("Google Forms credentials missing — no access_token in context.auth")

    return Credentials(
        token=access_token,
        token_uri="https://oauth2.googleapis.com/token",  # nosec B106
    )


def build_forms_service(context: ExecutionContext):
    """Build a Google Forms v1 service object from the execution context."""
    credentials = build_credentials(context)
    # static_discovery=False — the Forms API isn't bundled with older client
    # versions; force googleapiclient to fetch the live discovery document.
    return build("forms", "v1", credentials=credentials, static_discovery=False)


def _normalize_index(index: Any) -> int:
    if isinstance(index, bool) or not (isinstance(index, int) or (isinstance(index, float) and index.is_integer())):
        raise ValueError("index must be an integer")
    return int(index)


def _resolve_append_index(service, form_id: str, index: Any) -> int:
    """Forms API requires a numeric ``location.index`` in [0, item_count]
    on every ``createItem`` request — omitting it returns HTTP 400. When the
    caller passes ``index=None`` (meaning "append to the end"), look up the
    current item count via ``forms.get`` and use that.

    Normalizes integer values to ``int`` to defend against JSON shapes the
    platform might forward (for example ``1.0``). Fractional floats, strings,
    and other non-integer values raise ``ValueError`` which surfaces as
    ``ActionError``.
    """
    if index is not None:
        return _normalize_index(index)
    form = service.forms().get(formId=form_id).execute()
    return len(form.get("items", []) or [])


def _run_batch_update(
    service,
    form_id: str,
    requests: List[Dict[str, Any]],
    include_form: bool = True,
) -> Dict[str, Any]:
    """Apply a batchUpdate and return the raw API response."""
    body: Dict[str, Any] = {"requests": requests, "includeFormInResponse": include_form}
    return service.forms().batchUpdate(formId=form_id, body=body).execute()


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------


@google_forms.action("create_form")
class CreateForm(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_forms_service(context)
            info: Dict[str, Any] = {"title": inputs["title"]}
            if inputs.get("document_title"):
                info["documentTitle"] = inputs["document_title"]

            # The Forms API exposes an `unpublished` query parameter on
            # forms.create that explicitly controls publish state at creation
            # time. Passing it directly is correct both before and after
            # Google's 2026-06-30 cutoff (when the default flips from
            # "published" to "unpublished") — no follow-up setPublishSettings
            # round-trip needed.
            # https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/create
            # https://developers.google.com/workspace/forms/api/guides/api-changes-to-google-forms
            auto_publish = inputs.get("auto_publish", True)

            result = service.forms().create(body={"info": info}, unpublished=(not auto_publish)).execute()

            form_id = result.get("formId", "")
            publish_settings = result.get("publishSettings")
            api_publish_state = publish_settings.get("publishState", {}) if isinstance(publish_settings, dict) else {}

            # auto_published reflects what actually happened, not just what the
            # caller asked for. This stays accurate if the handler is ever
            # refactored to allow partial-success returns (e.g. create
            # succeeded but a follow-up step failed): if there's no formId, or
            # the API does not explicitly report isPublished=true, we don't
            # claim the form was auto-published.
            auto_published = bool(form_id) and (api_publish_state.get("isPublished") is True)

            response_data = {
                "form": result,
                "form_id": form_id,
                "responder_uri": result.get("responderUri", ""),
                "auto_published": auto_published,
                "result": True,
            }
            if auto_published:
                # publish_settings is included on the Form resource so we
                # surface it directly — no separate API call.
                response_data["publish_settings"] = publish_settings

            return ActionResult(
                data=response_data,
                cost_usd=0.0,
            )

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))


@google_forms.action("get_form")
class GetForm(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_forms_service(context)
            result = service.forms().get(formId=inputs["form_id"]).execute()
            return ActionResult(data={"form": result, "result": True}, cost_usd=0.0)

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))


@google_forms.action("update_form_info")
class UpdateFormInfo(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            if "title" not in inputs and "description" not in inputs:
                return ActionError(message="At least one of title or description must be provided.")

            service = build_forms_service(context)

            info: Dict[str, Any] = {}
            update_fields: List[str] = []
            if "title" in inputs:
                info["title"] = inputs.get("title")
                update_fields.append("title")
            if "description" in inputs:
                info["description"] = inputs.get("description")
                update_fields.append("description")

            requests = [{"updateFormInfo": {"info": info, "updateMask": ",".join(update_fields)}}]
            result = _run_batch_update(service, inputs["form_id"], requests)

            return ActionResult(data={"form": result.get("form", {}), "result": True}, cost_usd=0.0)

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))


@google_forms.action("set_publish_settings")
class SetPublishSettings(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_forms_service(context)

            # Forms API rejects partial publishState updates — both fields must
            # be sent on every call. A published form accepts responses by
            # default; an unpublished one cannot accept responses, even if the
            # caller also passes is_accepting_responses=true.
            is_published = inputs["is_published"]
            is_accepting = inputs.get("is_accepting_responses", True) if is_published else False

            body = {
                "publishSettings": {
                    "publishState": {
                        "isPublished": is_published,
                        "isAcceptingResponses": is_accepting,
                    }
                },
                # Forms API docs only accept "publishState" or "*" for the
                # updateMask on setPublishSettings — nested field paths like
                # "publishState.isPublished" are not part of the documented
                # contract (they happen to be accepted today but aren't safe).
                "updateMask": "publishState",
            }
            result = service.forms().setPublishSettings(formId=inputs["form_id"], body=body).execute()

            # API returns ``{formId, publishSettings: {publishState: {...}}}``;
            # expose the inner PublishSettings object so consumers can navigate
            # ``publish_settings.publishState.isPublished`` directly.
            return ActionResult(
                data={"publish_settings": result.get("publishSettings", {}), "result": True},
                cost_usd=0.0,
            )

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))


# ---------------------------------------------------------------------------
# Question convenience wrappers
# ---------------------------------------------------------------------------


def _question_base(title: str, description: Any = None) -> Dict[str, Any]:
    """Build the common ``item`` envelope shared by every question type."""
    item: Dict[str, Any] = {"title": title}
    if description is not None:
        item["description"] = description
    return item


def _create_item_request(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    return {"createItem": {"item": item, "location": {"index": index}}}


@google_forms.action("add_text_question")
class AddTextQuestion(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_forms_service(context)

            item = _question_base(inputs["title"], inputs.get("description"))
            item["questionItem"] = {
                "question": {
                    "required": bool(inputs.get("required", False)),
                    "textQuestion": {"paragraph": bool(inputs.get("paragraph", False))},
                }
            }
            index = _resolve_append_index(service, inputs["form_id"], inputs.get("index"))
            requests = [_create_item_request(item, index)]
            result = _run_batch_update(service, inputs["form_id"], requests)

            return ActionResult(data={"form": result.get("form", {}), "result": True}, cost_usd=0.0)

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))


@google_forms.action("add_multiple_choice_question")
class AddMultipleChoiceQuestion(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_forms_service(context)

            options = [{"value": opt} for opt in inputs["options"]]
            choice_question: Dict[str, Any] = {
                "type": inputs["type"],
                "options": options,
            }
            if "shuffle" in inputs:
                choice_question["shuffle"] = inputs.get("shuffle")

            item = _question_base(inputs["title"], inputs.get("description"))
            item["questionItem"] = {
                "question": {
                    "required": bool(inputs.get("required", False)),
                    "choiceQuestion": choice_question,
                }
            }
            index = _resolve_append_index(service, inputs["form_id"], inputs.get("index"))
            requests = [_create_item_request(item, index)]
            result = _run_batch_update(service, inputs["form_id"], requests)

            return ActionResult(data={"form": result.get("form", {}), "result": True}, cost_usd=0.0)

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))


@google_forms.action("add_scale_question")
class AddScaleQuestion(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_forms_service(context)

            scale_question: Dict[str, Any] = {"low": inputs["low"], "high": inputs["high"]}
            if inputs.get("low_label") is not None:
                scale_question["lowLabel"] = inputs["low_label"]
            if inputs.get("high_label") is not None:
                scale_question["highLabel"] = inputs["high_label"]

            item = _question_base(inputs["title"], inputs.get("description"))
            item["questionItem"] = {
                "question": {
                    "required": bool(inputs.get("required", False)),
                    "scaleQuestion": scale_question,
                }
            }
            index = _resolve_append_index(service, inputs["form_id"], inputs.get("index"))
            requests = [_create_item_request(item, index)]
            result = _run_batch_update(service, inputs["form_id"], requests)

            return ActionResult(data={"form": result.get("form", {}), "result": True}, cost_usd=0.0)

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))


@google_forms.action("delete_item")
class DeleteItem(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_forms_service(context)
            requests = [{"deleteItem": {"location": {"index": _normalize_index(inputs["index"])}}}]
            result = _run_batch_update(service, inputs["form_id"], requests)
            return ActionResult(data={"form": result.get("form", {}), "result": True}, cost_usd=0.0)

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))


@google_forms.action("batch_update_form")
class BatchUpdateForm(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_forms_service(context)

            body: Dict[str, Any] = {
                "requests": inputs["requests"],
                "includeFormInResponse": inputs.get("include_form_in_response", True),
            }
            if "write_control" in inputs:
                body["writeControl"] = inputs.get("write_control")

            result = service.forms().batchUpdate(formId=inputs["form_id"], body=body).execute()

            response: Dict[str, Any] = {
                "replies": result.get("replies", []),
                "result": True,
            }
            if "form" in result:
                response["form"] = result["form"]

            return ActionResult(data=response, cost_usd=0.0)

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


@google_forms.action("list_responses")
class ListResponses(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_forms_service(context)

            request_params: Dict[str, Any] = {"formId": inputs["form_id"]}
            if "page_size" in inputs:
                request_params["pageSize"] = inputs.get("page_size")
            if "page_token" in inputs:
                request_params["pageToken"] = inputs.get("page_token")
            if "filter" in inputs:
                request_params["filter"] = inputs.get("filter")

            result = service.forms().responses().list(**request_params).execute()

            response: Dict[str, Any] = {
                "responses": result.get("responses", []),
                "result": True,
            }
            if "nextPageToken" in result:
                response["next_page_token"] = result["nextPageToken"]

            return ActionResult(data=response, cost_usd=0.0)

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))


@google_forms.action("get_response")
class GetResponse(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_forms_service(context)
            result = (
                service.forms().responses().get(formId=inputs["form_id"], responseId=inputs["response_id"]).execute()
            )
            return ActionResult(data={"response": result, "result": True}, cost_usd=0.0)

        except HttpError as e:
            return ActionError(message=f"Google Forms API error: {str(e)}")
        except Exception as e:
            return ActionError(message=str(e))
