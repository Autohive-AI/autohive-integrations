"""
Unit tests for the Lumin PDF integration using mocked fetch.

Run with:
    pytest lumin-pdf/tests/test_lumin_pdf_unit.py -m unit
"""

import os
import sys

import pytest
from autohive_integrations_sdk import FetchResponse, ResultType

INVALID_INPUT_TYPES = {ResultType.ACTION_ERROR, ResultType.VALIDATION_ERROR}

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lumin_pdf import lumin_pdf  # noqa: E402

pytestmark = pytest.mark.unit

BASE_URL = "https://api.luminpdf.com/v1"
API_KEY = "test_api_key"  # nosec B105


# ---- User & Workspace ----


class TestGetCurrentUser:
    async def test_returns_user(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "u1", "email": "test@example.com"})

        result = await lumin_pdf.execute_action("get_current_user", {}, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["user"] == {"id": "u1", "email": "test@example.com"}
        ctx.fetch.assert_called_once_with(f"{BASE_URL}/user/info", method="GET", headers={"X-API-KEY": API_KEY})

    async def test_error_returns_action_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Unauthorized")

        result = await lumin_pdf.execute_action("get_current_user", {}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message


class TestGetWorkspace:
    async def test_returns_workspace(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "ws1", "name": "My Workspace"})

        result = await lumin_pdf.execute_action("get_workspace", {}, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["workspace"] == {"id": "ws1", "name": "My Workspace"}
        ctx.fetch.assert_called_once_with(f"{BASE_URL}/workspaces/info", method="GET", headers={"X-API-KEY": API_KEY})

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Not found")

        result = await lumin_pdf.execute_action("get_workspace", {}, ctx)

        assert result.type == ResultType.ACTION_ERROR


class TestListWorkspaceMembers:
    async def test_returns_members_list(self, make_context):
        members = [{"id": "m1"}, {"id": "m2"}]
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data=members)

        result = await lumin_pdf.execute_action("list_workspace_members", {"page": 1, "limit": 10}, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["members"] == members
        assert ctx.fetch.call_args.kwargs["params"] == {"page": 1, "limit": 10}

    async def test_returns_members_from_data_key(self, make_context):
        members = [{"id": "m1"}]
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": members, "total": 1})

        result = await lumin_pdf.execute_action("list_workspace_members", {}, ctx)

        assert result.result.data["members"] == members

    async def test_defaults_page_and_limit_when_not_provided(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await lumin_pdf.execute_action("list_workspace_members", {}, ctx)

        params = ctx.fetch.call_args.kwargs["params"]
        assert params["page"] == 1
        assert params["limit"] == 10

    async def test_page_only_defaults_limit_to_10(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await lumin_pdf.execute_action("list_workspace_members", {"page": 3}, ctx)

        assert ctx.fetch.call_args.kwargs["params"] == {"page": 3, "limit": 10}

    async def test_limit_only_defaults_page_to_1(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await lumin_pdf.execute_action("list_workspace_members", {"limit": 10}, ctx)

        assert ctx.fetch.call_args.kwargs["params"] == {"page": 1, "limit": 10}


# ---- Templates ----


class TestListTemplates:
    async def test_returns_templates_list(self, make_context):
        templates = [{"id": "t1", "name": "NDA"}]
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data=templates)

        result = await lumin_pdf.execute_action("list_templates", {"limit": 5}, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["templates"] == templates

    async def test_returns_templates_from_data_key(self, make_context):
        templates = [{"id": "t1"}]
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"templates": templates})

        result = await lumin_pdf.execute_action("list_templates", {}, ctx)

        assert result.result.data["templates"] == templates

    async def test_defaults_page_and_limit_when_not_provided(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await lumin_pdf.execute_action("list_templates", {}, ctx)

        params = ctx.fetch.call_args.kwargs["params"]
        assert params["page"] == 1
        assert params["limit"] == 10

    async def test_page_only_defaults_limit_to_10(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await lumin_pdf.execute_action("list_templates", {"page": 3}, ctx)

        assert ctx.fetch.call_args.kwargs["params"] == {"page": 3, "limit": 10}

    async def test_limit_only_defaults_page_to_1(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await lumin_pdf.execute_action("list_templates", {"limit": 25}, ctx)

        assert ctx.fetch.call_args.kwargs["params"] == {"page": 1, "limit": 25}

    async def test_limit_clamped_to_nearest_valid_value(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        # 5 → nearest valid is 10, 20 → nearest valid is 25, 40 → nearest valid is 50
        for raw, expected in [(5, 10), (20, 25), (40, 50)]:
            await lumin_pdf.execute_action("list_templates", {"limit": raw}, ctx)
            assert ctx.fetch.call_args.kwargs["params"]["limit"] == expected

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Server error")

        result = await lumin_pdf.execute_action("list_templates", {}, ctx)

        assert result.type == ResultType.ACTION_ERROR


@pytest.mark.parametrize(
    "action_name, expected_path, inputs, expected_params",
    [
        ("list_workspace_members", "/workspaces/members", {}, {"page": 1, "limit": 10}),
        ("list_workspace_members", "/workspaces/members", {"page": 3}, {"page": 3, "limit": 10}),
        ("list_workspace_members", "/workspaces/members", {"limit": 25}, {"page": 1, "limit": 25}),
        ("list_workspace_members", "/workspaces/members", {"page": 2, "limit": 50}, {"page": 2, "limit": 50}),
        ("list_templates", "/templates", {}, {"page": 1, "limit": 10}),
        ("list_templates", "/templates", {"page": 3}, {"page": 3, "limit": 10}),
        ("list_templates", "/templates", {"limit": 25}, {"page": 1, "limit": 25}),
        ("list_templates", "/templates", {"page": 2, "limit": 50}, {"page": 2, "limit": 50}),
    ],
)
async def test_list_actions_send_pagination_params(make_context, action_name, expected_path, inputs, expected_params):
    ctx = make_context(auth={"api_key": API_KEY})
    ctx.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

    await lumin_pdf.execute_action(action_name, inputs, ctx)

    call = ctx.fetch.call_args
    assert call.args[0] == f"{BASE_URL}{expected_path}"
    assert call.kwargs["method"] == "GET"
    assert call.kwargs["params"] == expected_params


class TestGetTemplate:
    async def test_returns_template(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "t1", "name": "NDA"})

        result = await lumin_pdf.execute_action("get_template", {"template_id": "t1"}, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["template"] == {"id": "t1", "name": "NDA"}
        ctx.fetch.assert_called_once_with(
            f"{BASE_URL}/templates/t1", method="GET", headers={"X-API-KEY": API_KEY, "X-Lumin-API-Version": "1.1"}
        )

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Not found")

        result = await lumin_pdf.execute_action("get_template", {"template_id": "bad"}, ctx)

        assert result.type == ResultType.ACTION_ERROR


# ---- Signature Requests ----


class TestSendSignatureRequest:
    async def test_send_with_file_url(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr1", "status": "pending"})
        inputs = {
            "title": "Test Doc",
            "file_url": "https://example.com/doc.pdf",
            "signers": [{"name": "Alice", "email_address": "alice@example.com"}],
        }

        result = await lumin_pdf.execute_action("send_signature_request", inputs, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["signature_request"]["id"] == "sr1"
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["title"] == "Test Doc"
        assert body["file_url"] == "https://example.com/doc.pdf"
        assert body["signers"] == [{"name": "Alice", "email_address": "alice@example.com"}]
        assert "expires_at" in body

    async def test_send_normalizes_email_field(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr2"})
        inputs = {
            "title": "Test",
            "file_url": "https://example.com/doc.pdf",
            "signers": [{"name": "Bob", "email": "bob@example.com"}],
        }

        await lumin_pdf.execute_action("send_signature_request", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        assert body["signers"][0]["email_address"] == "bob@example.com"

    async def test_send_with_file_urls(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr3"})
        inputs = {
            "title": "Multi",
            "file_urls": ["https://example.com/a.pdf", "https://example.com/b.pdf"],
            "signers": [{"name": "Carol", "email_address": "carol@example.com"}],
        }

        await lumin_pdf.execute_action("send_signature_request", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        assert "file_urls" in body
        assert "file_url" not in body

    async def test_missing_email_returns_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        inputs = {
            "title": "Test",
            "file_url": "https://example.com/doc.pdf",
            "signers": [{"name": "Alice"}],
        }

        result = await lumin_pdf.execute_action("send_signature_request", inputs, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "email_address" in result.result.message
        ctx.fetch.assert_not_called()

    async def test_missing_name_returns_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        inputs = {
            "title": "Test",
            "file_url": "https://example.com/doc.pdf",
            "signers": [{"email_address": "alice@example.com"}],
        }

        result = await lumin_pdf.execute_action("send_signature_request", inputs, ctx)

        assert result.type in INVALID_INPUT_TYPES
        ctx.fetch.assert_not_called()

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Bad request")

        result = await lumin_pdf.execute_action(
            "send_signature_request",
            {"title": "T", "signers": []},
            ctx,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGetSignatureRequest:
    async def test_returns_signature_request(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr1", "status": "pending"})

        result = await lumin_pdf.execute_action("get_signature_request", {"signature_request_id": "sr1"}, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["signature_request"]["id"] == "sr1"
        ctx.fetch.assert_called_once_with(
            f"{BASE_URL}/signature_request/sr1",
            method="GET",
            headers={"X-API-KEY": API_KEY},
        )

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Not found")

        result = await lumin_pdf.execute_action("get_signature_request", {"signature_request_id": "bad"}, ctx)

        assert result.type == ResultType.ACTION_ERROR


class TestCancelSignatureRequest:
    async def test_cancels_request(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await lumin_pdf.execute_action("cancel_signature_request", {"signature_request_id": "sr1"}, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["canceled"] is True
        ctx.fetch.assert_called_once_with(
            f"{BASE_URL}/signature_request/cancel/sr1",
            method="PUT",
            headers={"X-API-KEY": API_KEY},
            json={},
        )

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Already canceled")

        result = await lumin_pdf.execute_action("cancel_signature_request", {"signature_request_id": "sr1"}, ctx)

        assert result.type == ResultType.ACTION_ERROR


class TestGenerateSigningLink:
    async def test_returns_view_url(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"view_url": "https://sign.luminpdf.com/abc"}
        )
        inputs = {"signature_request_id": "sr1", "signer_email": "alice@example.com"}

        result = await lumin_pdf.execute_action("generate_signing_link", inputs, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["signing_link"] == "https://sign.luminpdf.com/abc"

    async def test_falls_back_to_url_key(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"url": "https://sign.luminpdf.com/xyz"})
        inputs = {"signature_request_id": "sr1", "signer_email": "bob@example.com"}

        result = await lumin_pdf.execute_action("generate_signing_link", inputs, ctx)

        assert result.result.data["signing_link"] == "https://sign.luminpdf.com/xyz"

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Forbidden")

        result = await lumin_pdf.execute_action(
            "generate_signing_link",
            {"signature_request_id": "sr1", "signer_email": "x@example.com"},
            ctx,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestSendReminder:
    async def test_sends_reminder_with_emails(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={})
        inputs = {"signature_request_id": "sr1", "emails": ["alice@example.com"]}

        result = await lumin_pdf.execute_action("send_reminder", inputs, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["sent"] is True
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["emails"] == ["alice@example.com"]

    async def test_sends_without_emails_fetches_signers(self, make_context):
        from unittest.mock import AsyncMock

        ctx = make_context(auth={"api_key": API_KEY})
        # First call: fetch SR to get signers. Second call: send reminder.
        ctx.fetch = AsyncMock(
            side_effect=[
                FetchResponse(
                    status=200,
                    headers={},
                    data={"signers": [{"email_address": "alice@example.com", "status": "NEED_TO_SIGN"}]},
                ),
                FetchResponse(status=200, headers={}, data={}),
            ]
        )

        result = await lumin_pdf.execute_action("send_reminder", {"signature_request_id": "sr1"}, ctx)

        assert result.result.data["result"] is True
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["emails"] == ["alice@example.com"]

    async def test_no_pending_signers_raises_error(self, make_context):
        from unittest.mock import AsyncMock

        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch = AsyncMock(
            side_effect=[
                FetchResponse(
                    status=200,
                    headers={},
                    data={"signers": [{"email_address": "alice@example.com", "status": "SIGNED"}]},
                ),
            ]
        )

        result = await lumin_pdf.execute_action("send_reminder", {"signature_request_id": "sr1"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "No pending signers" in result.result.message

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Timeout")

        result = await lumin_pdf.execute_action("send_reminder", {"signature_request_id": "sr1"}, ctx)

        assert result.type == ResultType.ACTION_ERROR


# ---- New Actions ----


class TestSendFromTemplate:
    async def test_send_with_required_fields(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr1", "status": "pending"})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [{"name": "Alice", "email_address": "alice@example.com", "signer_role": "signer"}],
        }

        result = await lumin_pdf.execute_action("send_from_template", inputs, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["signature_request"]["id"] == "sr1"
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["template_id"] == "tpl1"
        assert body["title"] == "Contract"
        assert "expires_at" in body

    async def test_send_with_optional_fields(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr2"})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [{"name": "Bob", "email_address": "bob@example.com", "signer_role": "signer"}],
            "message": "Please sign",
            "tags": {"company": "Acme"},
            "fields": {"date": "2026-01-01"},
        }

        await lumin_pdf.execute_action("send_from_template", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        assert body["message"] == "Please sign"
        assert body["tags"] == {"company": "Acme"}
        assert body["fields"] == {"date": "2026-01-01"}

    async def test_normalizes_email_to_email_address(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr5"})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [{"name": "Alice", "email": "alice@example.com", "signer_role": "Employee"}],
        }

        await lumin_pdf.execute_action("send_from_template", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        assert body["signers"][0]["email_address"] == "alice@example.com"
        assert "email" not in body["signers"][0]
        assert body["signers"][0]["signer_role"] == "Employee"

    async def test_role_alias_mapped_to_signer_role(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr6"})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [{"name": "Bob", "email_address": "bob@example.com", "role": "Employer"}],
        }

        await lumin_pdf.execute_action("send_from_template", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        assert body["signers"][0]["signer_role"] == "Employer"
        assert "role" not in body["signers"][0]

    async def test_preserves_verification_payload(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr7"})
        verification = {"type": "SMS", "phone": "+15550001234"}
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [
                {
                    "name": "Alice",
                    "email_address": "alice@example.com",
                    "signer_role": "Employee",
                    "verification": verification,
                }
            ],
        }

        await lumin_pdf.execute_action("send_from_template", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        assert body["signers"][0]["verification"] == verification

    async def test_missing_email_returns_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [{"name": "Alice", "signer_role": "Employee"}],
        }

        result = await lumin_pdf.execute_action("send_from_template", inputs, ctx)

        assert result.type == ResultType.ACTION_ERROR
        assert "email_address" in result.result.message
        ctx.fetch.assert_not_called()

    async def test_missing_name_returns_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [{"email_address": "alice@example.com", "signer_role": "Employee"}],
        }

        result = await lumin_pdf.execute_action("send_from_template", inputs, ctx)

        assert result.type in INVALID_INPUT_TYPES
        ctx.fetch.assert_not_called()

    async def test_due_date_naive_treated_as_utc(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr3"})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [],
            "due_date": "2026-12-31T00:00:00",
        }

        await lumin_pdf.execute_action("send_from_template", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        # 2026-12-31T00:00:00 naive → treated as UTC = 1798675200000 ms
        assert body["expires_at"] == 1798675200000

    async def test_due_date_offset_aware_converted_correctly(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr4"})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [],
            "due_date": "2026-12-31T00:00:00+08:00",
        }

        await lumin_pdf.execute_action("send_from_template", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        # 2026-12-31T00:00:00+08:00 = 2026-12-30T16:00:00Z = 1798646400000 ms
        assert body["expires_at"] == 1798646400000

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Bad template")

        result = await lumin_pdf.execute_action(
            "send_from_template",
            {"template_id": "bad", "title": "T", "signers": []},
            ctx,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateSignatureRequest:
    async def test_updates_expiry(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr1", "expires_at": 9999999999000})
        inputs = {"signature_request_id": "sr1", "due_date": "2026-12-31T00:00:00"}

        result = await lumin_pdf.execute_action("update_signature_request", inputs, ctx)

        assert result.result.data["result"] is True
        assert "signature_request" in result.result.data
        call = ctx.fetch.call_args
        assert call.kwargs["method"] == "PATCH"
        assert f"{BASE_URL}/signature_request/sr1" in call.args[0]
        assert isinstance(call.kwargs["json"]["expires_at"], int)

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Not found")

        result = await lumin_pdf.execute_action(
            "update_signature_request",
            {"signature_request_id": "bad", "due_date": "2026-01-01T00:00:00"},
            ctx,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestDownloadSignedDocument:
    async def test_returns_file_url(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"signed_url": "https://cdn.lumin.com/signed.pdf"}
        )

        result = await lumin_pdf.execute_action("download_signed_document", {"signature_request_id": "sr1"}, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["file_url"] == "https://cdn.lumin.com/signed.pdf"
        assert ctx.fetch.call_args.kwargs["params"] == {"type": "agreement"}
        assert ctx.fetch.call_args.kwargs["headers"].get("Accept") == "application/json"

    async def test_custom_type(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"signed_url": "https://cdn.lumin.com/coc.pdf"}
        )

        await lumin_pdf.execute_action(
            "download_signed_document",
            {"signature_request_id": "sr1", "type": "coc"},
            ctx,
        )

        assert ctx.fetch.call_args.kwargs["params"] == {"type": "coc"}

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Not signed yet")

        result = await lumin_pdf.execute_action("download_signed_document", {"signature_request_id": "sr1"}, ctx)

        assert result.type == ResultType.ACTION_ERROR


class TestUploadDocument:
    async def test_upload_from_url(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "doc1", "name": "My Doc"})
        inputs = {"document_name": "My Doc", "file_url": "https://example.com/doc.pdf"}

        result = await lumin_pdf.execute_action("upload_document", inputs, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["document"]["id"] == "doc1"
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["method"] == "file-upload"
        assert body["document_data"]["file_url"] == "https://example.com/doc.pdf"
        assert body["location"] == {"type": "personal"}

    async def test_upload_from_template(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "doc2"})
        inputs = {"document_name": "From Template", "template_id": "tpl1", "location": "workspace"}

        await lumin_pdf.execute_action("upload_document", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        assert body["method"] == "template"
        assert body["document_data"]["template_id"] == "tpl1"
        assert body["location"] == {"type": "workspace"}

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("File too large")

        result = await lumin_pdf.execute_action("upload_document", {"document_name": "Big File"}, ctx)

        assert result.type == ResultType.ACTION_ERROR


class TestGenerateDocumentFromTemplate:
    async def test_generates_document(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "doc1", "name": "Generated"})
        inputs = {
            "template_id": "tpl1",
            "document_name": "Generated Doc",
            "fields": {"name": "Acme Corp"},
        }

        result = await lumin_pdf.execute_action("generate_document_from_template", inputs, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["document"]["id"] == "doc1"
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["document_name"] == "Generated Doc"
        assert body["fields"] == {"name": "Acme Corp"}
        assert f"{BASE_URL}/templates/tpl1/generate-document" in ctx.fetch.call_args.args[0]
        assert ctx.fetch.call_args.kwargs["headers"].get("Accept") == "application/json"

    async def test_without_optional_fields(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "doc2"})
        inputs = {"template_id": "tpl1", "document_name": "Plain Doc"}

        await lumin_pdf.execute_action("generate_document_from_template", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        assert "fields" not in body
        assert "tags" not in body
        assert "variables" not in body

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Template not found")

        result = await lumin_pdf.execute_action(
            "generate_document_from_template",
            {"template_id": "bad", "document_name": "Doc"},
            ctx,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestCreateAgreement:
    async def test_creates_agreement(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "agr1", "name": "NDA"})
        inputs = {"agreement_name": "NDA", "template_id": "tpl1"}

        result = await lumin_pdf.execute_action("create_agreement", inputs, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["agreement"]["id"] == "agr1"

    async def test_unwraps_nested_agreement_response(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        # API returns {"agreement": {"id": "agr1", ...}} — should be unwrapped
        ctx.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"agreement": {"id": "agr1", "name": "NDA"}}
        )
        inputs = {"agreement_name": "NDA", "template_id": "tpl1"}

        result = await lumin_pdf.execute_action("create_agreement", inputs, ctx)

        assert result.result.data["agreement"]["id"] == "agr1"
        assert "agreement" not in result.result.data["agreement"]
        body = ctx.fetch.call_args.kwargs["json"]
        assert body["method"] == "template"
        assert body["agreement_name"] == "NDA"
        assert body["agreement_data"]["template_id"] == "tpl1"

    async def test_with_optional_data(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "agr2"})
        inputs = {
            "agreement_name": "MSA",
            "template_id": "tpl2",
            "variables": {"party": "Acme"},
            "fields": {"date": "2026-01-01"},
        }

        await lumin_pdf.execute_action("create_agreement", inputs, ctx)

        body = ctx.fetch.call_args.kwargs["json"]
        assert body["agreement_data"]["variables"] == {"party": "Acme"}
        assert body["agreement_data"]["fields"] == {"date": "2026-01-01"}

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Forbidden")

        result = await lumin_pdf.execute_action(
            "create_agreement", {"agreement_name": "NDA", "template_id": "bad"}, ctx
        )

        assert result.type == ResultType.ACTION_ERROR


class TestDownloadAgreement:
    async def test_returns_file_url(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"signed_url": "https://cdn.lumin.com/agreement.pdf"}
        )

        result = await lumin_pdf.execute_action("download_agreement", {"agreement_id": "agr1"}, ctx)

        assert result.result.data["result"] is True
        assert result.result.data["file_url"] == "https://cdn.lumin.com/agreement.pdf"
        assert f"{BASE_URL}/agreements/agr1/file" in ctx.fetch.call_args.args[0]
        assert ctx.fetch.call_args.kwargs["headers"].get("Accept") == "application/json"

    async def test_error(self, make_context):
        ctx = make_context(auth={"api_key": API_KEY})
        ctx.fetch.side_effect = Exception("Not found")

        result = await lumin_pdf.execute_action("download_agreement", {"agreement_id": "bad"}, ctx)

        assert result.type == ResultType.ACTION_ERROR
