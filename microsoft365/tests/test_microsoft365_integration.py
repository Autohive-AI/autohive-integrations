import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import aiohttp
import pytest
from autohive_integrations_sdk import FetchResponse, ResultType
from microsoft365.microsoft365 import microsoft365

pytestmark = pytest.mark.integration

CRED = os.getenv("MICROSOFT365_ACCESS_TOKEN", "")
skip_if_no_creds = pytest.mark.skipif(not CRED, reason="MICROSOFT365_ACCESS_TOKEN required")

# Shared state for chained tests (create → use → delete)
_state: dict = {}


@pytest.fixture
def live_context(make_context):
    async def real_fetch(url, *, method="GET", params=None, headers=None, json=None, body=None, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                params=params,
                json=json,
                data=body,
                headers={"Authorization": f"Bearer {CRED}", **(dict(headers or {}))},
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = await resp.read()
                return FetchResponse(status=resp.status, headers=dict(resp.headers), data=data)

    ctx = make_context(auth={})
    ctx.fetch.side_effect = real_fetch
    return ctx


# ============================================================
# EMAIL — READ
# ============================================================


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_emails_live(live_context):
    result = await microsoft365.execute_action("list_emails", {"limit": 5}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    data = result.result.data
    assert "emails" in data
    if data["emails"]:
        _state["email_id"] = data["emails"][0]["id"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_emails_with_fields_live(live_context):
    result = await microsoft365.execute_action(
        "list_emails",
        {"limit": 3, "fields": ["id", "subject", "sender", "receivedDateTime", "hasAttachments", "bodyPreview"]},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    emails = result.result.data["emails"]
    for email in emails:
        assert "body" not in email, "body should be excluded when not in fields"


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_emails_from_contact_live(live_context):
    result = await microsoft365.execute_action(
        "list_emails_from_contact",
        {"contact_email": "noreply@microsoft.com", "limit": 3},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "emails" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_read_email_live(live_context):
    email_id = _state.get("email_id")
    if not email_id:
        pytest.skip("No email_id from test_list_emails_live")
    result = await microsoft365.execute_action(
        "read_email", {"email_id": email_id, "include_attachments": False}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "email" in result.result.data
    assert result.result.data["email"]["id"] == email_id


@skip_if_no_creds
@pytest.mark.asyncio
async def test_search_emails_live(live_context):
    result = await microsoft365.execute_action(
        "search_emails", {"query": "test", "limit": 5}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "messages" in result.result.data


# ============================================================
# EMAIL — WRITE (chained: draft → mark read → move → send)
# ============================================================


@skip_if_no_creds
@pytest.mark.asyncio
async def test_01_create_draft_email_live(live_context):
    result = await microsoft365.execute_action(
        "create_draft_email",
        {
            "subject": "[Autohive Integration Test] Draft",
            "body": "This is an integration test draft. Safe to delete.",
            "body_type": "Text",
            "to_recipients": ["shubhank@autohive.com"],
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "draft_id" in result.result.data
    _state["draft_id"] = result.result.data["draft_id"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_02_mark_email_read_live(live_context):
    draft_id = _state.get("draft_id")
    if not draft_id:
        pytest.skip("No draft_id from test_01")
    result = await microsoft365.execute_action(
        "mark_email_read", {"email_id": draft_id, "is_read": True}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message


@skip_if_no_creds
@pytest.mark.asyncio
async def test_03_send_draft_email_live(live_context):
    draft_id = _state.get("draft_id")
    if not draft_id:
        pytest.skip("No draft_id from test_01")
    result = await microsoft365.execute_action(
        "send_draft_email", {"draft_id": draft_id}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("sent") is True


@skip_if_no_creds
@pytest.mark.asyncio
async def test_04_send_email_live(live_context):
    result = await microsoft365.execute_action(
        "send_email",
        {
            "to": "shubhank@autohive.com",
            "subject": "[Autohive Integration Test] Direct Send",
            "body": "Integration test email — safe to delete.",
            "body_type": "Text",
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("sent") is True


@skip_if_no_creds
@pytest.mark.asyncio
async def test_05_reply_to_email_live(live_context):
    email_id = _state.get("email_id")
    if not email_id:
        pytest.skip("No email_id from test_list_emails_live")
    result = await microsoft365.execute_action(
        "reply_to_email",
        {"message_id": email_id, "comment": "Integration test reply — safe to ignore."},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("sent") is True


@skip_if_no_creds
@pytest.mark.asyncio
async def test_06_forward_email_live(live_context):
    email_id = _state.get("email_id")
    if not email_id:
        pytest.skip("No email_id from test_list_emails_live")
    result = await microsoft365.execute_action(
        "forward_email",
        {
            "message_id": email_id,
            "to_recipients": ["shubhank@autohive.com"],
            "comment": "Integration test forward — safe to ignore.",
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data.get("sent") is True


# ============================================================
# EMAIL — FOLDERS
# ============================================================


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_mail_folders_live(live_context):
    result = await microsoft365.execute_action(
        "list_mail_folders", {"include_hidden": False, "include_children": False}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    data = result.result.data
    assert "folders" in data
    if data["folders"]:
        _state["inbox_folder_id"] = next(
            (f["id"] for f in data["folders"] if f.get("displayName") == "Inbox"),
            data["folders"][0]["id"],
        )


@skip_if_no_creds
@pytest.mark.asyncio
async def test_get_mail_folder_live(live_context):
    result = await microsoft365.execute_action(
        "get_mail_folder", {"folder_id": "inbox"}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "folder" in result.result.data
    assert result.result.data["folder"]["id"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_move_email_live(live_context):
    email_id = _state.get("email_id")
    if not email_id:
        pytest.skip("No email_id from test_list_emails_live")
    # Move to Drafts then back — non-destructive round-trip
    result = await microsoft365.execute_action(
        "move_email",
        {"email_id": email_id, "destination_folder_id": "drafts"},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data["id"]
    # Move back to inbox
    moved_id = result.result.data["id"]
    await microsoft365.execute_action(
        "move_email",
        {"email_id": moved_id, "destination_folder_id": "inbox"},
        live_context,
    )


# ============================================================
# EMAIL — ATTACHMENTS
# ============================================================


@skip_if_no_creds
@pytest.mark.asyncio
async def test_download_email_attachment_live(live_context):
    # Find an email with attachments first
    result = await microsoft365.execute_action(
        "list_emails", {"limit": 20, "fields": ["id", "hasAttachments"]}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    email_with_att = next(
        (e for e in result.result.data["emails"] if e.get("hasAttachments")), None
    )
    if not email_with_att:
        pytest.skip("No emails with attachments found in inbox")

    # Read the email to get attachment IDs
    read_result = await microsoft365.execute_action(
        "read_email", {"email_id": email_with_att["id"], "include_attachments": True}, live_context
    )
    assert read_result.type != ResultType.ACTION_ERROR, read_result.result.message
    attachments = read_result.result.data.get("attachments", [])
    if not attachments:
        pytest.skip("Email reported hasAttachments but no attachments returned")

    att_id = attachments[0]["id"]
    result = await microsoft365.execute_action(
        "download_email_attachment",
        {"message_id": email_with_att["id"], "attachment_id": att_id, "include_content": True},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "file" in result.result.data
    assert "metadata" in result.result.data


# ============================================================
# CALENDAR
# ============================================================


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_calendar_events_live(live_context):
    result = await microsoft365.execute_action("list_calendar_events", {"limit": 5}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "events" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_07_create_calendar_event_live(live_context):
    result = await microsoft365.execute_action(
        "create_calendar_event",
        {
            "subject": "[Autohive Integration Test] Event",
            "start_time": "2026-12-01T10:00:00",
            "end_time": "2026-12-01T11:00:00",
            "body": "Integration test event — safe to delete.",
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "id" in result.result.data
    _state["calendar_event_id"] = result.result.data["id"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_08_update_calendar_event_live(live_context):
    event_id = _state.get("calendar_event_id")
    if not event_id:
        pytest.skip("No calendar_event_id from test_07")
    result = await microsoft365.execute_action(
        "update_calendar_event",
        {"event_id": event_id, "subject": "[Autohive Integration Test] Event (Updated)"},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert result.result.data["id"] == event_id


@skip_if_no_creds
@pytest.mark.asyncio
async def test_find_meeting_times_live(live_context):
    result = await microsoft365.execute_action(
        "find_meeting_times",
        {
            "attendees": ["shubhank@autohive.com"],
            "duration_minutes": 30,
            "start_datetime": "2026-12-01T08:00:00Z",
            "end_datetime": "2026-12-01T18:00:00Z",
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "meeting_time_suggestions" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_get_schedule_live(live_context):
    result = await microsoft365.execute_action(
        "get_schedule",
        {
            "schedules": ["shubhank@RaygunLtd.onmicrosoft.com"],
            "start_datetime": "2026-12-01T08:00:00Z",
            "end_datetime": "2026-12-01T18:00:00Z",
            "availability_view_interval": 60,
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "schedules" in result.result.data


# ============================================================
# ONEDRIVE
# ============================================================


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_files_live(live_context):
    result = await microsoft365.execute_action("list_files", {"folder_path": "/"}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    data = result.result.data
    assert "files" in data
    if data["files"]:
        _state["onedrive_file_id"] = data["files"][0]["id"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_search_onedrive_files_live(live_context):
    result = await microsoft365.execute_action(
        "search_onedrive_files", {"query": "test", "limit": 5}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "files" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_09_upload_file_live(live_context):
    result = await microsoft365.execute_action(
        "upload_file",
        {
            "filename": "autohive_integration_test.txt",
            "content": "Integration test file — safe to delete.",
            "content_type": "text/plain",
            "folder_path": "/",
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "id" in result.result.data
    _state["uploaded_file_id"] = result.result.data["id"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_read_onedrive_file_content_live(live_context):
    file_id = _state.get("uploaded_file_id") or _state.get("onedrive_file_id")
    if not file_id:
        pytest.skip("No file_id available")
    result = await microsoft365.execute_action(
        "read_onedrive_file_content", {"file_id": file_id}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "file" in result.result.data
    assert "metadata" in result.result.data


# ============================================================
# CONTACTS
# ============================================================


@skip_if_no_creds
@pytest.mark.asyncio
async def test_read_contacts_live(live_context):
    result = await microsoft365.execute_action("read_contacts", {"limit": 5}, live_context)
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "contacts" in result.result.data


# ============================================================
# SHAREPOINT
# ============================================================


@skip_if_no_creds
@pytest.mark.asyncio
async def test_search_sharepoint_sites_live(live_context):
    result = await microsoft365.execute_action(
        "search_sharepoint_sites", {"query": "test"}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    data = result.result.data
    assert "sites" in data
    if data["sites"]:
        _state["sharepoint_site_id"] = data["sites"][0]["id"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_get_sharepoint_site_details_live(live_context):
    site_id = _state.get("sharepoint_site_id")
    if not site_id:
        pytest.skip("No sharepoint_site_id from test_search_sharepoint_sites_live")
    result = await microsoft365.execute_action(
        "get_sharepoint_site_details", {"site_id": site_id}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "site" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_sharepoint_libraries_live(live_context):
    site_id = _state.get("sharepoint_site_id")
    if not site_id:
        pytest.skip("No sharepoint_site_id from test_search_sharepoint_sites_live")
    result = await microsoft365.execute_action(
        "list_sharepoint_libraries", {"site_id": site_id}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    data = result.result.data
    assert "libraries" in data
    if data["libraries"]:
        _state["sharepoint_drive_id"] = data["libraries"][0]["id"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_search_sharepoint_documents_live(live_context):
    site_id = _state.get("sharepoint_site_id")
    if not site_id:
        pytest.skip("No sharepoint_site_id from test_search_sharepoint_sites_live")
    result = await microsoft365.execute_action(
        "search_sharepoint_documents",
        {"site_id": site_id, "query": "test", "limit": 5},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    data = result.result.data
    assert "files" in data
    if data["files"]:
        _state["sharepoint_file_id"] = data["files"][0]["id"]
        _state["sharepoint_file_drive_id"] = data["files"][0].get("drive_id", "")


@skip_if_no_creds
@pytest.mark.asyncio
async def test_read_sharepoint_document_live(live_context):
    site_id = _state.get("sharepoint_site_id")
    file_id = _state.get("sharepoint_file_id")
    if not site_id or not file_id:
        pytest.skip("No sharepoint site/file from earlier tests")
    result = await microsoft365.execute_action(
        "read_sharepoint_document",
        {
            "site_id": site_id,
            "file_id": file_id,
            "drive_id": _state.get("sharepoint_file_drive_id", ""),
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "file" in result.result.data
    assert "metadata" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_sharepoint_pages_live(live_context):
    site_id = _state.get("sharepoint_site_id")
    if not site_id:
        pytest.skip("No sharepoint_site_id from test_search_sharepoint_sites_live")
    result = await microsoft365.execute_action(
        "list_sharepoint_pages", {"site_id": site_id}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    data = result.result.data
    assert "pages" in data
    if data["pages"]:
        _state["sharepoint_page_id"] = data["pages"][0]["id"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_read_sharepoint_page_content_live(live_context):
    site_id = _state.get("sharepoint_site_id")
    page_id = _state.get("sharepoint_page_id")
    if not site_id or not page_id:
        pytest.skip("No sharepoint site/page from earlier tests")
    result = await microsoft365.execute_action(
        "read_sharepoint_page_content",
        {"site_id": site_id, "page_id": page_id, "include_content": True},
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "page" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_sharepoint_subsites_live(live_context):
    site_id = _state.get("sharepoint_site_id")
    if not site_id:
        pytest.skip("No sharepoint_site_id from test_search_sharepoint_sites_live")
    result = await microsoft365.execute_action(
        "list_sharepoint_subsites", {"site_id": site_id}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "subsites" in result.result.data


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_sharepoint_folder_contents_live(live_context):
    drive_id = _state.get("sharepoint_drive_id")
    if not drive_id:
        pytest.skip("No sharepoint_drive_id from test_list_sharepoint_libraries_live")
    result = await microsoft365.execute_action(
        "list_sharepoint_folder_contents", {"drive_id": drive_id}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "items" in result.result.data


# ============================================================
# ROOMS
# ============================================================


@skip_if_no_creds
@pytest.mark.asyncio
async def test_list_rooms_live(live_context):
    result = await microsoft365.execute_action(
        "list_rooms", {"list_type": "rooms", "limit": 10}, live_context
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    data = result.result.data
    assert "rooms" in data
    if data["rooms"]:
        _state["room_email"] = data["rooms"][0]["email_address"]


@skip_if_no_creds
@pytest.mark.asyncio
async def test_check_room_availability_live(live_context):
    room_email = _state.get("room_email")
    if not room_email:
        pytest.skip("No room_email from test_list_rooms_live")
    result = await microsoft365.execute_action(
        "check_room_availability",
        {
            "room_emails": [room_email],
            "start_datetime": "2026-12-01T10:00:00Z",
            "end_datetime": "2026-12-01T11:00:00Z",
        },
        live_context,
    )
    assert result.type != ResultType.ACTION_ERROR, result.result.message
    assert "rooms" in result.result.data
