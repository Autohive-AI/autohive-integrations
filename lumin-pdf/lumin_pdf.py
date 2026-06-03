import time
from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Any, Dict

lumin_pdf = Integration.load()

BASE_URL = "https://api.luminpdf.com/v1"


def _auth_headers(context: ExecutionContext, api_version: str = "") -> Dict[str, str]:
    auth = context.auth or {}
    api_key = auth.get("api_key") or auth.get("credentials", {}).get("api_key")
    headers = {}
    if api_key:
        headers["X-API-KEY"] = api_key
    if api_version:
        headers["X-Lumin-API-Version"] = api_version
    return headers


# ---- User & Workspace ----


@lumin_pdf.action("get_current_user")
class GetCurrentUserAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            response = await context.fetch(f"{BASE_URL}/user/info", method="GET", headers=_auth_headers(context))
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
            return ActionResult(data={"result": True, "workspace": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("list_workspace_members")
class ListWorkspaceMembersAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            params: Dict[str, Any] = {"page": int(inputs.get("page", 1))}
            if inputs.get("limit") is not None:
                params["limit"] = int(inputs["limit"])
            response = await context.fetch(
                f"{BASE_URL}/workspaces/members",
                method="GET",
                headers=_auth_headers(context),
                params=params,
            )
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
            params: Dict[str, Any] = {"page": int(inputs.get("page", 1))}
            if inputs.get("limit") is not None:
                params["limit"] = int(inputs["limit"])
            response = await context.fetch(
                f"{BASE_URL}/templates",
                method="GET",
                headers=_auth_headers(context, api_version="1.1"),
                params=params,
            )
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
            if due_date:
                from datetime import datetime, timezone

                body["expires_at"] = int(
                    datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc).timestamp() * 1000
                )
            else:
                body["expires_at"] = int((time.time() + 30 * 86400) * 1000)
            response = await context.fetch(
                f"{BASE_URL}/signature_request/send",
                method="POST",
                headers=_auth_headers(context),
                json=body,
            )
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
            return ActionResult(data={"result": True, "signature_request": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("cancel_signature_request")
class CancelSignatureRequestAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            req_id = inputs["signature_request_id"]
            await context.fetch(
                f"{BASE_URL}/signature_request/cancel/{req_id}",
                method="PUT",
                headers=_auth_headers(context),
                json={},
            )
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
            body: Dict[str, Any] = {}
            if inputs.get("emails"):
                body["emails"] = inputs["emails"]
            await context.fetch(
                f"{BASE_URL}/signature_request/remind/{req_id}",
                method="POST",
                headers=_auth_headers(context),
                json=body,
            )
            return ActionResult(data={"result": True, "sent": True}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("send_from_template")
class SendFromTemplateAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            body: Dict[str, Any] = {
                "template_id": inputs["template_id"],
                "title": inputs["title"],
                "signers": inputs["signers"],
            }
            due_date = inputs.get("due_date")
            if due_date:
                from datetime import datetime, timezone

                body["expires_at"] = int(
                    datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc).timestamp() * 1000
                )
            else:
                body["expires_at"] = int((time.time() + 30 * 86400) * 1000)
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
            return ActionResult(data={"result": True, "signature_request": response.data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))


@lumin_pdf.action("update_signature_request")
class UpdateSignatureRequestAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            req_id = inputs["signature_request_id"]
            due_date = inputs["due_date"]
            from datetime import datetime, timezone

            expires_at = int(datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc).timestamp() * 1000)
            response = await context.fetch(
                f"{BASE_URL}/signature_request/{req_id}",
                method="PATCH",
                headers=_auth_headers(context),
                json={"expires_at": expires_at},
            )
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
                headers=_auth_headers(context),
                params={"type": doc_type},
            )
            data = response.data
            file_url = (
                data.get("file_url") or data.get("url") or data.get("download_url", "")
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
            body: Dict[str, Any] = {
                "document_name": inputs["document_name"],
                "location": inputs.get("location", "personal"),
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
                headers=_auth_headers(context),
                json=body,
            )
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
            return ActionResult(data={"result": True, "agreement": response.data}, cost_usd=0.0)
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
                headers=_auth_headers(context),
            )
            data = response.data
            file_url = (
                data.get("file_url") or data.get("url") or data.get("download_url", "")
                if isinstance(data, dict)
                else ""
            )
            return ActionResult(data={"result": True, "file_url": file_url, "file": data}, cost_usd=0.0)
        except Exception as e:
            return ActionError(message=str(e))
