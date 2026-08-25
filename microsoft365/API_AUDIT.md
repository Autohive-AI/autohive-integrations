# Microsoft Graph API audit

Audit date: 26 August 2026  
Integration version: 3.0.0

Every Microsoft 365 action was compared with the Microsoft Graph v1.0 documentation listed below. “Verified” means the existing HTTP method, resource path, and payload match the documented API. “Fixed” means this audit changed the implementation or public contract.

| Action | Official Microsoft Graph documentation | Result |
|---|---|---|
| `send_email` | [Send mail](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0) | Verified request and `202 Accepted` behavior; corrected the documented output to `sent`. |
| `create_calendar_event` | [Create event](https://learn.microsoft.com/en-us/graph/api/user-post-events?view=graph-rest-1.0) | Fixed ISO 8601 parsing, UTC normalization, and invalid date-range rejection. |
| `upload_file` | [Upload or replace drive item contents](https://learn.microsoft.com/en-us/graph/api/driveitem-put-content?view=graph-rest-1.0) | Fixed path encoding, response validation, and the documented 250 MB simple-upload limit. |
| `list_files` | [List drive item children](https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0) | Fixed folder-path encoding, response validation, and `@odata.nextLink` pagination. |
| `update_calendar_event` | [Update event](https://learn.microsoft.com/en-us/graph/api/event-update?view=graph-rest-1.0) | Fixed ID encoding, UTC normalization, empty-value updates, no-op rejection, and response validation. |
| `list_calendar_events` | [List calendar view](https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0) | Fixed query parameter encoding, timezone normalization, date validation, safe defaults, pagination, and nullable fields. |
| `list_emails` | [List messages](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0) | Fixed folder encoding, date handling, field validation, pagination, and nullable fields. |
| `list_emails_from_contact` | [List messages](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0) and [search Outlook messages](https://learn.microsoft.com/en-us/graph/search-concept-messages) | Replaced the invalid `$filter` plus `$orderby` combination with documented `$search` syntax; added folder encoding and pagination. |
| `mark_email_read` | [Update message](https://learn.microsoft.com/en-us/graph/api/message-update?view=graph-rest-1.0) | Fixed message ID encoding and response validation. |
| `list_mail_folders` | [List mail folders](https://learn.microsoft.com/en-us/graph/api/user-list-mailfolders?view=graph-rest-1.0) and [list child folders](https://learn.microsoft.com/en-us/graph/api/mailfolder-list-childfolders?view=graph-rest-1.0) | Fixed pagination at every level, ID encoding, cycle protection, and error propagation. |
| `get_mail_folder` | [Get mail folder](https://learn.microsoft.com/en-us/graph/api/mailfolder-get?view=graph-rest-1.0) | Fixed folder ID encoding and response validation. |
| `move_email` | [Move message](https://learn.microsoft.com/en-us/graph/api/message-move?view=graph-rest-1.0) | Fixed message ID encoding, response validation, and required output fields. |
| `read_email` | [Get message](https://learn.microsoft.com/en-us/graph/api/message-get?view=graph-rest-1.0) and [list attachments](https://learn.microsoft.com/en-us/graph/api/message-list-attachments?view=graph-rest-1.0) | Fixed message ID encoding, response validation, and attachment pagination. |
| `read_contacts` | [List contacts](https://learn.microsoft.com/en-us/graph/api/user-list-contacts?view=graph-rest-1.0) | Fixed pagination, limit handling, and nullable contact fields. |
| `search_onedrive_files` | [Search drive items](https://learn.microsoft.com/en-us/graph/api/driveitem-search?view=graph-rest-1.0) | Fixed OData string escaping, URL encoding, response validation, and pagination. |
| `read_onedrive_file_content` | [Download contents](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0), [convert contents](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content-format?view=graph-rest-1.0), and [drive item resource](https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0) | Fixed MIME lookup to `file.mimeType`, documented conversion detection, `.pdf` output naming, ID encoding, and failure-on-empty behavior. |
| `create_draft_email` | [Create message](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0) | Verified payload and fixed response/error validation plus required outputs. |
| `send_draft_email` | [Send message](https://learn.microsoft.com/en-us/graph/api/message-send?view=graph-rest-1.0) | Fixed ID encoding and public output requirements. |
| `reply_to_email` | [Reply to message](https://learn.microsoft.com/en-us/graph/api/message-reply?view=graph-rest-1.0) | Fixed ID encoding and always supplies the required `comment` property, including an empty string. |
| `forward_email` | [Forward message](https://learn.microsoft.com/en-us/graph/api/message-forward?view=graph-rest-1.0) | Fixed ID encoding and public output requirements. |
| `download_email_attachment` | [Get attachment](https://learn.microsoft.com/en-us/graph/api/attachment-get?view=graph-rest-1.0) | Fixed ID encoding, raw `$value` download, `contentBytes` fallback, metadata-only behavior, and failure-on-empty behavior. |
| `search_emails` | [Microsoft Search API for Outlook messages](https://learn.microsoft.com/en-us/graph/search-concept-messages) | Fixed explicit result fields, nullable senders, and error/response validation. |
| `search_sharepoint_sites` | [Search for sites](https://learn.microsoft.com/en-us/graph/api/site-search?view=graph-rest-1.0) | Fixed pagination, caller limit, response validation, and nullable fields. |
| `get_sharepoint_site_details` | [Get site](https://learn.microsoft.com/en-us/graph/api/site-get?view=graph-rest-1.0) | Fixed site ID encoding and response validation. |
| `list_sharepoint_libraries` | [List drives](https://learn.microsoft.com/en-us/graph/api/drive-list?view=graph-rest-1.0) | Fixed pagination, caller limit, safe `$select` validation, and mandatory output fields. |
| `search_sharepoint_documents` | [List drives](https://learn.microsoft.com/en-us/graph/api/drive-list?view=graph-rest-1.0) and [search drive items](https://learn.microsoft.com/en-us/graph/api/driveitem-search?view=graph-rest-1.0) | Fixed multi-drive pagination, query and drive ID encoding, result limiting, and partial-error reporting. |
| `read_sharepoint_document` | [Download contents](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0) and [convert contents](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content-format?view=graph-rest-1.0) | Fixed site/drive/item ID encoding, nested MIME lookup, conversion naming, and failure-on-empty behavior. |
| `list_sharepoint_pages` | [List site pages](https://learn.microsoft.com/en-us/graph/api/sitepage-list?view=graph-rest-1.0) | Fixed pagination, limit, supported sort/select validation, and mandatory output fields. |
| `read_sharepoint_page_content` | [Get site page](https://learn.microsoft.com/en-us/graph/api/sitepage-get?view=graph-rest-1.0) | Fixed site/page ID encoding and response validation. |
| `list_sharepoint_subsites` | [List subsites](https://learn.microsoft.com/en-us/graph/api/site-list-subsites?view=graph-rest-1.0) | Fixed pagination, ID encoding, response validation, and `has_more`. |
| `list_sharepoint_folder_contents` | [List drive item children](https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0) | Fixed drive/folder ID encoding, pagination, response validation, and `has_more`. |
| `find_meeting_times` | [Find meeting times](https://learn.microsoft.com/en-us/graph/api/user-findmeetingtimes?view=graph-rest-1.0) | Fixed `timeSlots` casing, `activityDomain`, suggestion reasons, UTC ranges, validation, response handling, and the delegated `Calendars.Read.Shared` permission. |
| `get_schedule` | [Get schedule](https://learn.microsoft.com/en-us/graph/api/calendar-getschedule?view=graph-rest-1.0) | Fixed UTC normalization, date-range validation, documented 5–1440 minute interval validation, and response handling. |
| `list_rooms` | [List places](https://learn.microsoft.com/en-us/graph/api/place-list?view=graph-rest-1.0) | Fixed room-list email encoding, input validation, pagination, and response validation. |
| `check_room_availability` | [Get schedule](https://learn.microsoft.com/en-us/graph/api/calendar-getschedule?view=graph-rest-1.0) | Fixed UTC normalization, date-range validation, and response handling. |

## Authorization change

`Schedule.Read.All` was removed because it is a Microsoft Teams Shifts permission and does not authorize Outlook free/busy APIs. `Calendars.Read.Shared` was added because Microsoft documents it as the least-privileged delegated permission for `findMeetingTimes`. `Calendars.ReadWrite` remains in place for event management and `getSchedule`; `Place.Read.All` remains in place for room discovery.

Because OAuth permissions changed, users upgrading from an earlier version must reconnect Microsoft 365 once after deployment.
