import os
import sys

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


@pytest.mark.asyncio
async def test_upload_file(mock_context):
    mock_context.fetch = make_fetch({"id": "file1", "webUrl": "https://onedrive.com/f1", "size": 100})
    result = await microsoft365.execute_action(
        "upload_file",
        {"filename": "test.txt", "content": "hello"},
        mock_context,
    )
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["id"] == "file1"


@pytest.mark.asyncio
async def test_upload_file_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("upload failed"))
    result = await microsoft365.execute_action(
        "upload_file",
        {"filename": "test.txt", "content": "hello"},
        mock_context,
    )
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
async def test_list_calendar_events_error(mock_context):
    mock_context.fetch = AsyncMock(side_effect=Exception("err"))
    result = await microsoft365.execute_action("list_calendar_events", {}, mock_context)
    assert result.type == ResultType.ACTION_ERROR


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
    metadata = {"id": "f1", "name": "readme.txt", "size": 50, "mimeType": "text/plain", "webUrl": "https://od.com/f1"}
    mock_context.fetch = make_fetch(metadata)
    with patch("microsoft365.microsoft365._fetch_binary", new=AsyncMock(return_value=b"hello world")):
        result = await microsoft365.execute_action("read_onedrive_file_content", {"file_id": "f1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert result.result.data["file"]["name"] == "readme.txt"


@pytest.mark.asyncio
async def test_read_onedrive_file_content_content_error(mock_context):
    metadata = {"id": "f1", "name": "readme.txt", "size": 50, "mimeType": "text/plain", "webUrl": "https://od.com/f1"}
    mock_context.fetch = make_fetch(metadata)
    with patch("microsoft365.microsoft365._fetch_binary", new=AsyncMock(side_effect=Exception("binary fetch failed"))):
        result = await microsoft365.execute_action("read_onedrive_file_content", {"file_id": "f1"}, mock_context)
    assert result.type != ResultType.ACTION_ERROR
    assert "content_error" in result.result.data
    assert result.result.data["file"]["content"] == ""


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
    assert result.type != ResultType.ACTION_ERROR
    assert "content_error" in result.result.data
    assert result.result.data["file"]["content"] == ""


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
    metadata = {"id": "f1", "name": "readme.txt", "size": 50, "mimeType": "text/plain", "webUrl": "https://sp.com/f1"}
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
    metadata = {"id": "f1", "name": "doc.txt", "size": 50, "mimeType": "text/plain", "webUrl": "https://sp.com/f1"}
    mock_context.fetch = make_fetch(metadata)
    with patch("microsoft365.microsoft365._fetch_binary", new=AsyncMock(side_effect=Exception("binary fetch failed"))):
        result = await microsoft365.execute_action(
            "read_sharepoint_document",
            {"site_id": "s1", "file_id": "f1"},
            mock_context,
        )
    assert result.type != ResultType.ACTION_ERROR
    assert "content_error" in result.result.data
    assert result.result.data["file"]["content"] == ""


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
async def test_list_rooms_missing_email_error(mock_context):
    result = await microsoft365.execute_action(
        "list_rooms",
        {"list_type": "rooms_in_list"},
        mock_context,
    )
    assert result.type == ResultType.ACTION_ERROR
    assert "room_list_email" in result.result.message


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
