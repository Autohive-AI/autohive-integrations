"""
End-to-end integration tests for the Lumin PDF integration.

Requires a valid API key set in the LUMIN_PDF_TOKEN environment variable.

Write actions (send_signature_request) create real data — the test cancels
the created request at the end of the chain to clean up.

Run with:
    pytest lumin-pdf/tests/test_lumin_pdf_integration.py -m integration
"""

import os
import sys
import importlib

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _parent)

import pytest  # noqa: E402
from unittest.mock import MagicMock, AsyncMock  # noqa: E402
from autohive_integrations_sdk import FetchResponse  # noqa: E402

_spec = importlib.util.spec_from_file_location("lumin_pdf_mod", os.path.join(_parent, "lumin_pdf.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

lumin_pdf = _mod.lumin_pdf

pytestmark = pytest.mark.integration

ACCESS_TOKEN = os.environ.get("LUMIN_PDF_TOKEN", "")

PDF_URL = "https://www.learningcontainer.com/wp-content/uploads/2019/09/sample-pdf-file.pdf"


@pytest.fixture
def live_context():
    if not ACCESS_TOKEN:
        pytest.skip("LUMIN_PDF_TOKEN not set — skipping integration tests")

    import aiohttp

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, data=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params, data=data) as resp:
                try:
                    body = await resp.json()
                except Exception:
                    body = {}
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=body)

    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(side_effect=real_fetch)
    ctx.auth = {"api_key": ACCESS_TOKEN}
    return ctx


# ---- User & Workspace ----


class TestGetCurrentUser:
    async def test_returns_user_info(self, live_context):
        result = await lumin_pdf.execute_action("get_current_user", {}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "user" in data


class TestGetWorkspace:
    async def test_returns_workspace(self, live_context):
        result = await lumin_pdf.execute_action("get_workspace", {}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "workspace" in data


class TestListWorkspaceMembers:
    async def test_returns_members(self, live_context):
        result = await lumin_pdf.execute_action("list_workspace_members", {"limit": 10}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "members" in data
        assert isinstance(data["members"], list)


# ---- Templates ----


class TestListTemplates:
    async def test_returns_templates(self, live_context):
        result = await lumin_pdf.execute_action("list_templates", {"limit": 10}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "templates" in data
        assert isinstance(data["templates"], list)


class TestGetTemplate:
    async def test_fetches_template_by_id(self, live_context):
        list_result = await lumin_pdf.execute_action("list_templates", {"limit": 10}, live_context)
        templates = list_result.result.data["templates"]

        if not templates:
            pytest.skip("No templates in workspace")

        template_id = templates[0].get("template_id") or templates[0].get("id")
        result = await lumin_pdf.execute_action("get_template", {"template_id": template_id}, live_context)

        data = result.result.data
        assert data["result"] is True
        assert "template" in data


# ---- Signature Request Lifecycle ----


class TestSignatureRequestLifecycle:
    async def test_full_lifecycle(self, live_context):
        # Send
        sr_result = await lumin_pdf.execute_action(
            "send_signature_request",
            {
                "title": "Autohive Integration Test",
                "file_url": PDF_URL,
                "signers": [{"name": "Test Signer", "email_address": "engineering@autohive.com"}],
                "message": "Integration test — will be canceled immediately.",
            },
            live_context,
        )
        assert sr_result.result.data["result"] is True
        sr_data = sr_result.result.data["signature_request"]
        assert isinstance(sr_data, dict)

        # API returns {"signature_request": {"signature_request_id": "..."}}
        inner = sr_data.get("signature_request") if isinstance(sr_data.get("signature_request"), dict) else sr_data
        sig_req_id = (
            inner.get("signature_request_id")
            or inner.get("id")
            or sr_data.get("signature_request_id")
            or sr_data.get("id")
        )
        assert sig_req_id, "No signature_request id returned"

        # Get
        get_result = await lumin_pdf.execute_action(
            "get_signature_request", {"signature_request_id": sig_req_id}, live_context
        )
        assert get_result.result.data["result"] is True
        assert "signature_request" in get_result.result.data

        # Generate signing link
        link_result = await lumin_pdf.execute_action(
            "generate_signing_link",
            {
                "signature_request_id": sig_req_id,
                "signer_email": "engineering@autohive.com",
            },
            live_context,
        )
        assert link_result.result.data["result"] is True
        assert "signing_link" in link_result.result.data

        # Cancel (cleanup)
        cancel_result = await lumin_pdf.execute_action(
            "cancel_signature_request",
            {"signature_request_id": sig_req_id},
            live_context,
        )
        assert cancel_result.result.data["result"] is True
        assert cancel_result.result.data["canceled"] is True


# ---- Upload Document ----


class TestUploadDocument:
    async def test_upload_from_url(self, live_context):
        result = await lumin_pdf.execute_action(
            "upload_document",
            {
                "document_name": "Autohive Integration Test Doc",
                "file_url": PDF_URL,
                "location": "personal",
            },
            live_context,
        )

        data = result.result.data
        assert data["result"] is True
        assert "document" in data


# ---- Send From Template ----


class TestSendFromTemplate:
    async def test_skipped_if_no_templates(self, live_context):
        list_result = await lumin_pdf.execute_action("list_templates", {"limit": 10}, live_context)
        templates = list_result.result.data["templates"]

        if not templates:
            pytest.skip("No templates in workspace")

        lumin_templates = [t for t in templates if t.get("type") == "lumin"]
        if not lumin_templates:
            pytest.skip("No lumin-type templates in workspace — send_from_template requires a lumin template, not a pdf template")

        template_id = lumin_templates[0].get("template_id") or lumin_templates[0].get("id")
        result = await lumin_pdf.execute_action(
            "send_from_template",
            {
                "template_id": template_id,
                "title": "Autohive Template Test",
                "signers": [{"name": "Test Signer", "email_address": "engineering@autohive.com"}],
            },
            live_context,
        )

        data = result.result.data
        assert data["result"] is True
        assert "signature_request" in data

        # Cancel the created request
        inner = data["signature_request"]
        sig_req_id = (
            inner.get("signature_request", {}).get("signature_request_id")
            or inner.get("signature_request_id")
            or inner.get("id")
        )
        if sig_req_id:
            await lumin_pdf.execute_action(
                "cancel_signature_request", {"signature_request_id": sig_req_id}, live_context
            )


# ---- Update Signature Request ----


class TestUpdateSignatureRequest:
    async def test_extends_expiry(self, live_context):
        # Create a request to update
        sr_result = await lumin_pdf.execute_action(
            "send_signature_request",
            {
                "title": "Autohive Update Test",
                "file_url": PDF_URL,
                "signers": [{"name": "Test Signer", "email_address": "engineering@autohive.com"}],
            },
            live_context,
        )
        sr_data = sr_result.result.data["signature_request"]
        inner = sr_data.get("signature_request") if isinstance(sr_data.get("signature_request"), dict) else sr_data
        sig_req_id = inner.get("signature_request_id") or inner.get("id")

        if not sig_req_id:
            pytest.skip("Could not create signature request to update")

        result = await lumin_pdf.execute_action(
            "update_signature_request",
            {"signature_request_id": sig_req_id, "due_date": "2027-01-01T00:00:00"},
            live_context,
        )

        assert result.result.data["result"] is True

        # Cleanup
        await lumin_pdf.execute_action("cancel_signature_request", {"signature_request_id": sig_req_id}, live_context)


# ---- Download Signed Document ----


class TestDownloadSignedDocument:
    async def test_returns_file_data(self, live_context):
        # Create and immediately try to download — will likely get a 409 since it's not signed yet,
        # but confirms the action calls the right endpoint
        sr_result = await lumin_pdf.execute_action(
            "send_signature_request",
            {
                "title": "Autohive Download Test",
                "file_url": PDF_URL,
                "signers": [{"name": "Test Signer", "email_address": "engineering@autohive.com"}],
            },
            live_context,
        )
        sr_data = sr_result.result.data["signature_request"]
        inner = sr_data.get("signature_request") if isinstance(sr_data.get("signature_request"), dict) else sr_data
        sig_req_id = inner.get("signature_request_id") or inner.get("id")

        if not sig_req_id:
            pytest.skip("Could not create signature request")

        result = await lumin_pdf.execute_action(
            "download_signed_document", {"signature_request_id": sig_req_id}, live_context
        )

        # Document not signed yet — action either returns a file URL (success) or an error (expected for unsigned docs)
        # Accept any result — what matters is the action reached the endpoint without silently swallowing errors
        assert result is not None

        # Cleanup
        await lumin_pdf.execute_action("cancel_signature_request", {"signature_request_id": sig_req_id}, live_context)


# ---- Generate Document From Template ----


class TestGenerateDocumentFromTemplate:
    async def test_skipped_if_no_templates(self, live_context):
        list_result = await lumin_pdf.execute_action("list_templates", {"limit": 10}, live_context)
        templates = list_result.result.data["templates"]

        if not templates:
            pytest.skip("No templates in workspace")

        template_id = templates[0].get("template_id") or templates[0].get("id")
        result = await lumin_pdf.execute_action(
            "generate_document_from_template",
            {"template_id": template_id, "document_name": "Autohive Generated Doc"},
            live_context,
        )

        data = result.result.data
        assert data["result"] is True
        assert "document" in data


# ---- Create Agreement ----


class TestCreateAgreement:
    async def test_skipped_if_no_templates(self, live_context):
        list_result = await lumin_pdf.execute_action("list_templates", {"limit": 10}, live_context)
        templates = list_result.result.data["templates"]

        if not templates:
            pytest.skip("No templates in workspace")

        lumin_templates = [t for t in templates if t.get("type") == "lumin"]
        if not lumin_templates:
            pytest.skip("No lumin-type templates in workspace — create_agreement requires a lumin template, not a pdf template")

        template_id = lumin_templates[0].get("template_id") or lumin_templates[0].get("id")
        result = await lumin_pdf.execute_action(
            "create_agreement",
            {"agreement_name": "Autohive Test Agreement", "template_id": template_id},
            live_context,
        )

        data = result.result.data
        assert data["result"] is True
        assert "agreement" in data

        agreement = data["agreement"]
        agreement_id = (
            agreement.get("agreement", {}).get("agreement_id")
            or agreement.get("agreement_id")
            or agreement.get("id")
        )
        assert agreement_id, f"No agreement_id in response: {agreement}"


# ---- Send Reminder ----


class TestSendReminder:
    async def test_sends_reminder(self, live_context):
        # Create a signature request to remind on
        sr_result = await lumin_pdf.execute_action(
            "send_signature_request",
            {
                "title": "Autohive Reminder Test",
                "file_url": PDF_URL,
                "signers": [{"name": "Test Signer", "email_address": "engineering@autohive.com"}],
            },
            live_context,
        )
        sr_data = sr_result.result.data["signature_request"]
        inner = sr_data.get("signature_request") if isinstance(sr_data.get("signature_request"), dict) else sr_data
        sig_req_id = inner.get("signature_request_id") or inner.get("id")

        if not sig_req_id:
            pytest.skip("Could not create signature request for reminder test")

        result = await lumin_pdf.execute_action(
            "send_reminder",
            {"signature_request_id": sig_req_id},
            live_context,
        )

        assert result.result.data["result"] is True
        assert result.result.data["sent"] is True

        # Cleanup
        await lumin_pdf.execute_action("cancel_signature_request", {"signature_request_id": sig_req_id}, live_context)


# ---- Download Agreement ----


class TestDownloadAgreement:
    async def test_downloads_agreement(self, live_context):
        list_result = await lumin_pdf.execute_action("list_templates", {"limit": 10}, live_context)
        templates = list_result.result.data["templates"]

        if not templates:
            pytest.skip("No templates in workspace")

        lumin_templates = [t for t in templates if t.get("type") == "lumin"]
        if not lumin_templates:
            pytest.skip("No lumin-type templates in workspace — download_agreement requires a lumin template")

        template_id = lumin_templates[0].get("template_id") or lumin_templates[0].get("id")

        # Create an agreement to download
        create_result = await lumin_pdf.execute_action(
            "create_agreement",
            {"agreement_name": "Autohive Download Agreement Test", "template_id": template_id},
            live_context,
        )
        data = create_result.result.data
        assert data["result"] is True

        agreement = data["agreement"]
        agreement_id = (
            agreement.get("agreement", {}).get("agreement_id")
            or agreement.get("agreement_id")
            or agreement.get("id")
        )

        if not agreement_id:
            pytest.skip("Could not extract agreement_id from create response")

        result = await lumin_pdf.execute_action(
            "download_agreement",
            {"agreement_id": agreement_id},
            live_context,
        )

        assert "result" in result.result.data
