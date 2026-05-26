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
