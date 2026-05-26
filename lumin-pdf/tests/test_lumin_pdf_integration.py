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
        list_result = await lumin_pdf.execute_action("list_templates", {"limit": 1}, live_context)
        templates = list_result.result.data["templates"]

        if not templates:
            pytest.skip("No templates in workspace")

        template_id = templates[0].get("id")
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
