import importlib.util
import os

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

from autohive_integrations_sdk import FetchResponse, ResultType  # noqa: E402

_spec = importlib.util.spec_from_file_location("microsoft_word_mod", os.path.join(_parent, "microsoft_word.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

microsoft_word = _mod.microsoft_word
create_docx_from_text = _mod.create_docx_from_text

pytestmark = pytest.mark.unit

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


@pytest.fixture
def mock_context():
    ctx = MagicMock(name="ExecutionContext")
    ctx.fetch = AsyncMock(name="fetch")
    ctx.auth = {
        "auth_type": "PlatformOauth2",
        "credentials": {"access_token": "test_token"},  # nosec B105
    }
    return ctx


def ok(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


SAMPLE_DOCX = create_docx_from_text("Hello world\nSecond paragraph")


# ---- List Documents ----


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok(
            {
                "value": [
                    {"id": "1", "name": "Report.docx", "webUrl": "http://x", "lastModifiedDateTime": "t", "size": 10},
                    {"id": "2", "name": "Image.png"},
                ]
            }
        )

        result = await microsoft_word.execute_action("word_list_documents", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert len(result.result.data["documents"]) == 1
        assert result.result.data["documents"][0]["name"] == "Report.docx"

    @pytest.mark.asyncio
    async def test_next_page_token(self, mock_context):
        mock_context.fetch.return_value = ok({"value": [], "@odata.nextLink": "http://next"})

        result = await microsoft_word.execute_action("word_list_documents", {}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["next_page_token"] == "http://next"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await microsoft_word.execute_action("word_list_documents", {}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "boom" in result.result.message


# ---- Get Document ----


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "d1", "name": "Report.docx"})

        result = await microsoft_word.execute_action("word_get_document", {"document_id": "d1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["document"]["id"] == "d1"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await microsoft_word.execute_action("word_get_document", {"document_id": "d1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Get Content ----


class TestGetContent:
    @pytest.mark.asyncio
    async def test_success_text(self, mock_context):
        mock_context.fetch.return_value = ok(SAMPLE_DOCX)

        result = await microsoft_word.execute_action("word_get_content", {"document_id": "d1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert "Hello world" in result.result.data["content"]
        assert result.result.data["word_count"] > 0

    @pytest.mark.asyncio
    async def test_success_with_metadata(self, mock_context):
        async def fetch_side_effect(url, method="GET", **kwargs):
            if url.endswith("/content"):
                return ok(SAMPLE_DOCX)
            return ok({"id": "d1", "name": "Report.docx"})

        mock_context.fetch.side_effect = fetch_side_effect

        result = await microsoft_word.execute_action(
            "word_get_content", {"document_id": "d1", "include_metadata": True}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["metadata"]["name"] == "Report.docx"

    @pytest.mark.asyncio
    async def test_non_bytes_content(self, mock_context):
        mock_context.fetch.return_value = ok({"error": "not found"})

        result = await microsoft_word.execute_action("word_get_content", {"document_id": "d1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to download" in result.result.message

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await microsoft_word.execute_action("word_get_content", {"document_id": "d1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Create Document ----


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_success_without_template(self, mock_context):
        mock_context.fetch.return_value = ok({"id": "d1", "name": "New.docx", "webUrl": "http://x"})

        result = await microsoft_word.execute_action(
            "word_create_document", {"name": "New", "content": "Hello"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["document_id"] == "d1"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await microsoft_word.execute_action("word_create_document", {"name": "New"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Update Content ----


class TestUpdateContent:
    @pytest.mark.asyncio
    async def test_success_without_preserve_formatting(self, mock_context):
        mock_context.fetch.return_value = ok({})

        result = await microsoft_word.execute_action(
            "word_update_content", {"document_id": "d1", "content": "New content"}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["updated"] is True

    @pytest.mark.asyncio
    async def test_preserve_formatting_non_bytes(self, mock_context):
        mock_context.fetch.return_value = ok({"error": "bad"})

        result = await microsoft_word.execute_action(
            "word_update_content",
            {"document_id": "d1", "content": "New content", "preserve_formatting": True},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to download" in result.result.message

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await microsoft_word.execute_action(
            "word_update_content", {"document_id": "d1", "content": "New content"}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Insert Text ----


class TestInsertText:
    @pytest.mark.asyncio
    async def test_success_start(self, mock_context):
        async def fetch_side_effect(url, method="GET", **kwargs):
            if method == "GET":
                return ok(SAMPLE_DOCX)
            return ok({})

        mock_context.fetch.side_effect = fetch_side_effect

        result = await microsoft_word.execute_action(
            "word_insert_text",
            {"document_id": "d1", "text": "Inserted", "location": "start"},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["inserted"] is True

    @pytest.mark.asyncio
    async def test_negative_paragraph_index(self, mock_context):
        result = await microsoft_word.execute_action(
            "word_insert_text",
            {
                "document_id": "d1",
                "text": "x",
                "location": "after_paragraph",
                "paragraph_index": -1,
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "non-negative" in result.result.message

    @pytest.mark.asyncio
    async def test_invalid_location(self, mock_context):
        # "location" is an enum in the input schema, so the SDK's validation
        # layer rejects an out-of-enum value before execute() ever runs.
        result = await microsoft_word.execute_action(
            "word_insert_text",
            {"document_id": "d1", "text": "x", "location": "nowhere"},
            mock_context,
        )

        assert result.type == ResultType.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await microsoft_word.execute_action(
            "word_insert_text",
            {"document_id": "d1", "text": "x", "location": "end"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Get Paragraphs ----


class TestGetParagraphs:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok(SAMPLE_DOCX)

        result = await microsoft_word.execute_action("word_get_paragraphs", {"document_id": "d1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["total_count"] == 2

    @pytest.mark.asyncio
    async def test_negative_start_index(self, mock_context):
        result = await microsoft_word.execute_action(
            "word_get_paragraphs", {"document_id": "d1", "start_index": -1}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "non-negative" in result.result.message

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await microsoft_word.execute_action("word_get_paragraphs", {"document_id": "d1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Search Replace ----


class TestSearchReplace:
    @pytest.mark.asyncio
    async def test_success(self, mock_context):
        mock_context.fetch.return_value = ok(SAMPLE_DOCX)

        result = await microsoft_word.execute_action(
            "word_search_replace",
            {"document_id": "d1", "search_text": "Hello", "replace_text": "Hi"},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["replaced"] is True

    @pytest.mark.asyncio
    async def test_empty_search_text(self, mock_context):
        result = await microsoft_word.execute_action(
            "word_search_replace",
            {"document_id": "d1", "search_text": "", "replace_text": "Hi"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "cannot be empty" in result.result.message

    @pytest.mark.asyncio
    async def test_no_match(self, mock_context):
        mock_context.fetch.return_value = ok(SAMPLE_DOCX)

        result = await microsoft_word.execute_action(
            "word_search_replace",
            {"document_id": "d1", "search_text": "NotFound", "replace_text": "Hi"},
            mock_context,
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["replaced"] is False

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await microsoft_word.execute_action(
            "word_search_replace",
            {"document_id": "d1", "search_text": "Hello", "replace_text": "Hi"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR


# ---- Export PDF ----


class TestExportPdf:
    @pytest.mark.asyncio
    async def test_success_base64(self, mock_context):
        mock_context.fetch.return_value = ok(b"%PDF-1.4 fake pdf bytes")

        result = await microsoft_word.execute_action("word_export_pdf", {"document_id": "d1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["encoding"] == "base64"

    @pytest.mark.asyncio
    async def test_non_bytes_pdf(self, mock_context):
        mock_context.fetch.return_value = ok({"error": "bad"})

        result = await microsoft_word.execute_action("word_export_pdf", {"document_id": "d1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to convert" in result.result.message

    @pytest.mark.asyncio
    async def test_save_to_drive(self, mock_context):
        async def fetch_side_effect(url, method="GET", **kwargs):
            if "content?format=pdf" in url:
                return ok(b"%PDF-1.4 fake pdf bytes")
            if method == "PUT":
                return ok({"webUrl": "http://x", "id": "pdf1", "size": 100})
            return ok({"name": "Report.docx"})

        mock_context.fetch.side_effect = fetch_side_effect

        result = await microsoft_word.execute_action(
            "word_export_pdf", {"document_id": "d1", "save_to_drive": True}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["pdf_id"] == "pdf1"

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await microsoft_word.execute_action("word_export_pdf", {"document_id": "d1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR


# ---- Get Tables ----


class TestGetTables:
    @pytest.mark.asyncio
    async def test_success_empty(self, mock_context):
        mock_context.fetch.return_value = ok(SAMPLE_DOCX)

        result = await microsoft_word.execute_action("word_get_tables", {"document_id": "d1"}, mock_context)

        assert result.type != ResultType.ACTION_ERROR
        assert result.result.data["table_count"] == 0

    @pytest.mark.asyncio
    async def test_index_out_of_range(self, mock_context):
        mock_context.fetch.return_value = ok(SAMPLE_DOCX)

        result = await microsoft_word.execute_action(
            "word_get_tables", {"document_id": "d1", "table_index": 5}, mock_context
        )

        assert result.type != ResultType.ACTION_ERROR
        assert "warning" in result.result.data

    @pytest.mark.asyncio
    async def test_non_bytes_content(self, mock_context):
        mock_context.fetch.return_value = ok({"error": "bad"})

        result = await microsoft_word.execute_action("word_get_tables", {"document_id": "d1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
        assert "Failed to download" in result.result.message

    @pytest.mark.asyncio
    async def test_error(self, mock_context):
        mock_context.fetch.side_effect = Exception("boom")

        result = await microsoft_word.execute_action("word_get_tables", {"document_id": "d1"}, mock_context)

        assert result.type == ResultType.ACTION_ERROR
