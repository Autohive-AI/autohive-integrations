import time
from datetime import datetime, timezone
from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Any, Dict


def _to_epoch_millis(due_date: str) -> int:
    dt = datetime.fromisoformat(due_date)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


lumin_pdf = Integration.load()

BASE_URL = "https://api.luminpdf.com/v1"


_VALID_LIMITS = (10, 25, 50)


def _clamp_limit(limit: int) -> int:
    """Round limit to the nearest value accepted by the Lumin API (10, 25, or 50)."""
    return min(_VALID_LIMITS, key=lambda v: abs(v - limit))


def _auth_headers(context: ExecutionContext, api_version: str = "") -> Dict[str, str]:
    auth = context.auth or {}
    api_key = auth.get("api_key") or auth.get("credentials", {}).get("api_key")
    headers = {}
    if api_key:
        headers["X-API-KEY"] = api_key
    if api_version:
        headers["X-Lumin-API-Version"] = api_version
    return headers


def _raise_for_status(response: Any) -> None:
    if response.status >= 400:
        data = response.data or {}
        msg = data.get("error_message") or data.get("message") or f"HTTP {response.status}"
        raise ValueError(msg)


# ---- User & Workspace ----


@lumin_pdf.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            response = await context.fetch(f"{BASE_URL}/user/info", method="GET", headers=_auth_headers(context))
            _raise_for_status(response)
            return ActionResult(data={"result": True, "user": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("get_workspace")
class GetWorkspaceAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            response = await context.fetch(
                f"{BASE_URL}/workspaces/info",
                method="GET",
                headers=_auth_headers(context),
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "workspace": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("list_workspace_members")
class ListWorkspaceMembersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            has_page = inputs.get("page") is not None
            has_limit = inputs.get("limit") is not None
            params: Dict[str, Any] = {}
            if has_page or has_limit:
                params["page"] = int(inputs["page"]) if has_page else 1
                params["limit"] = _clamp_limit(int(inputs["limit"])) if has_limit else 10
            response = await context.fetch(
                f"{BASE_URL}/workspaces/members",
                method="GET",
                headers=_auth_headers(context),
                params=params,
            )
            _raise_for_status(response)
            data = response.data
            members = data if isinstance(data, list) else data.get("data", data.get("members", []))
            return ActionResult(data={"result": True, "members": members}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Templates ----


@lumin_pdf.action("list_templates")
class ListTemplatesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            has_page = inputs.get("page") is not None
            has_limit = inputs.get("limit") is not None
            params: Dict[str, Any] = {}
            if has_page or has_limit:
                params["page"] = int(inputs["page"]) if has_page else 1
                params["limit"] = _clamp_limit(int(inputs["limit"])) if has_limit else 10
            response = await context.fetch(
                f"{BASE_URL}/templates",
                method="GET",
                headers=_auth_headers(context, api_version="1.1"),
                params=params,
            )
            _raise_for_status(response)
            data = response.data
            templates = data if isinstance(data, list) else data.get("data", data.get("templates", []))
            return ActionResult(data={"result": True, "templates": templates}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("get_template")
class GetTemplateAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            template_id = inputs["template_id"]
            response = await context.fetch(
                f"{BASE_URL}/templates/{template_id}",
                method="GET",
                headers=_auth_headers(context, api_version="1.1"),
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "template": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


# ---- Signature Requests ----


@lumin_pdf.action("send_signature_request")
class SendSignatureRequestAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            signers = []
            for s in inputs["signers"]:
                signers.append(
                    {
                        "name": s.get("name", ""),
                        "email_address": s.get("email_address") or s.get("email", ""),
                    }
                )
            body: Dict[str, Any] = {
                "title": inputs["title"],
                "signers": signers,
            }
            if inputs.get("file_urls"):
                body["file_urls"] = inputs["file_urls"]
            elif inputs.get("file_url"):
                body["file_url"] = inputs["file_url"]
            if inputs.get("message"):
                body["message"] = inputs["message"]
            due_date = inputs.get("due_date")
            body["expires_at"] = _to_epoch_millis(due_date) if due_date else int((time.time() + 30 * 86400) * 1000)
            response = await context.fetch(
                f"{BASE_URL}/signature_request/send",
                method="POST",
                headers=_auth_headers(context),
                json=body,
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "signature_request": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("get_signature_request")
class GetSignatureRequestAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            req_id = inputs["signature_request_id"]
            response = await context.fetch(
                f"{BASE_URL}/signature_request/{req_id}",
                method="GET",
                headers=_auth_headers(context),
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "signature_request": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("cancel_signature_request")
class CancelSignatureRequestAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            req_id = inputs["signature_request_id"]
            response = await context.fetch(
                f"{BASE_URL}/signature_request/cancel/{req_id}",
                method="PUT",
                headers=_auth_headers(context),
                json={},
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "canceled": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("generate_signing_link")
class GenerateSigningLinkAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            req_id = inputs["signature_request_id"]
            body = {"signer_email": inputs["signer_email"]}
            response = await context.fetch(
                f"{BASE_URL}/signature_request/{req_id}/signing-link",
                method="POST",
                headers=_auth_headers(context),
                json=body,
            )
            _raise_for_status(response)
            data = response.data
            signing_link = (
                data.get("view_url") or data.get("url") or data.get("signing_link", "")
                if isinstance(data, dict)
                else ""
            )
            return ActionResult(data={"result": True, "signing_link": signing_link}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("send_reminder")
class SendReminderAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            req_id = inputs["signature_request_id"]
            emails = inputs.get("emails")
            if not emails:
                # fetch pending signers to remind all
                sr = await context.fetch(
                    f"{BASE_URL}/signature_request/{req_id}",
                    method="GET",
                    headers=_auth_headers(context),
                )
                _raise_for_status(sr)
                signers = sr.data.get("signature_request", sr.data).get("signers", [])
                emails = [
                    s.get("email_address") or s.get("email")
                    for s in signers
                    if s.get("status") == "NEED_TO_SIGN" and (s.get("email_address") or s.get("email"))
                ]
                if not emails:
                    raise ValueError("No pending signers found to remind")
            body: Dict[str, Any] = {"emails": emails}
            response = await context.fetch(
                f"{BASE_URL}/signature_request/remind/{req_id}",
                method="POST",
                headers=_auth_headers(context),
                json=body,
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "sent": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("send_from_template")
class SendFromTemplateAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            signers = []
            for s in inputs["signers"]:
                signer: Dict[str, Any] = {"email_address": s.get("email_address") or s.get("email", "")}
                if s.get("name"):
                    signer["name"] = s["name"]
                if s.get("signer_role") or s.get("role"):
                    signer["signer_role"] = s.get("signer_role") or s.get("role")
                signers.append(signer)
            body: Dict[str, Any] = {
                "template_id": inputs["template_id"],
                "title": inputs["title"],
                "signers": signers,
            }
            due_date = inputs.get("due_date")
            body["expires_at"] = _to_epoch_millis(due_date) if due_date else int((time.time() + 30 * 86400) * 1000)
            if inputs.get("tags"):
                body["tags"] = inputs["tags"]
            if inputs.get("fields"):
                body["fields"] = inputs["fields"]
            if inputs.get("variables"):
                body["variables"] = inputs["variables"]
            if inputs.get("message"):
                body["message"] = inputs["message"]
            response = await context.fetch(
                f"{BASE_URL}/signature_request/send-from-template",
                method="POST",
                headers=_auth_headers(context),
                json=body,
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "signature_request": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("update_signature_request")
class UpdateSignatureRequestAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            req_id = inputs["signature_request_id"]
            due_date = inputs["due_date"]
            expires_at = _to_epoch_millis(due_date)
            response = await context.fetch(
                f"{BASE_URL}/signature_request/{req_id}",
                method="PATCH",
                headers=_auth_headers(context),
                json={"expires_at": expires_at},
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "signature_request": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("download_signed_document")
class DownloadSignedDocumentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            req_id = inputs["signature_request_id"]
            doc_type = inputs.get("type", "agreement")
            response = await context.fetch(
                f"{BASE_URL}/signature_request/{req_id}/file",
                method="GET",
                headers={**_auth_headers(context), "Accept": "application/json"},
                params={"type": doc_type},
            )
            _raise_for_status(response)
            data = response.data
            file_url = (
                data.get("signed_url") or data.get("file_url") or data.get("url") or data.get("download_url", "")
                if isinstance(data, dict)
                else ""
            )
            return ActionResult(data={"result": True, "file_url": file_url, "file": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("upload_document")
class UploadDocumentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            location = inputs.get("location", "personal")
            body: Dict[str, Any] = {
                "document_name": inputs["document_name"],
                "location": location if isinstance(location, dict) else {"type": location},
            }
            if inputs.get("file_url"):
                body["method"] = "file-upload"
                body["document_data"] = {"file_url": inputs["file_url"]}
            elif inputs.get("template_id"):
                body["method"] = "template"
                body["document_data"] = {"template_id": inputs["template_id"]}
            response = await context.fetch(
                f"{BASE_URL}/documents",
                method="POST",
                headers=_auth_headers(context),
                json=body,
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "document": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("generate_document_from_template")
class GenerateDocumentFromTemplateAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            template_id = inputs["template_id"]
            body: Dict[str, Any] = {"document_name": inputs["document_name"]}
            if inputs.get("tags"):
                body["tags"] = inputs["tags"]
            if inputs.get("fields"):
                body["fields"] = inputs["fields"]
            if inputs.get("variables"):
                body["variables"] = inputs["variables"]
            response = await context.fetch(
                f"{BASE_URL}/templates/{template_id}/generate-document",
                method="POST",
                headers={**_auth_headers(context), "Accept": "application/json"},
                json=body,
            )
            _raise_for_status(response)
            return ActionResult(data={"result": True, "document": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("create_agreement")
class CreateAgreementAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {
                "method": "template",
                "agreement_name": inputs["agreement_name"],
                "agreement_data": {"template_id": inputs["template_id"]},
            }
            if inputs.get("variables"):
                body["agreement_data"]["variables"] = inputs["variables"]
            if inputs.get("fields"):
                body["agreement_data"]["fields"] = inputs["fields"]
            if inputs.get("linked_objects"):
                body["agreement_data"]["linked_objects"] = inputs["linked_objects"]
            response = await context.fetch(
                f"{BASE_URL}/agreements",
                method="POST",
                headers=_auth_headers(context),
                json=body,
            )
            _raise_for_status(response)
            data = response.data
            agreement = data.get("agreement", data) if isinstance(data, dict) else data
            return ActionResult(data={"result": True, "agreement": agreement}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("download_agreement")
class DownloadAgreementAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            agreement_id = inputs["agreement_id"]
            response = await context.fetch(
                f"{BASE_URL}/agreements/{agreement_id}/file",
                method="GET",
                headers={**_auth_headers(context), "Accept": "application/json"},
            )
            _raise_for_status(response)
            data = response.data
            file_url = (
                data.get("signed_url") or data.get("file_url") or data.get("url") or data.get("download_url", "")
                if isinstance(data, dict)
                else ""
            )
            return ActionResult(data={"result": True, "file_url": file_url, "file": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
