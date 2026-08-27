import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from unittest.mock import AsyncMock, patch
from autohive_integrations_sdk import FetchResponse, ResultType
from microsoft365.microsoft365 import microsoft365

pytestmark = pytest.mark.unit


def make_fetch(data):
    return AsyncMock(return_value=FetchResponse(status=200, headers={}, data=data))


# ---- send_email ----


@pytest.mark.asyncio
async def test_send_email(mock_context):
    mock_context.fetch = AsyncMock(return_value=FetchResponse(status=200, headers={}, data=None))
    result = await microsoft365.execute_action(
        "send_email",
        {"subject": "Hi", "body": "Hello", "to": "user@example.com"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["sent"] is True


@pytest.mark.asyncio
async def test_send_email_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("network error"))
    result = await microsoft365.execute_action(
        "send_email",
        {"subject": "Hi", "body": "Hello", "to": "user@example.com"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "network error" in result.result.message


@pytest.mark.asyncio
async def test_send_email_graph_error_body_is_not_reported_as_success(mock_context):
    mock_context.fetch = AsyncMock(
        return_value=FetchResponse(
            status=403,
            headers={},
            data={"error": {"code": "ErrorAccessDenied", "message": "Access denied"}},
        )
    )
    result = await microsoft365.execute_action(
        "send_email",
        {"subject": "Hi", "body": "Hello", "to": "user@example.com"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "Access denied" in result.result.message


# ---- create_calendar_event ----


@pytest.mark.asyncio
async def test_create_calendar_event(mock_context):
    mock_context.fetch = make_fetch({"id": "evt1", "webLink": "https://outlook.com/evt1"})
    result = await microsoft365.execute_action(
        "create_calendar_event",
        {"subject": "Meeting", "start_time": "2026-06-15T10:00:00", "end_time": "2026-06-15T11:00:00"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["id"] == "evt1"


@pytest.mark.asyncio
async def test_create_calendar_event_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("api error"))
    result = await microsoft365.execute_action(
        "create_calendar_event",
        {"subject": "Meeting", "start_time": "2026-06-15T10:00:00", "end_time": "2026-06-15T11:00:00"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- upload_file ----


def make_file_input(content=b"hello", name="test.txt", content_type="text/plain"):
    return {
        "file": {
            "content": base64.b64encode(content).decode("ascii"),
            "name": name,
            "contentType": content_type,
        }
    }


@pytest.mark.asyncio
async def test_upload_file(mock_context):
    mock_context.fetch = make_fetch({"id": "file1", "webUrl": "https://onedrive.com/f1", "size": 100})
    result = await microsoft365.execute_action("upload_file", make_file_input(), mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["id"] == "file1"

    _, kwargs = mock_context.fetch.call_args
    assert kwargs["data"] == b"hello", "file must be uploaded as raw bytes, not base64"
    assert kwargs["headers"]["Content-Type"] == "text/plain"


@pytest.mark.asyncio
async def test_upload_file_uses_folder_path_and_encodes_name(mock_context):
    mock_context.fetch = make_fetch({"id": "file1", "webUrl": "https://onedrive.com/f1", "size": 100})
    inputs = make_file_input(name="my report.txt") | {"folder_path": "/Reports/2026"}
    result = await microsoft365.execute_action("upload_file", inputs, mock_context)
    assert result.type != ResultType.ACTION_ERROR

    args, _ = mock_context.fetch.call_args
    assert args[0].endswith("/me/drive/root:/Reports/2026/my%20report.txt:/content")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,content_type,payload",
    [
        ("report.pdf", "application/pdf", b"%PDF-1.7\r\n\x00\x01\x02\xff\xfe binary \x80 tail"),
        (
            "report.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x00\xde\xad\xbe\xef",
        ),
    ],
)
async def test_upload_file_preserves_binary_bytes(mock_context, name, content_type, payload):
    """Bytes must survive the round trip untouched — the old UTF-8 encode corrupted them."""
    mock_context.fetch = make_fetch({"id": "file1", "webUrl": "https://onedrive.com/f1", "size": len(payload)})
    result = await microsoft365.execute_action(
        "upload_file",
        make_file_input(content=payload, name=name, content_type=content_type),
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message

    _, kwargs = mock_context.fetch.call_args
    assert kwargs["data"] == payload
    assert kwargs["headers"]["Content-Type"] == content_type


@pytest.mark.asyncio
async def test_upload_file_overrides_name_and_content_type(mock_context):
    mock_context.fetch = make_fetch({"id": "file1", "webUrl": "https://onedrive.com/f1", "size": 100})
    inputs = make_file_input() | {"filename": "renamed.md", "content_type": "text/markdown"}
    result = await microsoft365.execute_action("upload_file", inputs, mock_context)
    assert result.type != ResultType.ACTION_ERROR

    args, kwargs = mock_context.fetch.call_args
    assert args[0].endswith("/renamed.md:/content")
    assert kwargs["headers"]["Content-Type"] == "text/markdown"


@pytest.mark.asyncio
async def test_upload_file_text_content_still_supported(mock_context):
    """The original text-content workflow must keep working (issue #450)."""
    mock_context.fetch = make_fetch({"id": "file1", "webUrl": "https://onedrive.com/f1", "size": 5})
    result = await microsoft365.execute_action(
        "upload_file",
        {"filename": "notes.md", "content": "# hello", "content_type": "text/markdown"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message

    _, kwargs = mock_context.fetch.call_args
    assert kwargs["data"] == b"# hello"
    assert kwargs["headers"]["Content-Type"] == "text/markdown"


@pytest.mark.asyncio
async def test_upload_file_text_content_defaults_to_plain_text(mock_context):
    mock_context.fetch = make_fetch({"id": "file1", "webUrl": "https://onedrive.com/f1", "size": 5})
    result = await microsoft365.execute_action(
        "upload_file",
        {"filename": "notes.txt", "content": "hello"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    _, kwargs = mock_context.fetch.call_args
    assert kwargs["headers"]["Content-Type"] == "text/plain"


@pytest.mark.asyncio
async def test_upload_file_rejects_payload_above_graph_simple_upload_limit(mock_context):
    with patch("microsoft365.microsoft365.MAX_SIMPLE_UPLOAD_BYTES", 4):
        result = await microsoft365.execute_action(
            "upload_file",
            make_file_input(content=b"12345"),
            mock_context,
        )
    assert result.type == ResultType.ACTION_ERROR
    assert "250 MB" in result.result.message
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_upload_file_missing_content(mock_context):
    """The wrapper hydrates URL-delivered files into 'content' before the action runs,
    so 'content' is required and a file object without it fails schema validation."""
    mock_context.fetch = make_fetch({"id": "file1"})
    result = await microsoft365.execute_action(
        "upload_file",
        {"file": {"name": "test.txt", "contentType": "text/plain"}},
        mock_context,
    )
    assert result.type == ResultType.VALIDATION_ERROR
    assert "content" in result.result["message"]
    mock_context.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_upload_file_rejects_empty_content(mock_context):
    mock_context.fetch = make_fetch({"id": "file1"})
    result = await microsoft365.execute_action(
        "upload_file",
        {"file": {"content": "", "name": "test.txt", "contentType": "text/plain"}},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "empty" in result.result.message


@pytest.mark.asyncio
async def test_upload_file_rejects_invalid_base64(mock_context):
    mock_context.fetch = make_fetch({"id": "file1"})
    result = await microsoft365.execute_action(
        "upload_file",
        {"file": {"content": "not!valid!base64!", "name": "test.txt", "contentType": "text/plain"}},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "base64" in result.result.message


@pytest.mark.asyncio
async def test_upload_file_requires_file_or_content(mock_context):
    mock_context.fetch = make_fetch({"id": "file1"})
    result = await microsoft365.execute_action("upload_file", {"folder_path": "/Reports"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "content" in result.result.message


@pytest.mark.asyncio
async def test_upload_file_text_content_requires_filename(mock_context):
    mock_context.fetch = make_fetch({"id": "file1"})
    result = await microsoft365.execute_action("upload_file", {"content": "hello"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "filename" in result.result.message


@pytest.mark.asyncio
async def test_upload_file_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("upload failed"))
    result = await microsoft365.execute_action("upload_file", make_file_input(), mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- list_files ----


@pytest.mark.asyncio
async def test_list_files(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "f1",
                    "name": "doc.txt",
                    "size": 50,
                    "lastModifiedDateTime": "2026-01-01",
                    "webUrl": "https://od.com/f1",
                }
            ]
        }
    )
    result = await microsoft365.execute_action("list_files", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["files"]) == 1


@pytest.mark.asyncio
async def test_list_files_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("list_files", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_list_files_follows_graph_pagination(mock_context):
    item1 = {"id": "f1", "name": "one.txt", "lastModifiedDateTime": "", "webUrl": "one"}
    item2 = {"id": "f2", "name": "two.txt", "lastModifiedDateTime": "", "webUrl": "two"}
    mock_context.fetch = AsyncMock(
        side_effect=[
            FetchResponse(
                status=200,
                headers={},
                data={
                    "value": [item1],
                    "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/drive/root/children?$skiptoken=next",
                },
            ),
            FetchResponse(status=200, headers={}, data={"value": [item2]}),
        ]
    )
    result = await microsoft365.execute_action("list_files", {"limit": 2}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert [item["id"] for item in result.result.data["files"]] == ["f1", "f2"]
    assert mock_context.fetch.await_count == 2
    assert (
        mock_context.fetch.await_args_list[1].args[0]
        == "https://graph.microsoft.com/v1.0/me/drive/root/children?$skiptoken=next"
    )


@pytest.mark.asyncio
async def test_list_files_rejects_next_link_outside_microsoft_graph(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [],
            "@odata.nextLink": "https://attacker.example/collect-oauth-token",
        }
    )

    result = await microsoft365.execute_action("list_files", {}, mock_context)

    assert result.type == ResultType.ACTION_ERROR
    assert "unsafe or unexpected" in result.result.message
    assert mock_context.fetch.await_count == 1


@pytest.mark.asyncio
async def test_list_files_rejects_repeated_next_link(mock_context):
    repeated_url = "https://graph.microsoft.com/v1.0/me/drive/root/children?$skiptoken=same"
    mock_context.fetch = AsyncMock(
        side_effect=[
            FetchResponse(status=200, headers={}, data={"value": [], "@odata.nextLink": repeated_url}),
            FetchResponse(status=200, headers={}, data={"value": [], "@odata.nextLink": repeated_url}),
        ]
    )

    result = await microsoft365.execute_action("list_files", {}, mock_context)

    assert result.type == ResultType.ACTION_ERROR
    assert "repeated" in result.result.message
    assert mock_context.fetch.await_count == 2


@pytest.mark.asyncio
async def test_list_files_rejects_non_object_collection_items(mock_context):
    mock_context.fetch = make_fetch({"value": [{"id": "valid"}, "not-an-object"]})

    result = await microsoft365.execute_action("list_files", {}, mock_context)

    assert result.type == ResultType.ACTION_ERROR
    assert "items must be objects" in result.result.message


# ---- update_calendar_event ----


@pytest.mark.asyncio
async def test_update_calendar_event(mock_context):
    mock_context.fetch = make_fetch({"id": "evt1", "webLink": "https://outlook.com/evt1"})
    result = await microsoft365.execute_action(
        "update_calendar_event",
        {"event_id": "evt1", "subject": "Updated"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["id"] == "evt1"


@pytest.mark.asyncio
async def test_update_calendar_event_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("not found"))
    result = await microsoft365.execute_action(
        "update_calendar_event",
        {"event_id": "evt1"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_update_calendar_event_can_clear_optional_fields_and_encodes_id(mock_context):
    mock_context.fetch = make_fetch({"id": "evt/1"})
    result = await microsoft365.execute_action(
        "update_calendar_event",
        {"event_id": "evt/1", "location": "", "attendees": []},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    args, kwargs = mock_context.fetch.await_args
    assert args[0].endswith("/events/evt%2F1")
    assert kwargs["json"]["location"] == {"displayName": ""}
    assert kwargs["json"]["attendees"] == []


# ---- list_calendar_events ----


@pytest.mark.asyncio
async def test_list_calendar_events(mock_context):
    event = {
        "id": "e1",
        "subject": "Standup",
        "start": {"dateTime": "2026-06-15T09:00:00", "timeZone": "UTC"},
        "end": {"dateTime": "2026-06-15T09:30:00", "timeZone": "UTC"},
        "location": {"displayName": "Room A"},
        "bodyPreview": "",
        "organizer": {"emailAddress": {"address": "boss@co.com"}},
        "attendees": [],
        "webLink": "https://outlook.com/e1",
        "isAllDay": False,
    }
    mock_context.fetch = make_fetch({"value": [event]})
    result = await microsoft365.execute_action("list_calendar_events", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["events"]) == 1


@pytest.mark.asyncio
async def test_list_calendar_events_accepts_nullable_graph_fields(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "e1",
                    "subject": None,
                    "start": None,
                    "end": None,
                    "location": None,
                    "organizer": {"emailAddress": None},
                    "attendees": [None, {"emailAddress": None, "status": None}],
                }
            ]
        }
    )

    result = await microsoft365.execute_action("list_calendar_events", {}, mock_context)

    assert result.type != ResultType.ACTION_ERROR
    event = result.result.data["events"][0]
    assert event["start"] == {}
    assert event["end"] == {}
    assert event["location"] == ""
    assert event["organizer"] == ""
    assert event["attendees"][0] == {"email": "", "name": "", "response_status": "none"}


@pytest.mark.asyncio
async def test_list_calendar_events_sends_range_as_query_params(mock_context):
    mock_context.fetch = make_fetch({"value": []})
    result = await microsoft365.execute_action(
        "list_calendar_events",
        {
            "start_datetime": "2026-06-15T09:00:00+12:00",
            "end_datetime": "2026-06-15T10:00:00+12:00",
        },
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    args, kwargs = mock_context.fetch.await_args
    assert args[0].endswith("/me/calendarView")
    assert kwargs["params"]["startDateTime"] == "2026-06-14T21:00:00Z"
    assert kwargs["params"]["endDateTime"] == "2026-06-14T22:00:00Z"


@pytest.mark.asyncio
async def test_list_calendar_events_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("list_calendar_events", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_list_calendar_events_rejects_end_without_start(mock_context):
    result = await microsoft365.execute_action(
        "list_calendar_events",
        {"end_datetime": "2026-06-15T10:00:00Z"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "start_datetime is required" in result.result.message
    mock_context.fetch.assert_not_called()


# ---- list_emails ----


@pytest.mark.asyncio
async def test_list_emails(mock_context):
    email = {
        "id": "em1",
        "subject": "Hello",
        "sender": {"emailAddress": {"address": "a@b.com"}},
        "receivedDateTime": "2026-06-10T10:00:00Z",
        "bodyPreview": "Hi there",
        "body": {"contentType": "Text", "content": "Hi there"},
        "hasAttachments": False,
        "isRead": False,
        "importance": "normal",
    }
    mock_context.fetch = make_fetch({"value": [email]})
    result = await microsoft365.execute_action("list_emails", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["emails"]) == 1


@pytest.mark.asyncio
async def test_list_emails_with_fields(mock_context):
    email = {
        "id": "em1",
        "subject": "Hello",
        "sender": {"emailAddress": {"address": "a@b.com"}},
        "receivedDateTime": "2026-06-10T10:00:00Z",
        "bodyPreview": "Hi there",
        "hasAttachments": False,
    }
    mock_context.fetch = make_fetch({"value": [email]})
    result = await microsoft365.execute_action(
        "list_emails",
        {"fields": ["id", "subject", "sender", "receivedDateTime", "hasAttachments", "bodyPreview"]},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    emails = result.result.data["emails"]
    assert len(emails) == 1
    # body should not be present when not in fields
    assert "body" not in emails[0]


@pytest.mark.asyncio
async def test_list_emails_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("list_emails", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


@pytest.mark.asyncio
async def test_list_emails_rejects_end_without_start(mock_context):
    result = await microsoft365.execute_action(
        "list_emails",
        {"end_datetime": "2026-06-15T10:00:00Z"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "start_datetime is required" in result.result.message
    mock_context.fetch.assert_not_called()


# ---- list_emails_from_contact ----


@pytest.mark.asyncio
async def test_list_emails_from_contact(mock_context):
    email = {
        "id": "em2",
        "subject": "Re: test",
        "sender": {"emailAddress": {"address": "friend@b.com"}},
        "receivedDateTime": "2026-06-10T10:00:00Z",
        "bodyPreview": "ok",
        "body": {},
        "hasAttachments": False,
        "isRead": True,
        "importance": "normal",
    }
    mock_context.fetch = make_fetch({"value": [email]})
    result = await microsoft365.execute_action(
        "list_emails_from_contact",
        {"contact_email": "friend@b.com"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["contact_email"] == "friend@b.com"
    _, kwargs = mock_context.fetch.await_args
    assert kwargs["params"]["$search"] == '"from:friend@b.com"'
    assert "$orderby" not in kwargs["params"]
    assert "$filter" not in kwargs["params"]


@pytest.mark.asyncio
async def test_list_emails_from_contact_with_fields(mock_context):
    email = {
        "id": "em2",
        "subject": "Re: test",
        "sender": {"emailAddress": {"address": "friend@b.com"}},
        "receivedDateTime": "2026-06-10T10:00:00Z",
        "bodyPreview": "ok",
        "hasAttachments": False,
    }
    mock_context.fetch = make_fetch({"value": [email]})
    result = await microsoft365.execute_action(
        "list_emails_from_contact",
        {
            "contact_email": "friend@b.com",
            "fields": ["id", "subject", "sender", "receivedDateTime", "hasAttachments", "bodyPreview"],
        },
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert "body" not in result.result.data["emails"][0]


@pytest.mark.asyncio
async def test_list_emails_from_contact_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "list_emails_from_contact",
        {"contact_email": "x@y.com"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- mark_email_read ----


@pytest.mark.asyncio
async def test_mark_email_read(mock_context):
    mock_context.fetch = make_fetch({"id": "em1", "isRead": True, "lastModifiedDateTime": "2026-06-10T10:00:00Z"})
    result = await microsoft365.execute_action(
        "mark_email_read",
        {"email_id": "em1", "is_read": True},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["isRead"] is True


@pytest.mark.asyncio
async def test_mark_email_read_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "mark_email_read",
        {"email_id": "em1", "is_read": True},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- list_mail_folders ----


@pytest.mark.asyncio
async def test_list_mail_folders(mock_context):
    folder = {
        "id": "fld1",
        "displayName": "Inbox",
        "parentFolderId": "",
        "childFolderCount": 0,
        "unreadItemCount": 3,
        "totalItemCount": 10,
        "isHidden": False,
    }
    mock_context.fetch = make_fetch({"value": [folder]})
    result = await microsoft365.execute_action("list_mail_folders", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["total_count"] == 1


@pytest.mark.asyncio
async def test_list_mail_folders_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("list_mail_folders", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- get_mail_folder ----


@pytest.mark.asyncio
async def test_get_mail_folder(mock_context):
    mock_context.fetch = make_fetch(
        {
            "id": "inbox",
            "displayName": "Inbox",
            "parentFolderId": "",
            "childFolderCount": 0,
            "unreadItemCount": 5,
            "totalItemCount": 20,
            "isHidden": False,
        }
    )
    result = await microsoft365.execute_action("get_mail_folder", {"folder_id": "inbox"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["folder"]["displayName"] == "Inbox"


@pytest.mark.asyncio
async def test_get_mail_folder_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("get_mail_folder", {"folder_id": "inbox"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- move_email ----


@pytest.mark.asyncio
async def test_move_email(mock_context):
    mock_context.fetch = make_fetch({"id": "em1", "parentFolderId": "archive", "subject": "Hello"})
    result = await microsoft365.execute_action(
        "move_email",
        {"email_id": "em1", "destination_folder_id": "archive"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["parentFolderId"] == "archive"


@pytest.mark.asyncio
async def test_move_email_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "move_email",
        {"email_id": "em1", "destination_folder_id": "archive"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- read_email ----


@pytest.mark.asyncio
async def test_read_email(mock_context):
    mock_context.fetch = make_fetch(
        {
            "id": "em1",
            "subject": "Hello",
            "sender": {"emailAddress": {"address": "a@b.com"}},
            "receivedDateTime": "2026-06-10T10:00:00Z",
            "body": {"contentType": "Text", "content": "body"},
            "hasAttachments": False,
        }
    )
    result = await microsoft365.execute_action("read_email", {"email_id": "em1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["email"]["id"] == "em1"


@pytest.mark.asyncio
async def test_read_email_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("read_email", {"email_id": "em1"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- read_contacts ----


@pytest.mark.asyncio
async def test_read_contacts(mock_context):
    contact = {
        "id": "c1",
        "displayName": "John Doe",
        "givenName": "John",
        "surname": "Doe",
        "emailAddresses": [{"address": "john@doe.com", "name": "John Doe"}],
        "businessPhones": [],
        "homePhones": [],
        "mobilePhone": "",
        "companyName": "Acme",
        "jobTitle": "Engineer",
    }
    mock_context.fetch = make_fetch({"value": [contact]})
    result = await microsoft365.execute_action("read_contacts", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["total_contacts"] == 1


@pytest.mark.asyncio
async def test_read_contacts_accepts_nullable_collections(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "c1",
                    "displayName": "No details",
                    "emailAddresses": None,
                    "businessPhones": None,
                    "homePhones": None,
                }
            ]
        }
    )

    result = await microsoft365.execute_action("read_contacts", {}, mock_context)

    assert result.type != ResultType.ACTION_ERROR
    contact = result.result.data["contacts"][0]
    assert contact["emailAddresses"] == []
    assert contact["businessPhones"] == []
    assert contact["homePhones"] == []


@pytest.mark.asyncio
async def test_read_contacts_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("read_contacts", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- search_onedrive_files ----


@pytest.mark.asyncio
async def test_search_onedrive_files(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "f1",
                    "name": "report.pdf",
                    "size": 100,
                    "lastModifiedDateTime": "2026-01-01",
                    "webUrl": "https://od.com/f1",
                }
            ]
        }
    )
    result = await microsoft365.execute_action("search_onedrive_files", {"query": "report"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["query"] == "report"


@pytest.mark.asyncio
async def test_search_onedrive_files_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("search_onedrive_files", {"query": "report"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- read_onedrive_file_content ----


@pytest.mark.asyncio
async def test_read_onedrive_file_content_text(mock_context):
    metadata = {
        "id": "f1",
        "name": "readme.txt",
        "size": 50,
        "file": {"mimeType": "text/plain"},
        "webUrl": "https://od.com/f1",
    }
    mock_context.fetch = make_fetch(metadata)
    with patch("microsoft365.microsoft365._fetch_binary", new=AsyncMock(return_value=b"hello world")):
        result = await microsoft365.execute_action("read_onedrive_file_content", {"file_id": "f1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["file"]["name"] == "readme.txt"


@pytest.mark.asyncio
async def test_read_onedrive_file_content_content_error(mock_context):
    metadata = {
        "id": "f1",
        "name": "readme.txt",
        "size": 50,
        "file": {"mimeType": "text/plain"},
        "webUrl": "https://od.com/f1",
    }
    mock_context.fetch = make_fetch(metadata)
    with patch("microsoft365.microsoft365._fetch_binary", new=AsyncMock(side_effect=Exception("binary fetch failed"))):
        result = await microsoft365.execute_action("read_onedrive_file_content", {"file_id": "f1"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR
    assert "binary fetch failed" in result.result.message


@pytest.mark.asyncio
async def test_read_onedrive_office_file_uses_documented_pdf_conversion(mock_context):
    metadata = {
        "id": "f1",
        "name": "quarterly report.docx",
        "size": 500,
        "file": {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        "webUrl": "https://od.com/f1",
    }
    mock_context.fetch = make_fetch(metadata)
    binary_fetch = AsyncMock(return_value=b"%PDF-1.7")
    with patch("microsoft365.microsoft365._fetch_binary", new=binary_fetch):
        result = await microsoft365.execute_action("read_onedrive_file_content", {"file_id": "f1"}, mock_context)

    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["file"]["name"] == "quarterly report.pdf"
    assert result.result.data["file"]["contentType"] == "application/pdf"
    assert result.result.data["metadata"]["convertedToPdf"] is True
    assert binary_fetch.await_args.args[0].endswith("/content?format=pdf")


@pytest.mark.asyncio
@pytest.mark.parametrize("extension", ["markdown", "dwg", "loop", "whiteboard"])
async def test_read_onedrive_uses_current_graph_pdf_conversion_extensions(mock_context, extension):
    metadata = {
        "id": "f1",
        "name": f"convertible.{extension}",
        "size": 20,
        "file": {"mimeType": "application/octet-stream"},
        "webUrl": "https://od.com/f1",
    }
    mock_context.fetch = make_fetch(metadata)
    binary_fetch = AsyncMock(return_value=b"%PDF-1.7")

    with patch("microsoft365.microsoft365._fetch_binary", new=binary_fetch):
        result = await microsoft365.execute_action("read_onedrive_file_content", {"file_id": "f1"}, mock_context)

    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["file"]["name"] == "convertible.pdf"
    assert binary_fetch.await_args.args[0].endswith("/content?format=pdf")


@pytest.mark.asyncio
async def test_read_onedrive_file_content_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("read_onedrive_file_content", {"file_id": "f1"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- create_draft_email ----


@pytest.mark.asyncio
async def test_create_draft_email(mock_context):
    mock_context.fetch = make_fetch(
        {
            "id": "draft1",
            "subject": "Draft",
            "createdDateTime": "2026-06-10T10:00:00Z",
            "isDraft": True,
        }
    )
    result = await microsoft365.execute_action(
        "create_draft_email",
        {"subject": "Draft", "body": "Body text", "to_recipients": ["a@b.com"]},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["draft_id"] == "draft1"


@pytest.mark.asyncio
async def test_create_draft_email_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "create_draft_email",
        {"subject": "Draft", "body": "Body text", "to_recipients": ["a@b.com"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- send_draft_email ----


@pytest.mark.asyncio
async def test_send_draft_email(mock_context):
    mock_context.fetch = AsyncMock(return_value=FetchResponse(status=200, headers={}, data=None))
    result = await microsoft365.execute_action("send_draft_email", {"draft_id": "draft1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["sent"] is True


@pytest.mark.asyncio
async def test_send_draft_email_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("send_draft_email", {"draft_id": "draft1"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- reply_to_email ----


@pytest.mark.asyncio
async def test_reply_to_email(mock_context):
    mock_context.fetch = AsyncMock(return_value=FetchResponse(status=200, headers={}, data=None))
    result = await microsoft365.execute_action(
        "reply_to_email",
        {"message_id": "em1", "comment": "Got it!"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["sent"] is True


@pytest.mark.asyncio
async def test_reply_to_email_sends_required_comment_property_when_empty(mock_context):
    mock_context.fetch = AsyncMock(return_value=FetchResponse(status=202, headers={}, data=None))
    result = await microsoft365.execute_action("reply_to_email", {"message_id": "em1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    _, kwargs = mock_context.fetch.await_args
    assert kwargs["json"] == {"comment": ""}


@pytest.mark.asyncio
async def test_reply_to_email_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "reply_to_email",
        {"message_id": "em1"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- forward_email ----


@pytest.mark.asyncio
async def test_forward_email(mock_context):
    mock_context.fetch = AsyncMock(return_value=FetchResponse(status=200, headers={}, data=None))
    result = await microsoft365.execute_action(
        "forward_email",
        {"message_id": "em1", "to_recipients": ["c@d.com"]},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["sent"] is True


@pytest.mark.asyncio
async def test_forward_email_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "forward_email",
        {"message_id": "em1", "to_recipients": ["c@d.com"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- download_email_attachment ----


@pytest.mark.asyncio
async def test_download_email_attachment(mock_context):
    meta = {"id": "att1", "name": "file.pdf", "contentType": "application/pdf", "size": 200, "isInline": False}
    mock_context.fetch = make_fetch(meta)
    with patch("microsoft365.microsoft365._fetch_binary", new=AsyncMock(return_value=b"%PDF-1.4 stub")):
        result = await microsoft365.execute_action(
            "download_email_attachment",
            {"message_id": "em1", "attachment_id": "att1"},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["metadata"]["name"] == "file.pdf"


@pytest.mark.asyncio
async def test_download_email_attachment_content_error(mock_context):
    meta = {"id": "att1", "name": "file.pdf", "contentType": "application/pdf", "size": 200, "isInline": False}
    mock_context.fetch = make_fetch(meta)
    with patch("microsoft365.microsoft365._fetch_binary", new=AsyncMock(side_effect=Exception("binary fetch failed"))):
        result = await microsoft365.execute_action(
            "download_email_attachment",
            {"message_id": "em1", "attachment_id": "att1"},
            mock_context,
        )
    assert result.type == ResultType.ACTION_ERROR
    assert "binary fetch failed" in result.result.message


@pytest.mark.asyncio
async def test_download_email_attachment_metadata_only_does_not_return_empty_file(mock_context):
    meta = {"id": "att1", "name": "file.pdf", "contentType": "application/pdf", "size": 200, "isInline": False}
    mock_context.fetch = make_fetch(meta)
    with patch("microsoft365.microsoft365._fetch_binary", new=AsyncMock()) as binary_fetch:
        result = await microsoft365.execute_action(
            "download_email_attachment",
            {"message_id": "em1", "attachment_id": "att1", "include_content": False},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert "file" not in result.result.data
    assert result.result.data["metadata"]["size"] == 200
    binary_fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_email_attachment_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "download_email_attachment",
        {"message_id": "em1", "attachment_id": "att1"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- search_emails ----


@pytest.mark.asyncio
async def test_search_emails(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "hitsContainers": [
                        {
                            "total": 1,
                            "hits": [
                                {
                                    "resource": {
                                        "id": "em1",
                                        "subject": "test",
                                        "receivedDateTime": "2026-06-10T10:00:00Z",
                                        "bodyPreview": "hi",
                                    }
                                }
                            ],
                        }
                    ]
                }
            ]
        }
    )
    result = await microsoft365.execute_action("search_emails", {"query": "test"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["total_results"] == 1


@pytest.mark.asyncio
async def test_search_emails_accepts_nullable_graph_collections(mock_context):
    mock_context.fetch = make_fetch({"value": [{"hitsContainers": None}]})

    result = await microsoft365.execute_action("search_emails", {"query": "test"}, mock_context)

    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["messages"] == []
    assert result.result.data["total_results"] == 0


@pytest.mark.asyncio
async def test_search_emails_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("search_emails", {"query": "test"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- search_sharepoint_sites ----


@pytest.mark.asyncio
async def test_search_sharepoint_sites(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "s1",
                    "name": "MySite",
                    "displayName": "My Site",
                    "description": "",
                    "webUrl": "https://sp.com/s1",
                    "createdDateTime": "",
                    "lastModifiedDateTime": "",
                }
            ]
        }
    )
    result = await microsoft365.execute_action("search_sharepoint_sites", {"query": "My"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["total_sites"] == 1


@pytest.mark.asyncio
async def test_search_sharepoint_sites_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("search_sharepoint_sites", {"query": "My"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- get_sharepoint_site_details ----


@pytest.mark.asyncio
async def test_get_sharepoint_site_details(mock_context):
    mock_context.fetch = make_fetch(
        {
            "id": "s1",
            "displayName": "My Site",
            "name": "mysite",
            "description": "",
            "webUrl": "https://sp.com/s1",
            "createdDateTime": "",
            "lastModifiedDateTime": "",
            "isPersonalSite": False,
        }
    )
    result = await microsoft365.execute_action("get_sharepoint_site_details", {"site_id": "s1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["site"]["id"] == "s1"


@pytest.mark.asyncio
async def test_get_sharepoint_site_details_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("get_sharepoint_site_details", {"site_id": "s1"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- list_sharepoint_libraries ----


@pytest.mark.asyncio
async def test_list_sharepoint_libraries(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "d1",
                    "name": "Documents",
                    "description": "",
                    "driveType": "documentLibrary",
                    "webUrl": "https://sp.com/d1",
                    "createdDateTime": "",
                    "lastModifiedDateTime": "",
                }
            ]
        }
    )
    result = await microsoft365.execute_action("list_sharepoint_libraries", {"site_id": "s1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["total_libraries"] == 1


@pytest.mark.asyncio
async def test_list_sharepoint_libraries_accepts_nullable_owner_and_quota(mock_context):
    mock_context.fetch = make_fetch({"value": [{"id": "d1", "name": "Documents", "owner": None, "quota": None}]})

    result = await microsoft365.execute_action("list_sharepoint_libraries", {"site_id": "s1"}, mock_context)

    assert result.type != ResultType.ACTION_ERROR
    library = result.result.data["libraries"][0]
    assert "owner" not in library
    assert "quota" not in library


@pytest.mark.asyncio
async def test_list_sharepoint_libraries_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("list_sharepoint_libraries", {"site_id": "s1"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- search_sharepoint_documents ----


@pytest.mark.asyncio
async def test_search_sharepoint_documents(mock_context):
    drives = {"value": [{"id": "d1", "name": "Docs"}]}
    files = {
        "value": [
            {
                "id": "f1",
                "name": "report.pdf",
                "size": 100,
                "lastModifiedDateTime": "2026-01-01",
                "webUrl": "https://sp.com/f1",
            }
        ]
    }
    mock_context.fetch = AsyncMock(
        side_effect=[
            FetchResponse(status=200, headers={}, data=drives),
            FetchResponse(status=200, headers={}, data=files),
        ]
    )
    result = await microsoft365.execute_action(
        "search_sharepoint_documents",
        {"site_id": "s1", "query": "report"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["total_files"] == 1


@pytest.mark.asyncio
async def test_search_sharepoint_documents_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "search_sharepoint_documents",
        {"site_id": "s1", "query": "report"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- read_sharepoint_document ----


@pytest.mark.asyncio
async def test_read_sharepoint_document(mock_context):
    metadata = {
        "id": "f1",
        "name": "readme.txt",
        "size": 50,
        "file": {"mimeType": "text/plain"},
        "webUrl": "https://sp.com/f1",
    }
    mock_context.fetch = make_fetch(metadata)
    with patch("microsoft365.microsoft365._fetch_binary", new=AsyncMock(return_value=b"hello world")):
        result = await microsoft365.execute_action(
            "read_sharepoint_document",
            {"site_id": "s1", "file_id": "f1"},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["file"]["name"] == "readme.txt"


@pytest.mark.asyncio
async def test_read_sharepoint_document_content_error(mock_context):
    metadata = {
        "id": "f1",
        "name": "doc.txt",
        "size": 50,
        "file": {"mimeType": "text/plain"},
        "webUrl": "https://sp.com/f1",
    }
    mock_context.fetch = make_fetch(metadata)
    with patch("microsoft365.microsoft365._fetch_binary", new=AsyncMock(side_effect=Exception("binary fetch failed"))):
        result = await microsoft365.execute_action(
            "read_sharepoint_document",
            {"site_id": "s1", "file_id": "f1"},
            mock_context,
        )
    assert result.type == ResultType.ACTION_ERROR
    assert "binary fetch failed" in result.result.message


@pytest.mark.asyncio
async def test_read_sharepoint_document_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "read_sharepoint_document",
        {"site_id": "s1", "file_id": "f1"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- list_sharepoint_pages ----


@pytest.mark.asyncio
async def test_list_sharepoint_pages(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "p1",
                    "name": "home.aspx",
                    "title": "Home",
                    "webUrl": "https://sp.com/home",
                    "pageLayout": "home",
                    "createdDateTime": "",
                    "lastModifiedDateTime": "",
                }
            ]
        }
    )
    result = await microsoft365.execute_action("list_sharepoint_pages", {"site_id": "s1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["total_pages"] == 1


@pytest.mark.asyncio
async def test_list_sharepoint_pages_accepts_nullable_identities(mock_context):
    mock_context.fetch = make_fetch(
        {"value": [{"id": "p1", "name": "home.aspx", "createdBy": None, "lastModifiedBy": None}]}
    )

    result = await microsoft365.execute_action("list_sharepoint_pages", {"site_id": "s1"}, mock_context)

    assert result.type != ResultType.ACTION_ERROR
    page = result.result.data["pages"][0]
    assert "created_by" not in page
    assert "last_modified_by" not in page


@pytest.mark.asyncio
async def test_list_sharepoint_pages_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("list_sharepoint_pages", {"site_id": "s1"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- read_sharepoint_page_content ----


@pytest.mark.asyncio
async def test_read_sharepoint_page_content(mock_context):
    mock_context.fetch = make_fetch(
        {
            "id": "p1",
            "name": "home.aspx",
            "title": "Home",
            "webUrl": "https://sp.com/home",
            "pageLayout": "home",
            "createdDateTime": "",
            "lastModifiedDateTime": "",
        }
    )
    result = await microsoft365.execute_action(
        "read_sharepoint_page_content",
        {"site_id": "s1", "page_id": "p1"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["page"]["id"] == "p1"


@pytest.mark.asyncio
async def test_read_sharepoint_page_content_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "read_sharepoint_page_content",
        {"site_id": "s1", "page_id": "p1"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- list_sharepoint_subsites ----


@pytest.mark.asyncio
async def test_list_sharepoint_subsites(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "sub1",
                    "name": "sub",
                    "displayName": "Sub Site",
                    "description": "",
                    "webUrl": "https://sp.com/sub",
                    "createdDateTime": "",
                    "lastModifiedDateTime": "",
                    "isPersonalSite": False,
                }
            ]
        }
    )
    result = await microsoft365.execute_action("list_sharepoint_subsites", {"site_id": "s1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["total_subsites"] == 1


@pytest.mark.asyncio
async def test_list_sharepoint_subsites_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("list_sharepoint_subsites", {"site_id": "s1"}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- list_sharepoint_folder_contents ----


@pytest.mark.asyncio
async def test_list_sharepoint_folder_contents(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "i1",
                    "name": "folder1",
                    "webUrl": "https://sp.com/f1",
                    "size": 0,
                    "createdDateTime": "",
                    "lastModifiedDateTime": "",
                    "folder": {"childCount": 2},
                }
            ]
        }
    )
    result = await microsoft365.execute_action(
        "list_sharepoint_folder_contents",
        {"drive_id": "d1"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["total_items"] == 1


@pytest.mark.asyncio
async def test_list_sharepoint_folder_contents_accepts_nullable_facets(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "i1",
                    "name": "unknown",
                    "folder": None,
                    "file": None,
                    "createdBy": None,
                    "lastModifiedBy": None,
                }
            ]
        }
    )

    result = await microsoft365.execute_action(
        "list_sharepoint_folder_contents",
        {"drive_id": "d1"},
        mock_context,
    )

    assert result.type != ResultType.ACTION_ERROR
    item = result.result.data["items"][0]
    assert item["is_folder"] is False
    assert "child_count" not in item
    assert "mime_type" not in item


@pytest.mark.asyncio
async def test_list_sharepoint_folder_contents_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "list_sharepoint_folder_contents",
        {"drive_id": "d1"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- find_meeting_times ----


@pytest.mark.asyncio
async def test_find_meeting_times(mock_context):
    mock_context.fetch = make_fetch(
        {
            "meetingTimeSuggestions": [
                {
                    "meetingTimeSlot": {
                        "start": {"dateTime": "2026-06-15T10:00:00", "timeZone": "UTC"},
                        "end": {"dateTime": "2026-06-15T11:00:00", "timeZone": "UTC"},
                    },
                    "confidence": 100.0,
                    "organizerAvailability": "free",
                    "attendeeAvailability": [],
                    "locations": [],
                }
            ]
        }
    )
    result = await microsoft365.execute_action(
        "find_meeting_times",
        {"attendees": ["a@b.com"]},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["meeting_time_suggestions"]) == 1
    _, kwargs = mock_context.fetch.await_args
    constraint = kwargs["json"]["timeConstraint"]
    assert "timeSlots" in constraint
    assert "timeslots" not in constraint
    assert constraint["activityDomain"] == "work"
    assert kwargs["json"]["returnSuggestionReasons"] is True


@pytest.mark.asyncio
async def test_find_meeting_times_accepts_nullable_suggestion_details(mock_context):
    mock_context.fetch = make_fetch(
        {
            "meetingTimeSuggestions": [
                {
                    "meetingTimeSlot": None,
                    "attendeeAvailability": [{"attendee": {"emailAddress": None}}],
                    "locations": None,
                }
            ]
        }
    )

    result = await microsoft365.execute_action(
        "find_meeting_times",
        {"attendees": ["a@b.com"]},
        mock_context,
    )

    assert result.type != ResultType.ACTION_ERROR
    suggestion = result.result.data["meeting_time_suggestions"][0]
    assert suggestion["start"] == ""
    assert suggestion["end"] == ""
    assert suggestion["attendee_availability"][0]["email"] == ""
    assert suggestion["suggested_locations"] == []


def test_find_meeting_times_declares_graph_permission_and_removes_shifts_scope():
    config = json.loads((Path(__file__).parents[1] / "config.json").read_text(encoding="utf-8"))
    assert config["version"] == "3.0.0"
    assert "Calendars.Read.Shared" in config["auth"]["scopes"]
    assert "Schedule.Read.All" not in config["auth"]["scopes"]


@pytest.mark.asyncio
async def test_find_meeting_times_missing_attendees(mock_context):
    result = await microsoft365.execute_action("find_meeting_times", {}, mock_context)
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_find_meeting_times_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "find_meeting_times",
        {"attendees": ["a@b.com"]},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- get_schedule ----


@pytest.mark.asyncio
async def test_get_schedule(mock_context):
    mock_context.fetch = make_fetch(
        {"value": [{"scheduleId": "a@b.com", "availabilityView": "000", "scheduleItems": []}]}
    )
    result = await microsoft365.execute_action(
        "get_schedule",
        {"schedules": ["a@b.com"], "start_datetime": "2026-06-15T09:00:00Z", "end_datetime": "2026-06-15T17:00:00Z"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert len(result.result.data["schedules"]) == 1
    _, kwargs = mock_context.fetch.await_args
    assert kwargs["json"]["startTime"] == {"dateTime": "2026-06-15T09:00:00", "timeZone": "UTC"}
    assert kwargs["json"]["endTime"] == {"dateTime": "2026-06-15T17:00:00", "timeZone": "UTC"}


@pytest.mark.asyncio
async def test_get_schedule_accepts_nullable_nested_fields(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "scheduleId": "a@b.com",
                    "scheduleItems": None,
                    "workingHours": {"timeZone": None},
                }
            ]
        }
    )

    result = await microsoft365.execute_action(
        "get_schedule",
        {"schedules": ["a@b.com"], "start_datetime": "2026-06-15T09:00:00Z", "end_datetime": "2026-06-15T17:00:00Z"},
        mock_context,
    )

    assert result.type != ResultType.ACTION_ERROR
    schedule = result.result.data["schedules"][0]
    assert schedule["schedule_items"] == []
    assert schedule["working_hours"]["timezone"] == ""


@pytest.mark.asyncio
async def test_get_schedule_missing_required_inputs(mock_context):
    # missing schedules
    result = await microsoft365.execute_action(
        "get_schedule",
        {"start_datetime": "2026-06-15T09:00:00Z", "end_datetime": "2026-06-15T17:00:00Z"},
        mock_context,
    )
    assert result.type == ResultType.VALIDATION_ERROR

    # missing start_datetime
    result = await microsoft365.execute_action(
        "get_schedule",
        {"schedules": ["a@b.com"], "end_datetime": "2026-06-15T17:00:00Z"},
        mock_context,
    )
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_get_schedule_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "get_schedule",
        {"schedules": ["a@b.com"], "start_datetime": "2026-06-15T09:00:00Z", "end_datetime": "2026-06-15T17:00:00Z"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR


# ---- list_rooms ----


@pytest.mark.asyncio
async def test_list_rooms(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "r1",
                    "displayName": "Room A",
                    "emailAddress": "rooma@co.com",
                    "capacity": 10,
                    "building": "HQ",
                    "floorNumber": 1,
                    "floorLabel": "1st",
                    "isWheelChairAccessible": True,
                    "audioDeviceName": "",
                    "videoDeviceName": "",
                    "displayDeviceName": "",
                    "phone": "",
                }
            ]
        }
    )
    result = await microsoft365.execute_action("list_rooms", {}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["total_count"] == 1


@pytest.mark.asyncio
async def test_list_rooms_omits_nullable_typed_properties(mock_context):
    mock_context.fetch = make_fetch(
        {
            "value": [
                {
                    "id": "r1",
                    "displayName": "Unconfigured room",
                    "capacity": None,
                    "floorNumber": None,
                    "isWheelChairAccessible": None,
                }
            ]
        }
    )

    result = await microsoft365.execute_action("list_rooms", {}, mock_context)

    assert result.type != ResultType.ACTION_ERROR
    room = result.result.data["rooms"][0]
    assert "capacity" not in room
    assert "floor_number" not in room
    assert "is_wheelchair_accessible" not in room


@pytest.mark.asyncio
async def test_list_rooms_missing_email_error(mock_context):
    result = await microsoft365.execute_action(
        "list_rooms",
        {"list_type": "rooms_in_list"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "room_list_email" in result.result.message


@pytest.mark.asyncio
async def test_list_rooms_encodes_room_list_email(mock_context):
    mock_context.fetch = make_fetch({"value": []})
    result = await microsoft365.execute_action(
        "list_rooms",
        {"list_type": "rooms_in_list", "room_list_email": "rooms+au@example.com"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    args, _ = mock_context.fetch.await_args
    assert "/places/rooms%2Bau%40example.com/microsoft.graph.roomList/rooms" in args[0]


@pytest.mark.asyncio
async def test_list_rooms_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("list_rooms", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


# ---- check_room_availability ----


@pytest.mark.asyncio
async def test_check_room_availability(mock_context):
    mock_context.fetch = make_fetch({"value": [{"scheduleId": "rooma@co.com", "scheduleItems": []}]})
    result = await microsoft365.execute_action(
        "check_room_availability",
        {
            "room_emails": ["rooma@co.com"],
            "start_datetime": "2026-06-15T10:00:00Z",
            "end_datetime": "2026-06-15T11:00:00Z",
        },
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert "rooma@co.com" in result.result.data["available_rooms"]


@pytest.mark.asyncio
async def test_check_room_availability_missing_required_inputs(mock_context):
    # missing room_emails
    result = await microsoft365.execute_action(
        "check_room_availability",
        {"start_datetime": "2026-06-15T10:00:00Z", "end_datetime": "2026-06-15T11:00:00Z"},
        mock_context,
    )
    assert result.type == ResultType.VALIDATION_ERROR

    # missing start_datetime
    result = await microsoft365.execute_action(
        "check_room_availability",
        {"room_emails": ["rooma@co.com"], "end_datetime": "2026-06-15T11:00:00Z"},
        mock_context,
    )
    assert result.type == ResultType.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_check_room_availability_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action(
        "check_room_availability",
        {
            "room_emails": ["rooma@co.com"],
            "start_datetime": "2026-06-15T10:00:00Z",
            "end_datetime": "2026-06-15T11:00:00Z",
        },
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
