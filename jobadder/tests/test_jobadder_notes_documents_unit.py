import base64
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from autohive_integrations_sdk import FetchResponse
from autohive_integrations_sdk.integration import ResultType

from jobadder.jobadder import MAX_CANDIDATE_ATTACHMENT_BYTES, _decode_file, _download_candidate_attachment, jobadder


pytestmark = pytest.mark.unit


def response(data, status=200):
    return FetchResponse(status=status, headers={}, data=data)


def list_payload(items=None, total_count=0):
    return {"items": items or [], "totalCount": total_count, "links": {}}


class FakeBinaryContent:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    async def read(self, size):
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if len(chunk) <= size:
            return chunk
        self.chunks.insert(0, chunk[size:])
        return chunk[:size]


class FakeBinaryResponse:
    def __init__(self, *, status=200, headers=None, chunks=None, error_text=""):
        self.status = status
        self.headers = headers or {}
        self.content = FakeBinaryContent(chunks or [])
        self.error_text = error_text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def text(self):
        return self.error_text


class FakeBinarySession:
    def __init__(self, response):
        self.get = MagicMock(return_value=response)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class TestDownloadCandidateAttachmentTransport:
    @pytest.mark.asyncio
    async def test_sends_auth_and_accept_and_streams_binary(self, mock_context):
        response = FakeBinaryResponse(
            headers={"Content-Type": "application/pdf", "Content-Length": "7"},
            chunks=[b"abc", b"defg"],
        )
        session = FakeBinarySession(response)

        with patch("jobadder.jobadder.aiohttp.ClientSession", return_value=session):
            content, headers = await _download_candidate_attachment(mock_context, 21, 9001, "application/pdf")

        assert content == b"abcdefg"
        assert headers["Content-Type"] == "application/pdf"
        session.get.assert_called_once_with(
            "https://au-api.jobadder.com/v2/candidates/21/attachments/9001",
            headers={"Authorization": "Bearer test_access_token", "Accept": "application/pdf"},
            ssl=True,
        )

    @pytest.mark.asyncio
    async def test_rejects_declared_oversized_download(self, mock_context):
        response = FakeBinaryResponse(headers={"Content-Length": str(MAX_CANDIDATE_ATTACHMENT_BYTES + 1)})
        session = FakeBinarySession(response)

        with (
            patch("jobadder.jobadder.aiohttp.ClientSession", return_value=session),
            pytest.raises(ValueError, match="exceeds the 5 MiB download limit"),
        ):
            await _download_candidate_attachment(mock_context, 21, 9001, "application/octet-stream")

    @pytest.mark.asyncio
    async def test_rejects_stream_that_exceeds_limit_without_content_length(self, mock_context):
        response = FakeBinaryResponse(chunks=[b"12345"])
        session = FakeBinarySession(response)

        with (
            patch("jobadder.jobadder.MAX_CANDIDATE_ATTACHMENT_BYTES", 4),
            patch("jobadder.jobadder.aiohttp.ClientSession", return_value=session),
            pytest.raises(ValueError, match="download limit"),
        ):
            await _download_candidate_attachment(mock_context, 21, 9001, "application/octet-stream")

    @pytest.mark.asyncio
    async def test_non_success_response_includes_only_provider_status(self, mock_context):
        response = FakeBinaryResponse(status=404, error_text="Attachment not found")
        session = FakeBinarySession(response)

        with (
            patch("jobadder.jobadder.aiohttp.ClientSession", return_value=session),
            pytest.raises(RuntimeError, match=r"HTTP 404\.$") as error,
        ):
            await _download_candidate_attachment(mock_context, 21, 9001, "application/octet-stream")

        assert "Attachment not found" not in str(error.value)


class TestDecodeCandidateAttachment:
    def test_accepts_file_at_upload_limit(self):
        with patch("jobadder.jobadder.MAX_CANDIDATE_ATTACHMENT_BYTES", 4):
            file_bytes, file_name, content_type = _decode_file(
                {
                    "content": base64.b64encode(b"1234").decode("ascii"),
                    "name": "document.txt",
                    "contentType": "text/plain",
                }
            )

        assert file_bytes == b"1234"
        assert file_name == "document.txt"
        assert content_type == "text/plain"

    def test_rejects_oversized_encoded_input_before_decoding(self):
        with (
            patch("jobadder.jobadder.MAX_CANDIDATE_ATTACHMENT_BYTES", 3),
            patch("jobadder.jobadder.base64.b64decode") as decode_mock,
            pytest.raises(ValueError, match="upload limit"),
        ):
            _decode_file({"content": "A" * 8, "name": "document.txt", "contentType": "text/plain"})

        decode_mock.assert_not_called()

    def test_rejects_decoded_file_over_upload_limit(self):
        with (
            patch("jobadder.jobadder.MAX_CANDIDATE_ATTACHMENT_BYTES", 4),
            pytest.raises(ValueError, match="upload limit"),
        ):
            _decode_file(
                {
                    "content": base64.b64encode(b"12345").decode("ascii"),
                    "name": "document.txt",
                    "contentType": "text/plain",
                }
            )


NOTE_TYPE_CASES = [
    ("list_candidate_note_types", "/candidates/lists/notetype"),
    ("list_contact_note_types", "/contacts/lists/notetype"),
    ("list_job_note_types", "/jobs/lists/notetype"),
    ("list_placement_note_types", "/placements/lists/notetype"),
    ("list_company_note_types", "/companies/lists/notetype"),
]


@pytest.mark.parametrize("action,path", NOTE_TYPE_CASES)
@pytest.mark.asyncio
async def test_list_note_types_maps_endpoint_and_name_filter(mock_context, action, path):
    note_types = [{"name": "Reference Check"}]
    mock_context.fetch.return_value = response(list_payload(note_types, 1))

    result = await jobadder.execute_action(action, {"name": "Reference"}, mock_context)

    assert result.result.data["note_types"] == note_types
    mock_context.fetch.assert_awaited_once_with(
        f"https://au-api.jobadder.com/v2{path}", method="GET", params={"name": "Reference"}
    )


@pytest.mark.parametrize("action,_path", NOTE_TYPE_CASES)
@pytest.mark.asyncio
async def test_list_note_types_returns_action_error(mock_context, action, _path):
    mock_context.fetch.side_effect = Exception("note types unavailable")

    result = await jobadder.execute_action(action, {}, mock_context)

    assert result.type == ResultType.ACTION_ERROR
    assert "note types unavailable" in result.result.message


NOTE_LIST_CASES = [
    ("list_candidate_notes", "candidate_id", 21, "/candidates/21/notes"),
    ("list_contact_notes", "contact_id", 31, "/contacts/31/notes"),
    ("list_job_notes", "job_id", 41, "/jobs/41/notes"),
    ("list_placement_notes", "placement_id", 51, "/placements/51/notes"),
    ("list_company_notes", "company_id", 61, "/companies/61/notes"),
]


@pytest.mark.parametrize("action,id_key,record_id,path", NOTE_LIST_CASES)
@pytest.mark.asyncio
async def test_record_note_lists_map_common_filters(mock_context, action, id_key, record_id, path):
    mock_context.fetch.return_value = response(list_payload())
    inputs = {
        id_key: record_id,
        "types": ["Reference Check"],
        "references": ["REF-42"],
        "created_at_from": "2026-09-01T00:00:00Z",
        "created_at_to": "2026-09-30T23:59:59Z",
        "updated_at_from": "2026-09-15T00:00:00Z",
        "updated_at_to": "2026-09-30T23:59:59Z",
        "sort": "createdAt",
        "offset": 10,
        "limit": 25,
    }

    await jobadder.execute_action(action, inputs, mock_context)

    call = mock_context.fetch.call_args
    parsed_url = urlparse(call.args[0])
    assert f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}" == f"https://au-api.jobadder.com/v2{path}"
    assert parse_qs(parsed_url.query) == {
        "type": ["Reference Check"],
        "reference": ["REF-42"],
        "createdAt": [">2026-09-01T00:00:00Z", "<2026-09-30T23:59:59Z"],
        "updatedAt": [">2026-09-15T00:00:00Z", "<2026-09-30T23:59:59Z"],
        "fields": ["text"],
    }
    assert call.kwargs["params"] == {
        "sort": "createdAt",
        "offset": 10,
        "limit": 25,
    }


class TestCandidateAttachments:
    @pytest.mark.asyncio
    async def test_list_maps_type_category_and_latest_filters(self, mock_context):
        mock_context.fetch.return_value = response(list_payload())

        await jobadder.execute_action(
            "list_candidate_attachments",
            {
                "candidate_id": 21,
                "types": ["Resume", "Reference"],
                "categories": ["Work Rights"],
                "latest": False,
                "offset": 5,
                "limit": 20,
            },
            mock_context,
        )

        call = mock_context.fetch.call_args
        assert parse_qs(urlparse(call.args[0]).query) == {
            "type": ["Resume", "Reference"],
            "category": ["Work Rights"],
        }
        assert call.kwargs["params"] == {
            "latest": "false",
            "offset": 5,
            "limit": 20,
        }

    @pytest.mark.asyncio
    async def test_list_categories_maps_type_filter(self, mock_context):
        categories = [{"name": "Cultivate Candidate Form", "type": "Other"}]
        mock_context.fetch.return_value = response(list_payload(categories, 1))

        result = await jobadder.execute_action(
            "list_candidate_attachment_categories", {"types": ["Other", "Check"]}, mock_context
        )

        assert result.result.data["categories"] == categories
        mock_context.fetch.assert_awaited_once_with(
            "https://au-api.jobadder.com/v2/candidates/lists/attachmentcategory?type=Other&type=Check",
            method="GET",
        )

    @pytest.mark.asyncio
    @patch("jobadder.jobadder._download_candidate_attachment", new_callable=AsyncMock)
    async def test_download_returns_autohive_file(self, download_mock, mock_context):
        download_mock.return_value = (b"reformatted cv", {"Content-Type": "application/pdf; charset=binary"})

        result = await jobadder.execute_action(
            "download_candidate_attachment",
            {
                "candidate_id": 21,
                "attachment_id": 9001,
                "file_name": "candidate-cv.pdf",
                "accept": "application/pdf",
            },
            mock_context,
        )

        assert result.result.data["file"] == {
            "name": "candidate-cv.pdf",
            "contentType": "application/pdf",
            "content": base64.b64encode(b"reformatted cv").decode("ascii"),
        }
        download_mock.assert_awaited_once_with(mock_context, 21, 9001, "application/pdf")

    @pytest.mark.asyncio
    @patch("jobadder.jobadder._download_candidate_attachment", new_callable=AsyncMock)
    async def test_download_error_returns_action_error(self, download_mock, mock_context):
        download_mock.side_effect = RuntimeError("attachment unavailable")

        result = await jobadder.execute_action(
            "download_candidate_attachment", {"candidate_id": 21, "attachment_id": 9001}, mock_context
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "attachment unavailable" in result.result.message

    @pytest.mark.asyncio
    async def test_upload_sends_multipart_file(self, mock_context):
        attachment = {"attachmentId": 9001, "type": "FormattedResume"}
        mock_context.fetch.return_value = response(attachment, status=201)

        result = await jobadder.execute_action(
            "upload_candidate_attachment",
            {
                "candidate_id": 21,
                "attachment_type": "FormattedResume",
                "file": {
                    "name": "formatted-cv.pdf",
                    "contentType": "application/pdf",
                    "content": base64.b64encode(b"formatted cv").decode("ascii"),
                },
            },
            mock_context,
        )

        assert result.result.data["attachment"] == attachment
        call = mock_context.fetch.call_args
        assert call.args[0].endswith("/candidates/21/attachments/FormattedResume")
        assert call.kwargs["method"] == "POST"
        form = call.kwargs["data"]
        field_options, field_headers, field_value = form._fields[0]
        assert field_options["name"] == "fileData"
        assert field_options["filename"] == "formatted-cv.pdf"
        assert field_headers["Content-Type"] == "application/pdf"
        assert field_value == b"formatted cv"

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_base64(self, mock_context):
        result = await jobadder.execute_action(
            "upload_candidate_attachment",
            {
                "candidate_id": 21,
                "attachment_type": "Resume",
                "file": {"name": "cv.pdf", "contentType": "application/pdf", "content": "not-base64!"},
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "not valid base64" in result.result.message
        mock_context.fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_provider_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("upload unavailable")

        result = await jobadder.execute_action(
            "upload_candidate_attachment",
            {
                "candidate_id": 21,
                "attachment_type": "Resume",
                "file": {
                    "name": "cv.pdf",
                    "contentType": "application/pdf",
                    "content": base64.b64encode(b"cv").decode("ascii"),
                },
            },
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "upload unavailable" in result.result.message

    @pytest.mark.asyncio
    async def test_update_maps_metadata_body(self, mock_context):
        attachment = {"attachmentId": 9001, "type": "Check", "category": "Work Rights"}
        mock_context.fetch.return_value = response(attachment)

        result = await jobadder.execute_action(
            "update_candidate_attachment",
            {
                "candidate_id": 21,
                "attachment_id": 9001,
                "type": "Check",
                "category": "Work Rights",
                "expiry": "2027-09-30",
            },
            mock_context,
        )

        assert result.result.data["attachment"] == attachment
        mock_context.fetch.assert_awaited_once_with(
            "https://au-api.jobadder.com/v2/candidates/21/attachments/9001",
            method="PUT",
            headers={"Content-Type": "application/json"},
            json={"type": "Check", "category": "Work Rights", "expiry": "2027-09-30"},
        )

    @pytest.mark.asyncio
    async def test_update_sends_nulls_to_clear_category_and_expiry(self, mock_context):
        mock_context.fetch.return_value = response({"attachmentId": 9001, "category": None, "expiry": None})

        await jobadder.execute_action(
            "update_candidate_attachment",
            {"candidate_id": 21, "attachment_id": 9001, "category": None, "expiry": None},
            mock_context,
        )

        mock_context.fetch.assert_awaited_once_with(
            "https://au-api.jobadder.com/v2/candidates/21/attachments/9001",
            method="PUT",
            headers={"Content-Type": "application/json"},
            json={"category": None, "expiry": None},
        )

    @pytest.mark.asyncio
    async def test_update_provider_error_returns_action_error(self, mock_context):
        mock_context.fetch.side_effect = RuntimeError("update unavailable")

        result = await jobadder.execute_action(
            "update_candidate_attachment",
            {"candidate_id": 21, "attachment_id": 9001, "type": "Resume"},
            mock_context,
        )

        assert result.type == ResultType.ACTION_ERROR
        assert "update unavailable" in result.result.message
