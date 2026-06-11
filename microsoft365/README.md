# Microsoft Copilot 365 Integration for Autohive

Connects Autohive to Microsoft Copilot 365 services including Outlook, OneDrive, Calendar, and SharePoint through the Microsoft Graph API.

## Description

This integration provides comprehensive access to Microsoft Copilot 365 services, enabling agents to manage emails, calendar events, contacts, files, and SharePoint sites through a unified interface. It interacts with the Microsoft Graph API to deliver seamless integration with Outlook email, OneDrive file storage, Calendar management, SharePoint collaboration, and intelligent meeting scheduling.

Key capabilities include sending and managing emails, creating and updating calendar events, intelligent meeting scheduling with attendee availability detection, room discovery and availability checking, uploading and accessing files, reading contact information, and accessing SharePoint sites and document libraries. Advanced features include HTML email content, file attachments, timezone-aware operations, folder management, PDF conversion for Office documents, multi-drive SharePoint document access, `findMeetingTimes` for smart scheduling suggestions, `getSchedule` for free/busy availability lookups, and a `fields` parameter on `list_emails` to limit response payload when scanning large inboxes.

## Setup & Authentication

**Authentication Method:** Platform OAuth2 (Microsoft 365)

Users need to connect their Microsoft 365 account through the Autohive platform. No manual credential configuration is required.

Required Microsoft Graph API permissions:
- `Mail.ReadWrite` — Read and send emails
- `Mail.Send` — Send emails on behalf of user
- `Files.ReadWrite` — Access OneDrive files
- `Calendars.ReadWrite` — Manage calendar events
- `Contacts.Read` — Read user contacts
- `Sites.Read.All` — Access SharePoint sites and document libraries
- `Schedule.Read.All` — Read free/busy availability for users and rooms
- `Place.Read.All` — List and query meeting rooms and room lists

## Actions

### `send_email`

Send an email via Outlook with support for CC, BCC, and HTML content.

**Inputs:**
- `to` (required): Recipient email address
- `subject` (required): Email subject
- `body` (required): Email body content
- `body_type` (optional): Body content type — `Text` or `HTML` (default: `Text`)
- `cc` (optional): CC email addresses
- `bcc` (optional): BCC email addresses

**Outputs:**
- `status`: Confirmation string

---

### `list_emails`

List emails for a specific date range and folder. Defaults to last 24 hours if no date specified.

Returns full body HTML by default. Use the `fields` parameter to limit response to metadata only when scanning a large inbox to avoid context window issues.

**Inputs:**
- `start_datetime` (optional): Start datetime in UTC (ISO 8601, e.g. `2024-08-01T07:00:00Z`). Recommended over `start_date`.
- `end_datetime` (optional): End datetime in UTC (ISO 8601). Defaults to `start_datetime` if omitted.
- `start_date` (optional): Legacy date-only parameter (e.g. `2024-08-01`)
- `end_date` (optional): Legacy date-only parameter
- `folder` (optional): Mail folder to query (default: `Inbox`)
- `limit` (optional): Maximum number of emails to return
- `fields` (optional): List of fields to return per email. When omitted, all fields including `body.content` (full HTML) are returned. Use to reduce payload — e.g. `["id", "subject", "sender", "receivedDateTime", "hasAttachments", "bodyPreview"]` for a lightweight metadata scan. Allowed values: `id`, `subject`, `sender`, `receivedDateTime`, `bodyPreview`, `body`, `hasAttachments`, `isRead`, `importance`.

**Outputs:**
- `emails`: List of email objects
- `count`: Number of emails returned

> **Tip:** Using `fields` to exclude `body` reduces payload by ~65% on HTML-heavy inboxes.

---

### `list_emails_from_contact`

Get the latest emails from a specific contact.

**Inputs:**
- `contact_email` (required): Email address of the contact
- `limit` (optional): Maximum number of emails to return
- `folder` (optional): Mail folder to search (default: `Inbox`)

**Outputs:**
- `emails`: List of email objects from the specified contact
- `count`: Number of emails returned

---

### `read_email`

Read email content and list attachment metadata.

**Inputs:**
- `email_id` (required): Unique identifier of the email
- `include_attachments` (optional): Include attachment metadata (default: `true`)

**Outputs:**
- `email`: Complete email object with content
- `attachments`: List of attachment metadata (when requested)

---

### `mark_email_read`

Change the read/unread status of an email.

**Inputs:**
- `email_id` (required): Unique identifier of the email
- `is_read` (required): `true` to mark as read, `false` to mark as unread

**Outputs:**
- `id`: Email ID
- `isRead`: Updated read status

---

### `list_mail_folders`

List mail folders in the user's mailbox. Returns folder IDs needed for `move_email`. Use `include_children=true` to get all folders including nested subfolders.

**Inputs:**
- `folder_id` (optional): ID of a parent folder to list children of. If not provided, lists root-level folders.
- `include_hidden` (optional): Include hidden system folders (default: `false`)
- `include_children` (optional): Recursively include all nested child folders. Recommended when searching for a custom folder. (default: `false`)

**Outputs:**
- `folders`: List of folder objects with `id`, `displayName`, `parentFolderId`, `childFolderCount`, `unreadItemCount`, `totalItemCount`, `isHidden`
- `total_count`: Total number of folders returned

---

### `get_mail_folder`

Get details of a specific mail folder by ID or well-known name.

Well-known names (lowercase, no spaces): `inbox`, `drafts`, `sentitems`, `deleteditems`, `junkemail`, `archive`, `outbox`, `clutter`, `scheduled`, `searchfolders`, `conversationhistory`

**Inputs:**
- `folder_id` (required): Folder ID or well-known name

**Outputs:**
- `folder`: Folder object with `id`, `displayName`, `parentFolderId`, `childFolderCount`, `unreadItemCount`, `totalItemCount`, `isHidden`

---

### `move_email`

Move an email to a different folder.

For custom folders (e.g. "Clients", "Projects"), first call `list_mail_folders` with `include_children=true` to find the folder ID. For system folders, use the well-known name directly.

**Inputs:**
- `email_id` (required): Unique identifier of the email
- `destination_folder_id` (required): Destination folder ID (from `list_mail_folders`) or a well-known folder name (`inbox`, `drafts`, `sentitems`, `deleteditems`, `junkemail`, `archive`, `outbox`, `clutter`, `scheduled`)

**Outputs:**
- `id`: ID of the moved email
- `parentFolderId`: ID of the destination folder
- `subject`: Subject of the moved email

---

### `create_draft_email`

Create a draft email message that can be sent later.

**Inputs:**
- `subject` (required): Email subject line
- `body` (required): Email body content
- `to_recipients` (required): List of recipient email addresses
- `body_type` (optional): Content type — `Text` or `HTML` (default: `Text`)
- `cc_recipients` (optional): List of CC recipient email addresses
- `bcc_recipients` (optional): List of BCC recipient email addresses
- `importance` (optional): `Low`, `Normal`, or `High`

**Outputs:**
- `draft_id`: ID of the created draft
- `subject`: Subject of the draft
- `created_datetime`: When the draft was created
- `is_draft`: `true`

---

### `send_draft_email`

Send a previously created draft email.

**Inputs:**
- `draft_id` (required): ID of the draft to send

**Outputs:**
- `draft_id`: ID of the sent draft
- `status`: Confirmation string

---

### `reply_to_email`

Reply to an existing email message.

**Inputs:**
- `message_id` (required): ID of the message to reply to
- `comment` (optional): Reply message text

**Outputs:**
- `message_id`: ID of the original message
- `operation`: `reply`
- `status`: Confirmation string

---

### `forward_email`

Forward an existing email message to other recipients.

**Inputs:**
- `message_id` (required): ID of the message to forward
- `to_recipients` (required): List of recipients to forward to
- `comment` (optional): Additional message text to include

**Outputs:**
- `message_id`: ID of the original message
- `operation`: `forward`
- `status`: Confirmation string

---

### `download_email_attachment`

Download the content of an email attachment. Returns the same file format as OneDrive/SharePoint reads for consistent handling.

**Inputs:**
- `message_id` (required): ID of the message containing the attachment
- `attachment_id` (required): ID of the attachment to download
- `include_content` (optional): Whether to include attachment content (default: `true`)

**Outputs:**
- `file`: Object with `content` (base64 encoded), `name`, `contentType`
- `metadata`: Object with `id`, `name`, `size`, `contentType`, `message_id`, `is_inline`

---

### `search_emails`

Search for emails using natural language queries.

**Inputs:**
- `query` (required): Search query (searches body, sender, subject, and attachments)
- `limit` (optional): Maximum number of results (default: 25, max: 1000)
- `enable_top_results` (optional): Enable relevance-based ranking (default: `false`)

**Outputs:**
- `query`: The search query executed
- `total_results`: Total number of matching emails
- `messages`: List of matching email messages

---

### `create_calendar_event`

Create a calendar event with attendees and location.

**Inputs:**
- `subject` (required): Event title
- `start_time` (required): Start time (ISO 8601 UTC)
- `end_time` (required): End time (ISO 8601 UTC)
- `location` (optional): Event location
- `body` (optional): Event description
- `attendees` (optional): List of attendee email addresses

**Outputs:**
- `id`: Unique identifier of the created event
- `webLink`: Web link to the event

---

### `update_calendar_event`

Update an existing calendar event.

**Inputs:**
- `event_id` (required): ID of the event to update
- `subject` (optional): Updated event title
- `start_time` (optional): Updated start time (ISO 8601 UTC)
- `end_time` (optional): Updated end time (ISO 8601 UTC)
- `location` (optional): Updated location
- `attendees` (optional): Updated list of attendee email addresses

**Outputs:**
- `id`: ID of the updated event
- `webLink`: Web link to the event

---

### `list_calendar_events`

List calendar events for a date range using Microsoft Graph `calendarView` for accurate filtering. Properly expands recurring events. Defaults to next 30 days if no dates provided.

**Inputs:**
- `start_datetime` (optional): Start datetime in UTC (ISO 8601, e.g. `2024-08-01T00:00:00Z`). Recommended.
- `end_datetime` (optional): End datetime in UTC (ISO 8601)
- `start_date` (optional): Legacy date-only parameter (e.g. `2024-08-01`)
- `end_date` (optional): Legacy date-only parameter
- `limit` (optional): Maximum number of events (default: 100)
- `user_timezone` (optional): User's timezone for intelligent defaults

**Outputs:**
- `events`: List of calendar event objects with `subject`, `start`, `end`, `location`, `organizer`, `attendees`

---

### `find_meeting_times`

Find available meeting time slots based on attendee availability, working hours, and optional room requirements. Uses Microsoft Graph `findMeetingTimes`.

**Inputs:**
- `attendees` (required): List of attendee email addresses
- `duration_minutes` (optional): Meeting duration in minutes (default: 60)
- `start_datetime` (optional): Start of search range (ISO 8601 UTC). Defaults to now.
- `end_datetime` (optional): End of search range (ISO 8601 UTC). Defaults to 7 days from start.
- `max_candidates` (optional): Maximum suggestions to return (default: 10, max: 20)
- `is_organizer_optional` (optional): Whether the organizer is optional (default: `false`)
- `location_constraint` (optional): Room/location email address to include as a required resource
- `minimum_attendee_percentage` (optional): Minimum % of attendees that must be available (0–100, default: 100)

**Outputs:**
- `meeting_time_suggestions`: List of suggested time slots with confidence scores, availability info, and suggested locations
- `empty_suggestions_reason`: Reason if no suggestions were returned

Requires `Calendars.ReadWrite` and `Schedule.Read.All` scopes.

---

### `get_schedule`

Get the free/busy availability schedule for one or more users or rooms. Returns busy time slots, working hours, and an availability view string.

**Inputs:**
- `schedules` (required): List of email addresses (users or rooms)
- `start_datetime` (required): Start of time range (ISO 8601 UTC)
- `end_datetime` (required): End of time range (ISO 8601 UTC)
- `availability_view_interval` (optional): Time slot duration in minutes for the view string (default: 30, range: 5–1440)

**Outputs:**
- `schedules`: List of availability objects, each with:
  - `email`: Email address
  - `availability_view`: String where each character = a slot (0=free, 1=tentative, 2=busy, 3=OOO, 4=working elsewhere)
  - `schedule_items`: List of calendar items with status, start/end, subject, location
  - `working_hours`: Working hours configuration

Requires `Schedule.Read.All` scope.

---

### `list_rooms`

List available meeting rooms and room lists in the organization.

**Inputs:**
- `list_type` (optional): `rooms` (all rooms), `room_lists` (buildings/floors), or `rooms_in_list` (rooms in a specific list) (default: `rooms`)
- `room_list_email` (optional): Email of a room list — required when `list_type` is `rooms_in_list`
- `limit` (optional): Maximum number of rooms (default: 100)

**Outputs:**
- `rooms`: List of room objects with `id`, `display_name`, `email_address`, `capacity`, `building`, `floor_number`, A/V equipment details
- `total_count`: Number of rooms/lists returned

Room email addresses can be used with `check_room_availability`, `get_schedule`, and `find_meeting_times`. Requires `Place.Read.All` scope.

---

### `check_room_availability`

Check if specific meeting rooms are available during a time range.

**Inputs:**
- `room_emails` (required): List of room email addresses (from `list_rooms`)
- `start_datetime` (required): Start of time range (ISO 8601 UTC)
- `end_datetime` (required): End of time range (ISO 8601 UTC)

**Outputs:**
- `rooms`: List of room availability objects, each with `email`, `is_available`, `conflicts`
- `available_rooms`: List of room emails that are fully free
- `unavailable_rooms`: List of room emails that have conflicts

Requires `Schedule.Read.All` scope.

---

### `upload_file`

Upload a file to OneDrive.

**Inputs:**
- `filename` (required): Name of the file (e.g. `report.txt`, `notes.md`)
- `content` (required): Text content of the file
- `content_type` (optional): MIME type
- `folder_path` (optional): Destination folder path in OneDrive (default: root)

**Outputs:**
- `id`: ID of the uploaded file
- `webUrl`: Web URL to access the file
- `size`: File size in bytes

---

### `list_files`

List files and folders in a OneDrive folder.

**Inputs:**
- `folder_path` (optional): Folder path to list (default: root)
- `limit` (optional): Maximum number of items

**Outputs:**
- `files`: List of file and folder objects
- `count`: Number of items returned

---

### `search_onedrive_files`

Search for files in OneDrive using natural language queries.

**Inputs:**
- `query` (required): Search query (e.g. `quarterly report`, `budget 2024`)
- `limit` (optional): Maximum number of files (default: 10)

**Outputs:**
- `files`: List of matching file objects with metadata
- `query`: The search query executed

---

### `read_onedrive_file_content`

Read the content of a OneDrive file. Office documents (`.docx`, `.xlsx`, `.pptx`, etc.) are automatically converted to PDF. Binary content is fetched directly to preserve file integrity.

**Inputs:**
- `file_id` (required): File ID (from `search_onedrive_files` or `list_files`)

**Outputs:**
- `file`: Object with `content` (base64 encoded), `name`, `contentType` (`application/pdf` for converted Office docs)
- `metadata`: File metadata with `id`, `size`, `webUrl`

---

### `read_contacts`

Read and search contacts from Outlook.

**Inputs:**
- `limit` (optional): Maximum number of contacts
- `search` (optional): Filter contacts by name or company (case-insensitive, partial match)

**Outputs:**
- `contacts`: List of contact objects with detailed information
- `message`: Description of the search results
- `search_term`: The search term used (when searching)
- `total_searched`: Total contacts searched through (when searching)

---

### `search_sharepoint_sites`

Search for SharePoint sites across your organization. Searches top-level site collections; use `list_sharepoint_subsites` to discover child sites under a known parent.

**Inputs:**
- `query` (required): Search query to find sites
- `order_by_created` (optional): Sort by creation date, newest first

**Outputs:**
- `query`: The search query executed
- `sites`: List of matching SharePoint sites
- `total_sites`: Total number of sites found

---

### `get_sharepoint_site_details`

Get detailed information about a specific SharePoint site.

**Inputs:**
- `site_id` (required): The ID of the SharePoint site

**Outputs:**
- `site`: Site details including `displayName`, `description`, `webUrl`, and metadata

---

### `list_sharepoint_libraries`

List all document libraries (drives) in a SharePoint site.

**Inputs:**
- `site_id` (required): The ID of the SharePoint site
- `limit` (optional): Maximum number of libraries
- `select_fields` (optional): Comma-separated list of fields to return

**Outputs:**
- `site_id`: The SharePoint site ID
- `libraries`: List of document libraries with metadata
- `total_libraries`: Total number of libraries found

---

### `search_sharepoint_documents`

Search for documents across all document libraries in a SharePoint site.

**Inputs:**
- `site_id` (required): The ID of the SharePoint site
- `query` (required): Search query to find documents
- `limit` (optional): Maximum number of documents (default: 10)

**Outputs:**
- `site_id`: The SharePoint site ID
- `query`: The search query executed
- `files`: List of matching documents with drive information
- `total_files`: Total number of files found
- `drives_searched`: Number of libraries searched
- `total_drives`: Total number of libraries in the site
- `search_errors`: Errors encountered during search (if any)

---

### `read_sharepoint_document`

Read the content of a SharePoint document. Office documents are automatically converted to PDF. Binary content is fetched directly to preserve file integrity.

**Inputs:**
- `site_id` (required): The ID of the SharePoint site
- `file_id` (required): The ID of the file to read
- `drive_id` (optional): ID of the specific document library containing the file. If not provided, uses the site's default drive.

**Outputs:**
- `file`: Object with `content` (base64 encoded), `name`, `contentType`
- `metadata`: File metadata with `id`, `size`, `webUrl`, `site_id`, `drive_id`

---

### `list_sharepoint_pages`

List all pages in a SharePoint site.

**Inputs:**
- `site_id` (required): The ID of the SharePoint site
- `limit` (optional): Maximum number of pages
- `order_by` (optional): Sort order (e.g. `createdDateTime desc`)
- `select_fields` (optional): Comma-separated list of fields to return

**Outputs:**
- `site_id`: The SharePoint site ID
- `pages`: List of pages with metadata
- `total_pages`: Total number of pages found

---

### `read_sharepoint_page_content`

Read the content and metadata of a SharePoint site page.

**Inputs:**
- `site_id` (required): The ID of the SharePoint site
- `page_id` (required): The ID of the page to read
- `include_content` (optional): Whether to include page content and web parts (default: `true`)

**Outputs:**
- `site_id`: The SharePoint site ID
- `page`: Page details including `title`, `layout`, and content

---

### `list_sharepoint_subsites`

List all subsites (child sites) under a SharePoint site.

**Inputs:**
- `site_id` (required): The ID of the parent SharePoint site
- `limit` (optional): Maximum number of subsites

**Outputs:**
- `site_id`: The parent site ID
- `subsites`: List of subsite objects with `id`, `displayName`, `webUrl`, `description`
- `total_subsites`: Total number of subsites found

---

### `list_sharepoint_folder_contents`

List files and folders within a SharePoint document library or subfolder. Use without `folder_id` to list root contents, or with `folder_id` to browse into subfolders.

**Inputs:**
- `drive_id` (required): The ID of the document library (from `list_sharepoint_libraries`)
- `folder_id` (optional): ID of a specific folder to list contents of. If not provided, lists root of the library.
- `limit` (optional): Maximum number of items (default: 50)

**Outputs:**
- `drive_id`: The document library ID
- `folder_id`: The folder ID browsed (if provided)
- `items`: List of file and folder objects with `id`, `name`, `type`, `size`, `webUrl`, `lastModifiedDateTime`
- `total_items`: Total number of items

---

## Requirements

- `autohive-integrations-sdk~=2.0.0`
- `aiohttp>=3.9.0`

## Usage Examples

**Send a simple email**

```json
{
  "to": "recipient@example.com",
  "subject": "Hello from Autohive",
  "body": "This is a test email.",
  "body_type": "Text"
}
```

**List emails — metadata only (large inbox scan)**

```json
{
  "start_datetime": "2024-08-01T00:00:00Z",
  "end_datetime": "2024-08-01T23:59:59Z",
  "fields": ["id", "subject", "sender", "receivedDateTime", "hasAttachments", "bodyPreview"]
}
```

**Create a calendar event with attendees**

```json
{
  "subject": "Team Meeting",
  "start_time": "2024-08-01T14:00:00Z",
  "end_time": "2024-08-01T15:00:00Z",
  "location": "Conference Room A",
  "body": "Weekly team sync",
  "attendees": ["team@example.com", "manager@example.com"]
}
```

**Move email to a custom folder (2-step)**

Step 1 — find the folder ID:
```json
// list_mail_folders
{ "include_children": true }
// → { "id": "AQMkADYAAAIBXQAAAA==", "displayName": "Clients", ... }
```

Step 2 — move using the folder ID:
```json
// move_email
{
  "email_id": "AAMkAGVmMDEzMTM...",
  "destination_folder_id": "AQMkADYAAAIBXQAAAA=="
}
```

**Move email to a system folder**

```json
{
  "email_id": "AAMkAGVmMDEzMTM...",
  "destination_folder_id": "archive"
}
```

**Find available meeting times**

```json
{
  "attendees": ["john@contoso.com", "sarah@contoso.com"],
  "duration_minutes": 60,
  "start_datetime": "2024-08-19T08:00:00Z",
  "end_datetime": "2024-08-23T18:00:00Z",
  "max_candidates": 5
}
```

**Full meeting scheduling workflow**

1. `list_rooms` — discover room email addresses
2. `find_meeting_times` with `location_constraint` — find mutual availability + room
3. `create_calendar_event` — book the chosen slot

**Browse a SharePoint document library**

1. `search_sharepoint_sites` — find site
2. `list_sharepoint_libraries` — list drives in the site
3. `list_sharepoint_folder_contents` with `drive_id` — browse root or subfolders
4. `read_sharepoint_document` with `file_id` and `drive_id` — read the file

**Discover SharePoint subsites**

```json
// search_sharepoint_sites to find parent site
{ "query": "HR Portal" }
// → site_id: "contoso.sharepoint.com,abc,xyz"

// list_sharepoint_subsites to find child sites
{ "site_id": "contoso.sharepoint.com,abc,xyz" }
```

## Testing

Install dependencies:
```bash
pip install -r requirements.txt
```

Run unit tests (no credentials needed):
```bash
cd microsoft365
python -m pytest tests/test_microsoft365_unit.py -v
```

Run live integration tests (requires a valid Microsoft 365 access token):
```bash
export MICROSOFT365_ACCESS_TOKEN="eyJ0eXAiOiJKV1Qi..."
python -m pytest tests/test_microsoft365_integration.py -v -m integration
```

Obtain an access token from the Microsoft Azure portal or via the Autohive platform OAuth flow. Tokens expire after approximately 80 minutes.
