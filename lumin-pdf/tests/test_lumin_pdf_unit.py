import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import AsyncMock, MagicMock

from autohive_integrations_sdk import FetchResponse, ResultType
from lumin_pdf import lumin_pdf

pytestmark = pytest.mark.unit

BASE_URL = "https://api.luminpdf.com/v1"
API_KEY = "test_api_key"  # nosec B105


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {"api_key": API_KEY}
    return ctx


# ---- User & Workspace ----


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_returns_user(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"id": "u1", "email": "test@example.com"}
        )

        result = await lumin_pdf.execute_action("get_current_user", {}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["user"] == {"id": "u1", "email": "test@example.com"}
        mock_context.fetch.assert_called_once_with(
            f"{BASE_URL}/user/info", method="GET", headers={"X-API-KEY": API_KEY}
        )

    @pytest.mark.asyncio
    async def test_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Unauthorized")

        result = await lumin_pdf.execute_action("get_current_user", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Unauthorized" in result.result.message


class TestGetWorkspace:
    @pytest.mark.asyncio
    async def test_returns_workspace(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"id": "ws1", "name": "My Workspace"}
        )

        result = await lumin_pdf.execute_action("get_workspace", {}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["workspace"] == {"id": "ws1", "name": "My Workspace"}
        mock_context.fetch.assert_called_once_with(
            f"{BASE_URL}/workspaces/info", method="GET", headers={"X-API-KEY": API_KEY}
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await lumin_pdf.execute_action("get_workspace", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestListWorkspaceMembers:
    @pytest.mark.asyncio
    async def test_returns_members_list(self, mock_context):
        members = [{"id": "m1"}, {"id": "m2"}]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=members)

        result = await lumin_pdf.execute_action("list_workspace_members", {"limit": 10}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["members"] == members
        call_kwargs = mock_context.fetch.call_args
        assert call_kwargs.kwargs["params"] == {"page": 1, "limit": 10}

    @pytest.mark.asyncio
    async def test_returns_members_from_data_key(self, mock_context):
        members = [{"id": "m1"}]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"data": members, "total": 1})

        result = await lumin_pdf.execute_action("list_workspace_members", {}, mock_context)

        assert result.result.data["members"] == members

    @pytest.mark.asyncio
    async def test_default_page(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=[])

        await lumin_pdf.execute_action("list_workspace_members", {}, mock_context)

        params = mock_context.fetch.call_args.kwargs["params"]
        assert params["page"] == 1
        assert "limit" not in params


# ---- Templates ----


class TestListTemplates:
    @pytest.mark.asyncio
    async def test_returns_templates_list(self, mock_context):
        templates = [{"id": "t1", "name": "NDA"}]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data=templates)

        result = await lumin_pdf.execute_action("list_templates", {"limit": 5}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["templates"] == templates

    @pytest.mark.asyncio
    async def test_returns_templates_from_data_key(self, mock_context):
        templates = [{"id": "t1"}]
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"templates": templates})

        result = await lumin_pdf.execute_action("list_templates", {}, mock_context)

        assert result.result.data["templates"] == templates

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Server error")

        result = await lumin_pdf.execute_action("list_templates", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGetTemplate:
    @pytest.mark.asyncio
    async def test_returns_template(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "t1", "name": "NDA"})

        result = await lumin_pdf.execute_action("get_template", {"template_id": "t1"}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["template"] == {"id": "t1", "name": "NDA"}
        mock_context.fetch.assert_called_once_with(
            f"{BASE_URL}/templates/t1", method="GET", headers={"X-API-KEY": API_KEY}
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await lumin_pdf.execute_action("get_template", {"template_id": "bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Signature Requests ----


class TestSendSignatureRequest:
    @pytest.mark.asyncio
    async def test_send_with_file_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr1", "status": "pending"})
        inputs = {
            "title": "Test Doc",
            "file_url": "https://example.com/doc.pdf",
            "signers": [{"name": "Alice", "email_address": "alice@example.com"}],
        }

        result = await lumin_pdf.execute_action("send_signature_request", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["signature_request"]["id"] == "sr1"
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["title"] == "Test Doc"
        assert body["file_url"] == "https://example.com/doc.pdf"
        assert body["signers"] == [{"name": "Alice", "email_address": "alice@example.com"}]
        assert "expires_at" in body

    @pytest.mark.asyncio
    async def test_send_normalizes_email_field(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr2"})
        inputs = {
            "title": "Test",
            "file_url": "https://example.com/doc.pdf",
            "signers": [{"name": "Bob", "email": "bob@example.com"}],
        }

        await lumin_pdf.execute_action("send_signature_request", inputs, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["signers"][0]["email_address"] == "bob@example.com"

    @pytest.mark.asyncio
    async def test_send_with_file_urls(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr3"})
        inputs = {
            "title": "Multi",
            "file_urls": ["https://example.com/a.pdf", "https://example.com/b.pdf"],
            "signers": [{"name": "Carol", "email_address": "carol@example.com"}],
        }

        await lumin_pdf.execute_action("send_signature_request", inputs, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert "file_urls" in body
        assert "file_url" not in body

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Bad request")

        result = await lumin_pdf.execute_action(
            "send_signature_request",
            {"title": "T", "signers": []},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGetSignatureRequest:
    @pytest.mark.asyncio
    async def test_returns_signature_request(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr1", "status": "pending"})

        result = await lumin_pdf.execute_action("get_signature_request", {"signature_request_id": "sr1"}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["signature_request"]["id"] == "sr1"
        mock_context.fetch.assert_called_once_with(
            f"{BASE_URL}/signature_request/sr1",
            method="GET",
            headers={"X-API-KEY": API_KEY},
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await lumin_pdf.execute_action("get_signature_request", {"signature_request_id": "bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestCancelSignatureRequest:
    @pytest.mark.asyncio
    async def test_cancels_request(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await lumin_pdf.execute_action(
            "cancel_signature_request", {"signature_request_id": "sr1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["canceled"] is True
        mock_context.fetch.assert_called_once_with(
            f"{BASE_URL}/signature_request/cancel/sr1",
            method="PUT",
            headers={"X-API-KEY": API_KEY},
            json={},
        )

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Already canceled")

        result = await lumin_pdf.execute_action(
            "cancel_signature_request", {"signature_request_id": "sr1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestGenerateSigningLink:
    @pytest.mark.asyncio
    async def test_returns_view_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"view_url": "https://sign.luminpdf.com/abc"}
        )
        inputs = {"signature_request_id": "sr1", "signer_email": "alice@example.com"}

        result = await lumin_pdf.execute_action("generate_signing_link", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["signing_link"] == "https://sign.luminpdf.com/abc"

    @pytest.mark.asyncio
    async def test_falls_back_to_url_key(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"url": "https://sign.luminpdf.com/xyz"}
        )
        inputs = {"signature_request_id": "sr1", "signer_email": "bob@example.com"}

        result = await lumin_pdf.execute_action("generate_signing_link", inputs, mock_context)

        assert result.result.data["signing_link"] == "https://sign.luminpdf.com/xyz"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await lumin_pdf.execute_action(
            "generate_signing_link",
            {"signature_request_id": "sr1", "signer_email": "x@example.com"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestSendReminder:
    @pytest.mark.asyncio
    async def test_sends_reminder(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})
        inputs = {"signature_request_id": "sr1", "emails": ["alice@example.com"]}

        result = await lumin_pdf.execute_action("send_reminder", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["sent"] is True
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["emails"] == ["alice@example.com"]

    @pytest.mark.asyncio
    async def test_sends_without_emails(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={})

        result = await lumin_pdf.execute_action("send_reminder", {"signature_request_id": "sr1"}, mock_context)

        assert result.result.data["result"] is True
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body == {}

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Timeout")

        result = await lumin_pdf.execute_action("send_reminder", {"signature_request_id": "sr1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- New Actions ----


class TestSendFromTemplate:
    @pytest.mark.asyncio
    async def test_send_with_required_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr1", "status": "pending"})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [{"name": "Alice", "signer_role": "signer"}],
        }

        result = await lumin_pdf.execute_action("send_from_template", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["signature_request"]["id"] == "sr1"
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["template_id"] == "tpl1"
        assert body["title"] == "Contract"
        assert "expires_at" in body

    @pytest.mark.asyncio
    async def test_send_with_optional_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr2"})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [{"name": "Bob", "signer_role": "signer"}],
            "message": "Please sign",
            "tags": {"company": "Acme"},
            "fields": {"date": "2026-01-01"},
        }

        await lumin_pdf.execute_action("send_from_template", inputs, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["message"] == "Please sign"
        assert body["tags"] == {"company": "Acme"}
        assert body["fields"] == {"date": "2026-01-01"}

    @pytest.mark.asyncio
    async def test_due_date_converted_to_millis(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "sr3"})
        inputs = {
            "template_id": "tpl1",
            "title": "Contract",
            "signers": [],
            "due_date": "2026-12-31T00:00:00",
        }

        await lumin_pdf.execute_action("send_from_template", inputs, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert isinstance(body["expires_at"], int)
        assert body["expires_at"] > 1_000_000_000_000  # epoch millis

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Bad template")

        result = await lumin_pdf.execute_action(
            "send_from_template",
            {"template_id": "bad", "title": "T", "signers": []},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestUpdateSignatureRequest:
    @pytest.mark.asyncio
    async def test_updates_expiry(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"id": "sr1", "expires_at": 9999999999000}
        )
        inputs = {"signature_request_id": "sr1", "due_date": "2026-12-31T00:00:00"}

        result = await lumin_pdf.execute_action("update_signature_request", inputs, mock_context)

        assert result.result.data["result"] is True
        assert "signature_request" in result.result.data
        call = mock_context.fetch.call_args
        assert call.kwargs["method"] == "PATCH"
        assert f"{BASE_URL}/signature_request/sr1" in call.args[0]
        assert isinstance(call.kwargs["json"]["expires_at"], int)

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await lumin_pdf.execute_action(
            "update_signature_request",
            {"signature_request_id": "bad", "due_date": "2026-01-01T00:00:00"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestDownloadSignedDocument:
    @pytest.mark.asyncio
    async def test_returns_file_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"file_url": "https://cdn.lumin.com/signed.pdf"}
        )

        result = await lumin_pdf.execute_action(
            "download_signed_document", {"signature_request_id": "sr1"}, mock_context
        )

        assert result.result.data["result"] is True
        assert result.result.data["file_url"] == "https://cdn.lumin.com/signed.pdf"
        call = mock_context.fetch.call_args
        assert call.kwargs["params"] == {"type": "agreement"}

    @pytest.mark.asyncio
    async def test_custom_type(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"file_url": "https://cdn.lumin.com/coc.pdf"}
        )

        await lumin_pdf.execute_action(
            "download_signed_document",
            {"signature_request_id": "sr1", "type": "coc"},
            mock_context,
        )

        assert mock_context.fetch.call_args.kwargs["params"] == {"type": "coc"}

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not signed yet")

        result = await lumin_pdf.execute_action(
            "download_signed_document", {"signature_request_id": "sr1"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestUploadDocument:
    @pytest.mark.asyncio
    async def test_upload_from_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "doc1", "name": "My Doc"})
        inputs = {"document_name": "My Doc", "file_url": "https://example.com/doc.pdf"}

        result = await lumin_pdf.execute_action("upload_document", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["document"]["id"] == "doc1"
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["method"] == "file-upload"
        assert body["document_data"]["file_url"] == "https://example.com/doc.pdf"
        assert body["location"] == "personal"

    @pytest.mark.asyncio
    async def test_upload_from_template(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "doc2"})
        inputs = {"document_name": "From Template", "template_id": "tpl1", "location": "workspace"}

        await lumin_pdf.execute_action("upload_document", inputs, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["method"] == "template"
        assert body["document_data"]["template_id"] == "tpl1"
        assert body["location"] == "workspace"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("File too large")

        result = await lumin_pdf.execute_action("upload_document", {"document_name": "Big File"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


class TestGenerateDocumentFromTemplate:
    @pytest.mark.asyncio
    async def test_generates_document(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"id": "doc1", "name": "Generated"}
        )
        inputs = {
            "template_id": "tpl1",
            "document_name": "Generated Doc",
            "fields": {"name": "Acme Corp"},
        }

        result = await lumin_pdf.execute_action("generate_document_from_template", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["document"]["id"] == "doc1"
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["document_name"] == "Generated Doc"
        assert body["fields"] == {"name": "Acme Corp"}
        assert f"{BASE_URL}/templates/tpl1/generate-document" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_without_optional_fields(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "doc2"})
        inputs = {"template_id": "tpl1", "document_name": "Plain Doc"}

        await lumin_pdf.execute_action("generate_document_from_template", inputs, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert "fields" not in body
        assert "tags" not in body
        assert "variables" not in body

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Template not found")

        result = await lumin_pdf.execute_action(
            "generate_document_from_template",
            {"template_id": "bad", "document_name": "Doc"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


class TestCreateAgreement:
    @pytest.mark.asyncio
    async def test_creates_agreement(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "agr1", "name": "NDA"})
        inputs = {"agreement_name": "NDA", "template_id": "tpl1"}

        result = await lumin_pdf.execute_action("create_agreement", inputs, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["agreement"]["id"] == "agr1"
        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["method"] == "template"
        assert body["agreement_name"] == "NDA"
        assert body["agreement_data"]["template_id"] == "tpl1"

    @pytest.mark.asyncio
    async def test_with_optional_data(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(status=200, headers={}, data={"id": "agr2"})
        inputs = {
            "agreement_name": "MSA",
            "template_id": "tpl2",
            "variables": {"party": "Acme"},
            "fields": {"date": "2026-01-01"},
        }

        await lumin_pdf.execute_action("create_agreement", inputs, mock_context)

        body = mock_context.fetch.call_args.kwargs["json"]
        assert body["agreement_data"]["variables"] == {"party": "Acme"}
        assert body["agreement_data"]["fields"] == {"date": "2026-01-01"}

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Forbidden")

        result = await lumin_pdf.execute_action(
            "create_agreement", {"agreement_name": "NDA", "template_id": "bad"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


class TestDownloadAgreement:
    @pytest.mark.asyncio
    async def test_returns_file_url(self, mock_context):
        mock_context.fetch.return_value = FetchResponse(
            status=200, headers={}, data={"file_url": "https://cdn.lumin.com/agreement.pdf"}
        )

        result = await lumin_pdf.execute_action("download_agreement", {"agreement_id": "agr1"}, mock_context)

        assert result.result.data["result"] is True
        assert result.result.data["file_url"] == "https://cdn.lumin.com/agreement.pdf"
        assert f"{BASE_URL}/agreements/agr1/file" in mock_context.fetch.call_args.args[0]

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("Not found")

        result = await lumin_pdf.execute_action("download_agreement", {"agreement_id": "bad"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
