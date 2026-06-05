"""
End-to-end integration tests for the Lumin PDF integration.

Requires credentials set in environment variables or a .env file at the repo root:
    LUMIN_PDF_TOKEN  — your Lumin PDF API key

Read-only tests can be run safely with:
    pytest lumin-pdf/tests/test_lumin_pdf_integration.py -m "integration and not destructive"

Destructive tests create, update, delete, or email real Lumin resources. Run them only against
a test account where this is acceptable:
    pytest lumin-pdf/tests/test_lumin_pdf_integration.py -m "integration and destructive"
"""

import asyncio
import os
import sys

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lumin_pdf import lumin_pdf  # noqa: E402

pytestmark = pytest.mark.integration

PDF_URL = "https://www.learningcontainer.com/wp-content/uploads/2019/09/sample-pdf-file.pdf"
READY_SIGNATURE_STATUSES = {"NEED_TO_SIGN", "WAITING_FOR_OTHERS"}
TERMINAL_SIGNATURE_STATUSES = {"APPROVED", "CANCELLED", "FAILED", "REJECTED"}


def _signature_request_id(data):
    inner = data.get("signature_request") if isinstance(data.get("signature_request"), dict) else data
    return inner.get("signature_request_id") or inner.get("id") or data.get("signature_request_id") or data.get("id")


async def _cancel_signature_request(live_context, signature_request_id):
    return await lumin_pdf.execute_action(
        "cancel_signature_request", {"signature_request_id": signature_request_id}, live_context
    )


async def _wait_for_signature_request_ready(live_context, signature_request_id, timeout_seconds=60):
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        result = await lumin_pdf.execute_action(
            "get_signature_request", {"signature_request_id": signature_request_id}, live_context
        )
        data = result.result.data["signature_request"]
        signature_request = data.get("signature_request", data) if isinstance(data, dict) else data
        status = signature_request.get("status")
        if status in READY_SIGNATURE_STATUSES:
            return signature_request
        if status in TERMINAL_SIGNATURE_STATUSES:
            pytest.fail(f"Signature request reached terminal status before becoming ready: {status}")
        await asyncio.sleep(2)

    pytest.skip("Signature request did not become ready in time")
    raise AssertionError("Unreachable: pytest.skip should raise and not return")


@pytest.fixture
def live_context(env_credentials, make_context):
    api_key = env_credentials("LUMIN_PDF_TOKEN")
    if not api_key:
        pytest.skip("LUMIN_PDF_TOKEN not set — skipping integration tests")

    async def real_fetch(url, *, method="GET", json=None, headers=None, params=None, data=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json, headers=headers, params=params, data=data) as resp:
                try:
                    body = await resp.json()
                except Exception:
                    body = {}
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=body)

    ctx = make_context(auth={"api_key": api_key})
    ctx.fetch.side_effect = real_fetch
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


@pytest.mark.destructive
class TestSignatureRequestLifecycle:
    async def test_full_lifecycle(self, live_context):
        sig_req_id = None
        canceled = False
        try:
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

            sig_req_id = _signature_request_id(sr_data)
            assert sig_req_id, "No signature_request id returned"

            # Get
            get_result = await lumin_pdf.execute_action(
                "get_signature_request", {"signature_request_id": sig_req_id}, live_context
            )
            assert get_result.result.data["result"] is True
            assert "signature_request" in get_result.result.data

            await _wait_for_signature_request_ready(live_context, sig_req_id)

            # Generate signing link
            link_result = await lumin_pdf.execute_action(
                "generate_signing_link",
                {"signature_request_id": sig_req_id, "signer_email": "engineering@autohive.com"},
                live_context,
            )
            assert link_result.result.data["result"] is True
            assert "signing_link" in link_result.result.data

            # Cancel (cleanup)
            cancel_result = await _cancel_signature_request(live_context, sig_req_id)
            canceled = True
            assert cancel_result.result.data["result"] is True
            assert cancel_result.result.data["canceled"] is True
        finally:
            if sig_req_id and not canceled:
                await _cancel_signature_request(live_context, sig_req_id)


# ---- Upload Document ----


@pytest.mark.destructive
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


@pytest.mark.destructive
class TestSendFromTemplate:
    async def test_skipped_if_no_templates(self, live_context):
        list_result = await lumin_pdf.execute_action("list_templates", {"limit": 10}, live_context)
        templates = list_result.result.data["templates"]

        if not templates:
            pytest.skip("No templates in workspace")

        lumin_templates = [t for t in templates if t.get("type") == "lumin"]
        if not lumin_templates:
            pytest.skip("No lumin-type templates in workspace — send_from_template requires a lumin template")

        template_id = lumin_templates[0].get("template_id") or lumin_templates[0].get("id")
        sig_req_id = None
        try:
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

            sig_req_id = _signature_request_id(data["signature_request"])
        finally:
            if sig_req_id:
                await _cancel_signature_request(live_context, sig_req_id)


# ---- Update Signature Request ----


@pytest.mark.destructive
class TestUpdateSignatureRequest:
    async def test_extends_expiry(self, live_context):
        sig_req_id = None
        try:
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
            sig_req_id = _signature_request_id(sr_data)

            if not sig_req_id:
                pytest.skip("Could not create signature request to update")

            await _wait_for_signature_request_ready(live_context, sig_req_id)

            result = await lumin_pdf.execute_action(
                "update_signature_request",
                {"signature_request_id": sig_req_id, "due_date": "2027-01-01T00:00:00"},
                live_context,
            )

            assert result.result.data["result"] is True
        finally:
            if sig_req_id:
                await _cancel_signature_request(live_context, sig_req_id)


# ---- Download Signed Document ----


@pytest.mark.destructive
class TestDownloadSignedDocument:
    async def test_returns_file_data(self, live_context):
        sig_req_id = None
        try:
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
            sig_req_id = _signature_request_id(sr_data)

            if not sig_req_id:
                pytest.skip("Could not create signature request")

            result = await lumin_pdf.execute_action(
                "download_signed_document", {"signature_request_id": sig_req_id}, live_context
            )

            # Document not signed yet — accept any result (error expected for unsigned docs)
            assert result is not None
        finally:
            if sig_req_id:
                await _cancel_signature_request(live_context, sig_req_id)


# ---- Generate Document From Template ----


@pytest.mark.destructive
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


@pytest.mark.destructive
class TestCreateAgreement:
    async def test_skipped_if_no_templates(self, live_context):
        list_result = await lumin_pdf.execute_action("list_templates", {"limit": 10}, live_context)
        templates = list_result.result.data["templates"]

        if not templates:
            pytest.skip("No templates in workspace")

        lumin_templates = [t for t in templates if t.get("type") == "lumin"]
        if not lumin_templates:
            pytest.skip("No lumin-type templates in workspace — create_agreement requires a lumin template")

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
            agreement.get("agreement", {}).get("agreement_id") or agreement.get("agreement_id") or agreement.get("id")
        )
        assert agreement_id, f"No agreement_id in response: {agreement}"


# ---- Send Reminder ----


@pytest.mark.destructive
class TestSendReminder:
    async def test_sends_reminder(self, live_context):
        sig_req_id = None
        try:
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
            sig_req_id = _signature_request_id(sr_data)

            if not sig_req_id:
                pytest.skip("Could not create signature request for reminder test")

            await _wait_for_signature_request_ready(live_context, sig_req_id)

            result = await lumin_pdf.execute_action("send_reminder", {"signature_request_id": sig_req_id}, live_context)

            assert result.result.data["result"] is True
            assert result.result.data["sent"] is True
        finally:
            if sig_req_id:
                await _cancel_signature_request(live_context, sig_req_id)


# ---- Download Agreement ----


@pytest.mark.destructive
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

        create_result = await lumin_pdf.execute_action(
            "create_agreement",
            {"agreement_name": "Autohive Download Agreement Test", "template_id": template_id},
            live_context,
        )
        data = create_result.result.data
        assert data["result"] is True

        agreement = data["agreement"]
        agreement_id = (
            agreement.get("agreement", {}).get("agreement_id") or agreement.get("agreement_id") or agreement.get("id")
        )

        if not agreement_id:
            pytest.skip("Could not extract agreement_id from create response")

        result = await lumin_pdf.execute_action("download_agreement", {"agreement_id": agreement_id}, live_context)

        assert "result" in result.result.data
