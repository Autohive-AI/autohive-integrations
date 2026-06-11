from autohive_integrations_sdk import (
    Integration,
    ExecutionContext,
    ActionHandler,
    ActionResult,
    ActionError,
)
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
import base64
import urllib.parse
import aiohttp

# Create the integration using the config.json
microsoft365 = Integration.load()

# Microsoft Graph API Base URL
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


def _check_response(response: Any, *required_keys: str) -> None:
    """Raise a descriptive exception if the Graph API returned an error response."""
    if not isinstance(response, dict):
        raise ValueError(f"Unexpected response type: {type(response)}")
    if "error" in response:
        err = response["error"]
        raise ValueError(err.get("message") or str(err))
    for key in required_keys:
        if key not in response:
            raise KeyError(f"Expected key '{key}' missing from response: {list(response.keys())}")


async def _fetch_binary(url: str, token: str) -> bytes:
    """Fetch a binary /content endpoint directly, bypassing SDK text decoding."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"Authorization": f"Bearer {token}"}) as resp:
            if not resp.ok:
                text = await resp.text()
                raise ValueError(f"HTTP {resp.status}: {text}")
            return await resp.read()


# ---- Action Handlers ----


@microsoft365.action("send_email")
class SendEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            message = {
                "subject": inputs["subject"],
                "body": {
                    "contentType": inputs.get("body_type", "Text"),
                    "content": inputs["body"],
                },
                "toRecipients": [{"emailAddress": {"address": inputs["to"]}}],
            }

            if inputs.get("cc"):
                message["ccRecipients"] = [{"emailAddress": {"address": email}} for email in inputs["cc"]]

            if inputs.get("bcc"):
                message["bccRecipients"] = [{"emailAddress": {"address": email}} for email in inputs["bcc"]]

            email_data = {"message": message, "saveToSentItems": True}

            await context.fetch(f"{GRAPH_API_BASE}/me/sendMail", method="POST", json=email_data)

            return ActionResult(data={"sent": True}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("create_calendar_event")
class CreateCalendarEventAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            event_data = {
                "subject": inputs["subject"],
                "start": {"dateTime": inputs["start_time"], "timeZone": "UTC"},
                "end": {"dateTime": inputs["end_time"], "timeZone": "UTC"},
            }

            if inputs.get("location"):
                event_data["location"] = {"displayName": inputs["location"]}

            if inputs.get("body"):
                event_data["body"] = {"contentType": "Text", "content": inputs["body"]}

            if inputs.get("attendees"):
                event_data["attendees"] = [
                    {
                        "emailAddress": {"address": email, "name": email},
                        "type": "required",
                    }
                    for email in inputs["attendees"]
                ]

            resp = await context.fetch(f"{GRAPH_API_BASE}/me/events", method="POST", json=event_data)
            response = resp.data
            _check_response(response, "id", "webLink")

            return ActionResult(
                data={
                    "id": response["id"],
                    "webLink": response["webLink"],
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("upload_file")
class UploadFileAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            filename = inputs["filename"]
            content = inputs["content"]
            content_type = inputs.get("content_type", "text/plain")
            folder_path = inputs.get("folder_path", "/").strip("/")

            file_content = content.encode("utf-8")

            if folder_path:
                upload_url = f"{GRAPH_API_BASE}/me/drive/root:/{folder_path}/{filename}:/content"
            else:
                upload_url = f"{GRAPH_API_BASE}/me/drive/root:/{filename}:/content"

            resp = await context.fetch(
                upload_url,
                method="PUT",
                data=file_content,
                headers={"Content-Type": content_type},
            )
            response = resp.data
            _check_response(response, "id")

            return ActionResult(
                data={
                    "id": response["id"],
                    "webUrl": response.get("webUrl", ""),
                    "size": response.get("size", 0),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("list_files")
class ListFilesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            folder_path = inputs.get("folder_path", "/").strip("/")
            limit = inputs.get("limit", 100)

            if folder_path:
                api_url = f"{GRAPH_API_BASE}/me/drive/root:/{folder_path}:/children"
            else:
                api_url = f"{GRAPH_API_BASE}/me/drive/root/children"

            params = {
                "$top": limit,
                "$select": "id,name,size,lastModifiedDateTime,webUrl,folder",
            }

            resp = await context.fetch(api_url, params=params)
            response = resp.data

            files = []
            for item in response.get("value", []):
                file_item = {
                    "id": item["id"],
                    "name": item["name"],
                    "size": item.get("size", 0),
                    "lastModifiedDateTime": item["lastModifiedDateTime"],
                    "webUrl": item["webUrl"],
                }
                if "folder" in item:
                    file_item["folder"] = item["folder"]
                files.append(file_item)

            return ActionResult(data={"files": files}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("update_calendar_event")
class UpdateCalendarEventAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            event_id = inputs["event_id"]

            event_data = {}

            if inputs.get("subject"):
                event_data["subject"] = inputs["subject"]

            if inputs.get("start_time"):
                event_data["start"] = {
                    "dateTime": inputs["start_time"],
                    "timeZone": "UTC",
                }

            if inputs.get("end_time"):
                event_data["end"] = {"dateTime": inputs["end_time"], "timeZone": "UTC"}

            if inputs.get("location"):
                event_data["location"] = {"displayName": inputs["location"]}

            if inputs.get("body"):
                event_data["body"] = {"contentType": "Text", "content": inputs["body"]}

            if inputs.get("attendees"):
                event_data["attendees"] = [
                    {
                        "emailAddress": {"address": email, "name": email},
                        "type": "required",
                    }
                    for email in inputs["attendees"]
                ]

            resp = await context.fetch(
                f"{GRAPH_API_BASE}/me/events/{event_id}",
                method="PATCH",
                json=event_data,
            )
            response = resp.data
            _check_response(response, "id")

            return ActionResult(
                data={
                    "id": response["id"],
                    "webLink": response.get("webLink", ""),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("list_calendar_events")
class ListCalendarEventsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            if inputs.get("start_datetime"):
                start_datetime = inputs.get("start_datetime")
                end_datetime = inputs.get("end_datetime", start_datetime)
            elif inputs.get("start_date"):
                start_date = inputs.get("start_date")
                end_date = inputs.get("end_date", start_date)
                start_datetime = f"{start_date}T00:00:00Z"
                end_datetime = f"{end_date}T23:59:59Z"
            else:
                now = datetime.now(timezone.utc)
                end_time = now + timedelta(days=30)
                start_datetime = now.strftime("%Y-%m-%dT%H:%M:%SZ")
                end_datetime = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            limit = inputs.get("limit", 100)

            params = {
                "$top": limit,
                "$orderby": "start/dateTime",
                "$select": "id,subject,start,end,location,bodyPreview,organizer,attendees,webLink,isAllDay",
            }

            api_url = f"{GRAPH_API_BASE}/me/calendarView?startDateTime={start_datetime}&endDateTime={end_datetime}"

            resp = await context.fetch(api_url, params=params)
            response = resp.data

            events = []
            for event in response.get("value", []):
                attendees = []
                for attendee in event.get("attendees", []):
                    attendees.append(
                        {
                            "email": attendee["emailAddress"]["address"],
                            "name": attendee["emailAddress"]["name"],
                            "response_status": attendee["status"]["response"],
                        }
                    )

                organizer_email = ""
                if event.get("organizer") and event["organizer"].get("emailAddress"):
                    organizer_email = event["organizer"]["emailAddress"]["address"]

                events.append(
                    {
                        "id": event["id"],
                        "subject": event.get("subject") or "",
                        "start": event["start"],
                        "end": event["end"],
                        "location": event.get("location", {}).get("displayName") or "",
                        "bodyPreview": event.get("bodyPreview") or "",
                        "organizer": organizer_email,
                        "attendees": attendees,
                        "webLink": event["webLink"],
                        "isAllDay": event.get("isAllDay", False),
                    }
                )

            return ActionResult(data={"events": events}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("list_emails")
class ListEmailsAction(ActionHandler):
    _ALLOWED_FIELDS = {
        "id",
        "subject",
        "sender",
        "receivedDateTime",
        "bodyPreview",
        "body",
        "hasAttachments",
        "isRead",
        "importance",
    }

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            if inputs.get("start_datetime"):
                start_datetime = inputs.get("start_datetime")
                end_datetime = inputs.get("end_datetime", start_datetime)
            elif inputs.get("start_date"):
                start_date = inputs.get("start_date")
                end_date = inputs.get("end_date", start_date)
                start_datetime = f"{start_date}T00:00:00Z"
                end_datetime = f"{end_date}T23:59:59Z"
            else:
                now = datetime.now(timezone.utc)
                start_time = now - timedelta(days=1)
                start_datetime = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                end_datetime = now.strftime("%Y-%m-%dT%H:%M:%SZ")

            folder = inputs.get("folder", "Inbox")
            limit = inputs.get("limit", 50)

            requested_fields = inputs.get("fields")
            if requested_fields:
                active_fields = {f for f in requested_fields if f in self._ALLOWED_FIELDS}
                active_fields.add("id")
            else:
                active_fields = self._ALLOWED_FIELDS

            params = {
                "$top": limit,
                "$orderby": "receivedDateTime desc",
                "$select": ",".join(sorted(active_fields)),
                "$filter": f"receivedDateTime ge {start_datetime} and receivedDateTime le {end_datetime}",
            }

            api_url = f"{GRAPH_API_BASE}/me/mailFolders/{folder}/messages"
            resp = await context.fetch(api_url, params=params)
            response = resp.data

            emails = []
            for email in response.get("value", []):
                email_data: Dict[str, Any] = {"id": email["id"]}
                if "subject" in active_fields:
                    email_data["subject"] = email.get("subject") or ""
                if "sender" in active_fields:
                    email_data["sender"] = email["sender"]
                if "receivedDateTime" in active_fields:
                    email_data["receivedDateTime"] = email["receivedDateTime"]
                if "bodyPreview" in active_fields:
                    email_data["bodyPreview"] = email.get("bodyPreview") or ""
                if "body" in active_fields:
                    email_data["body"] = email.get("body", {})
                if "hasAttachments" in active_fields:
                    email_data["hasAttachments"] = email.get("hasAttachments", False)
                if "isRead" in active_fields:
                    email_data["isRead"] = email.get("isRead", False)
                if "importance" in active_fields:
                    email_data["importance"] = email.get("importance", "normal")
                emails.append(email_data)

            return ActionResult(data={"emails": emails}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("list_emails_from_contact")
class ListEmailsFromContactAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            contact_email = inputs["contact_email"]
            limit = inputs.get("limit", 5)
            folder = inputs.get("folder", "Inbox")

            params = {
                "$top": limit,
                "$orderby": "receivedDateTime desc",
                "$select": "id,subject,sender,receivedDateTime,bodyPreview,body,hasAttachments,isRead,importance",
            }

            api_url = f"{GRAPH_API_BASE}/me/mailFolders/{folder}/messages"
            resp = await context.fetch(api_url, params=params)
            response = resp.data

            emails = []
            for email in response.get("value", []):
                emails.append(
                    {
                        "id": email["id"],
                        "subject": email.get("subject") or "",
                        "sender": email["sender"],
                        "receivedDateTime": email["receivedDateTime"],
                        "bodyPreview": email.get("bodyPreview") or "",
                        "body": email.get("body", {}),
                        "hasAttachments": email.get("hasAttachments", False),
                        "isRead": email.get("isRead", False),
                        "importance": email.get("importance", "normal"),
                    }
                )

            return ActionResult(
                data={"emails": emails, "contact_email": contact_email},
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("mark_email_read")
class MarkEmailReadAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            email_id = inputs["email_id"]
            is_read = inputs["is_read"]

            update_data = {"isRead": is_read}

            resp = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{email_id}",
                method="PATCH",
                json=update_data,
            )
            response = resp.data
            _check_response(response, "id")

            return ActionResult(
                data={
                    "id": response["id"],
                    "isRead": response.get("isRead", is_read),
                    "lastModifiedDateTime": response.get("lastModifiedDateTime", ""),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("list_mail_folders")
class ListMailFoldersAction(ActionHandler):
    """List mail folders in the user's mailbox.

    Returns root-level folders by default. Use include_hidden to show hidden folders.
    Use include_children to recursively fetch all nested folders.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            include_hidden = inputs.get("include_hidden", False)
            include_children = inputs.get("include_children", False)
            folder_id = inputs.get("folder_id")

            if folder_id:
                api_url = f"{GRAPH_API_BASE}/me/mailFolders/{folder_id}/childFolders"
            else:
                api_url = f"{GRAPH_API_BASE}/me/mailFolders"

            params = {
                "$select": "id,displayName,parentFolderId,childFolderCount,unreadItemCount,totalItemCount,isHidden"
            }

            if include_hidden:
                params["includeHiddenFolders"] = "true"

            all_folder_items = []
            next_url = api_url
            is_first_request = True

            while next_url:
                if is_first_request:
                    resp = await context.fetch(next_url, params=params)
                    is_first_request = False
                else:
                    resp = await context.fetch(next_url)
                response = resp.data
                all_folder_items.extend(response.get("value", []))
                next_url = response.get("@odata.nextLink")

            folders = []
            for folder in all_folder_items:
                folder_data = {
                    "id": folder["id"],
                    "displayName": folder.get("displayName", ""),
                    "parentFolderId": folder.get("parentFolderId", ""),
                    "childFolderCount": folder.get("childFolderCount", 0),
                    "unreadItemCount": folder.get("unreadItemCount", 0),
                    "totalItemCount": folder.get("totalItemCount", 0),
                    "isHidden": folder.get("isHidden", False),
                }
                folders.append(folder_data)

                if include_children and folder.get("childFolderCount", 0) > 0:
                    child_folders = await self._fetch_child_folders_recursive(folder["id"], context, include_hidden)
                    folders.extend(child_folders)

            return ActionResult(
                data={"folders": folders, "total_count": len(folders)},
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))

    async def _fetch_child_folders_recursive(
        self, parent_folder_id: str, context: ExecutionContext, include_hidden: bool
    ) -> List[Dict[str, Any]]:
        """Recursively fetch all child folders under a parent folder."""
        try:
            api_url = f"{GRAPH_API_BASE}/me/mailFolders/{parent_folder_id}/childFolders"
            params = {
                "$select": "id,displayName,parentFolderId,childFolderCount,unreadItemCount,totalItemCount,isHidden"
            }
            if include_hidden:
                params["includeHiddenFolders"] = "true"

            all_folder_items = []
            next_url = api_url
            is_first_request = True

            while next_url:
                if is_first_request:
                    resp = await context.fetch(next_url, params=params)
                    is_first_request = False
                else:
                    resp = await context.fetch(next_url)
                response = resp.data
                all_folder_items.extend(response.get("value", []))
                next_url = response.get("@odata.nextLink")

            folders = []
            for folder in all_folder_items:
                folder_data = {
                    "id": folder["id"],
                    "displayName": folder.get("displayName", ""),
                    "parentFolderId": folder.get("parentFolderId", ""),
                    "childFolderCount": folder.get("childFolderCount", 0),
                    "unreadItemCount": folder.get("unreadItemCount", 0),
                    "totalItemCount": folder.get("totalItemCount", 0),
                    "isHidden": folder.get("isHidden", False),
                }
                folders.append(folder_data)

                if folder.get("childFolderCount", 0) > 0:
                    child_folders = await self._fetch_child_folders_recursive(folder["id"], context, include_hidden)
                    folders.extend(child_folders)

            return folders
        except Exception:
            return []


@microsoft365.action("get_mail_folder")
class GetMailFolderAction(ActionHandler):
    """Get a specific mail folder by ID or well-known name.

    Well-known folder names: inbox, drafts, sentitems, deleteditems, junkemail,
    archive, outbox, clutter, scheduled, searchfolders, conversationhistory
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            folder_id = inputs["folder_id"]

            api_url = f"{GRAPH_API_BASE}/me/mailFolders/{folder_id}"

            params = {
                "$select": "id,displayName,parentFolderId,childFolderCount,unreadItemCount,totalItemCount,isHidden"
            }

            resp = await context.fetch(api_url, params=params)
            response = resp.data

            folder_data = {
                "id": response["id"],
                "displayName": response.get("displayName", ""),
                "parentFolderId": response.get("parentFolderId", ""),
                "childFolderCount": response.get("childFolderCount", 0),
                "unreadItemCount": response.get("unreadItemCount", 0),
                "totalItemCount": response.get("totalItemCount", 0),
                "isHidden": response.get("isHidden", False),
            }

            return ActionResult(data={"folder": folder_data}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("move_email")
class MoveEmailAction(ActionHandler):
    """Move an email to a different folder.

    The destination_folder_id must be either:
    1. A folder ID (e.g., 'AQMkADYAAAIBXQAAAA==') obtained from list_mail_folders
    2. A well-known folder name (lowercase, no spaces): inbox, drafts, sentitems,
       deleteditems, junkemail, archive, outbox, clutter, scheduled

    For custom folders, use list_mail_folders with include_children=true to find the folder ID.
    """

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            email_id = inputs["email_id"]
            destination_folder_id = inputs["destination_folder_id"]

            move_data = {"destinationId": destination_folder_id}

            resp = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{email_id}/move",
                method="POST",
                json=move_data,
            )
            response = resp.data
            _check_response(response, "id")

            return ActionResult(
                data={
                    "id": response["id"],
                    "parentFolderId": response.get("parentFolderId", ""),
                    "subject": response.get("subject", ""),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("read_email")
class ReadEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            email_id = inputs["email_id"]
            include_attachments = inputs.get("include_attachments", True)

            resp = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{email_id}",
                params={"$select": "id,subject,sender,receivedDateTime,body,hasAttachments"},
            )
            email_response = resp.data
            _check_response(email_response, "id")

            email_details = {
                "id": email_response["id"],
                "subject": email_response.get("subject") or "",
                "sender": email_response.get("sender", {}),
                "receivedDateTime": email_response.get("receivedDateTime", ""),
                "body": email_response.get("body", {}),
                "hasAttachments": email_response.get("hasAttachments", False),
            }

            attachments = []

            if include_attachments and email_details["hasAttachments"]:
                resp2 = await context.fetch(f"{GRAPH_API_BASE}/me/messages/{email_id}/attachments")
                attachments_response = resp2.data

                for attachment in attachments_response.get("value", []):
                    attachments.append(
                        {
                            "id": attachment["id"],
                            "name": attachment["name"],
                            "size": attachment.get("size", 0),
                            "contentType": attachment.get("contentType", "application/octet-stream"),
                            "message": "Attachment metadata only. Content extraction not supported for this file type.",
                        }
                    )

            return ActionResult(
                data={
                    "email": email_details,
                    "attachments": attachments,
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("read_contacts")
class ReadContactsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            limit = inputs.get("limit", 100)
            search = inputs.get("search")

            api_url = f"{GRAPH_API_BASE}/me/contacts"

            params = {
                "$top": limit,
                "$select": (
                    "id,displayName,givenName,surname,emailAddresses,"
                    "businessPhones,homePhones,mobilePhone,companyName,jobTitle"
                ),
            }

            resp = await context.fetch(api_url, params=params)
            response = resp.data

            all_contacts = response.get("value", [])
            contacts = []

            for contact in all_contacts:
                if search:
                    search_lower = search.lower()
                    display_name = contact.get("displayName", "").lower()
                    given_name = contact.get("givenName", "").lower()
                    surname = contact.get("surname", "").lower()
                    company = contact.get("companyName", "").lower()

                    if not (
                        search_lower in display_name
                        or search_lower in given_name
                        or search_lower in surname
                        or search_lower in company
                    ):
                        continue

                email_addresses = []
                for email in contact.get("emailAddresses", []):
                    email_addresses.append(
                        {
                            "address": email.get("address", ""),
                            "name": email.get("name", ""),
                        }
                    )

                phone_numbers = []

                for phone in contact.get("businessPhones", []):
                    phone_numbers.append({"number": phone, "type": "business"})

                for phone in contact.get("homePhones", []):
                    phone_numbers.append({"number": phone, "type": "home"})

                mobile = contact.get("mobilePhone")
                if mobile:
                    phone_numbers.append({"number": mobile, "type": "mobile"})

                contacts.append(
                    {
                        "id": contact.get("id", ""),
                        "displayName": contact.get("displayName", ""),
                        "givenName": contact.get("givenName", ""),
                        "surname": contact.get("surname", ""),
                        "emailAddresses": email_addresses,
                        "businessPhones": contact.get("businessPhones", []),
                        "homePhones": contact.get("homePhones", []),
                        "mobilePhone": contact.get("mobilePhone", ""),
                        "companyName": contact.get("companyName", ""),
                        "jobTitle": contact.get("jobTitle", ""),
                    }
                )

            if search:
                if contacts:
                    message = f"Found {len(contacts)} contact(s) matching '{search}'"
                else:
                    message = f"No contacts found matching '{search}'"

                return ActionResult(
                    data={
                        "contacts": contacts,
                        "message": message,
                        "search_term": search,
                        "total_searched": len(all_contacts),
                    },
                    cost_usd=0.0,
                )
            else:
                return ActionResult(
                    data={
                        "contacts": contacts,
                        "message": f"Retrieved {len(contacts)} contacts",
                        "total_contacts": len(contacts),
                    },
                    cost_usd=0.0,
                )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("search_onedrive_files")
class SearchOneDriveFilesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            search_query = inputs["query"]
            limit = inputs.get("limit", 10)

            encoded_query = urllib.parse.quote(search_query)

            params = {
                "$top": limit,
                "$select": "id,name,size,lastModifiedDateTime,webUrl,folder,file",
            }

            api_url = f"{GRAPH_API_BASE}/me/drive/root/search(q='{encoded_query}')"
            resp = await context.fetch(api_url, params=params)
            response = resp.data

            files = []
            for item in response.get("value", []):
                file_item = {
                    "id": item["id"],
                    "name": item["name"],
                    "size": item.get("size", 0),
                    "lastModifiedDateTime": item["lastModifiedDateTime"],
                    "webUrl": item["webUrl"],
                }
                if "folder" in item:
                    file_item["folder"] = item["folder"]
                if "file" in item:
                    file_item["file"] = item["file"]
                files.append(file_item)

            return ActionResult(
                data={"files": files, "query": search_query},
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("read_onedrive_file_content")
class ReadOneDriveFileContentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            file_id = inputs["file_id"]

            metadata_params = {"$select": "id,name,size,mimeType,file,webUrl"}
            resp = await context.fetch(f"{GRAPH_API_BASE}/me/drive/items/{file_id}", params=metadata_params)
            metadata_response = resp.data
            _check_response(metadata_response, "id", "name")

            file_name = metadata_response["name"]
            file_size = metadata_response.get("size", 0)
            mime_type = metadata_response.get("mimeType", "")
            web_url = metadata_response.get("webUrl", "")

            content = None
            content_type = "application/octet-stream"
            content_available = False
            content_info = ""

            try:
                _token = context.auth.get("credentials", {}).get("access_token", "")
                if any(ext in file_name.lower() for ext in [".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"]):
                    content_url = f"{GRAPH_API_BASE}/me/drive/items/{file_id}/content?format=pdf"
                    content_bytes = await _fetch_binary(content_url, _token)
                    content = base64.b64encode(content_bytes).decode("utf-8")
                    content_type = "application/pdf"
                    content_available = True
                    content_info = "Office document converted to PDF and encoded for LLM processing"
                elif file_name.lower().endswith(".pdf"):
                    content_url = f"{GRAPH_API_BASE}/me/drive/items/{file_id}/content"
                    content_bytes = await _fetch_binary(content_url, _token)
                    content = base64.b64encode(content_bytes).decode("utf-8")
                    content_type = "application/pdf"
                    content_available = True
                    content_info = "PDF content retrieved and encoded for LLM processing"
                else:
                    content_url = f"{GRAPH_API_BASE}/me/drive/items/{file_id}/content"
                    content_bytes = await _fetch_binary(content_url, _token)
                    content = base64.b64encode(content_bytes).decode("utf-8")
                    content_type = mime_type or "text/plain"
                    content_available = True
                    content_info = "Text content retrieved and encoded successfully"

            except Exception as content_error:
                content = None
                content_available = False
                content_info = f"Content retrieval failed: {str(content_error)}"

            if not mime_type:
                if file_name.lower().endswith(".pdf"):
                    mime_type = "application/pdf"
                elif any(ext in file_name.lower() for ext in [".docx", ".doc"]):
                    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif any(ext in file_name.lower() for ext in [".xlsx", ".xls"]):
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif any(ext in file_name.lower() for ext in [".pptx", ".ppt"]):
                    mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                else:
                    mime_type = "application/octet-stream"

            if content_available and content:
                return ActionResult(
                    data={
                        "file": {
                            "content": content,
                            "name": file_name,
                            "contentType": content_type,
                        },
                        "metadata": {
                            "id": file_id,
                            "name": file_name,
                            "size": file_size,
                            "mimeType": mime_type,
                            "webUrl": web_url,
                        },
                    },
                    cost_usd=0.0,
                )
            else:
                fallback_content_type = mime_type
                if file_name.lower().endswith(".pdf"):
                    fallback_content_type = "application/pdf"

                return ActionResult(
                    data={
                        "file": {
                            "content": "",
                            "name": file_name,
                            "contentType": fallback_content_type,
                        },
                        "metadata": {
                            "id": file_id,
                            "name": file_name,
                            "size": file_size,
                            "mimeType": mime_type,
                            "webUrl": web_url,
                        },
                        "content_error": content_info,
                    },
                    cost_usd=0.0,
                )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("create_draft_email")
class CreateDraftEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            message = {
                "subject": inputs["subject"],
                "body": {
                    "contentType": inputs.get("body_type", "Text"),
                    "content": inputs["body"],
                },
                "toRecipients": [],
            }

            for recipient in inputs["to_recipients"]:
                if isinstance(recipient, str):
                    message["toRecipients"].append({"emailAddress": {"address": recipient}})
                else:
                    message["toRecipients"].append(
                        {
                            "emailAddress": {
                                "address": recipient.get("address", recipient.get("email")),
                                "name": recipient.get("name", ""),
                            }
                        }
                    )

            if inputs.get("cc_recipients"):
                message["ccRecipients"] = []
                for recipient in inputs["cc_recipients"]:
                    if isinstance(recipient, str):
                        message["ccRecipients"].append({"emailAddress": {"address": recipient}})
                    else:
                        message["ccRecipients"].append(
                            {
                                "emailAddress": {
                                    "address": recipient.get("address", recipient.get("email")),
                                    "name": recipient.get("name", ""),
                                }
                            }
                        )

            if inputs.get("bcc_recipients"):
                message["bccRecipients"] = []
                for recipient in inputs["bcc_recipients"]:
                    if isinstance(recipient, str):
                        message["bccRecipients"].append({"emailAddress": {"address": recipient}})
                    else:
                        message["bccRecipients"].append(
                            {
                                "emailAddress": {
                                    "address": recipient.get("address", recipient.get("email")),
                                    "name": recipient.get("name", ""),
                                }
                            }
                        )

            if inputs.get("importance"):
                message["importance"] = inputs["importance"]

            resp = await context.fetch(f"{GRAPH_API_BASE}/me/messages", method="POST", json=message)
            response = resp.data

            draft_id = response.get("id") if isinstance(response, dict) else None
            if not draft_id:
                error = response.get("error", {}) if isinstance(response, dict) else {}
                msg = error.get("message") or f"Unexpected response: {response}"
                return ActionError(message=msg)

            return ActionResult(
                data={
                    "draft_id": draft_id,
                    "subject": response.get("subject") or "",
                    "created_datetime": response.get("createdDateTime") or "",
                    "is_draft": response.get("isDraft", True),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("send_draft_email")
class SendDraftEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            draft_id = inputs["draft_id"]

            await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{draft_id}/send",
                method="POST",
                headers={"Content-Length": "0"},
            )

            return ActionResult(
                data={"sent": True, "draft_id": draft_id},
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("reply_to_email")
class ReplyToEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            message_id = inputs["message_id"]

            reply_data = {}
            if inputs.get("comment"):
                reply_data["comment"] = inputs["comment"]

            await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{message_id}/reply",
                method="POST",
                json=reply_data,
            )

            return ActionResult(
                data={
                    "sent": True,
                    "message_id": message_id,
                    "operation": "reply",
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("forward_email")
class ForwardEmailAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            message_id = inputs["message_id"]

            forward_data = {"toRecipients": []}

            for recipient in inputs["to_recipients"]:
                if isinstance(recipient, str):
                    forward_data["toRecipients"].append({"emailAddress": {"address": recipient}})
                else:
                    forward_data["toRecipients"].append(
                        {
                            "emailAddress": {
                                "address": recipient.get("address", recipient.get("email")),
                                "name": recipient.get("name", ""),
                            }
                        }
                    )

            if inputs.get("comment"):
                forward_data["comment"] = inputs["comment"]

            await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{message_id}/forward",
                method="POST",
                json=forward_data,
            )

            return ActionResult(
                data={
                    "sent": True,
                    "message_id": message_id,
                    "operation": "forward",
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("download_email_attachment")
class DownloadEmailAttachmentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            message_id = inputs["message_id"]
            attachment_id = inputs["attachment_id"]
            include_content = inputs.get("include_content", True)

            resp = await context.fetch(
                f"{GRAPH_API_BASE}/me/messages/{message_id}/attachments/{attachment_id}",
                method="GET",
            )
            attachment_response = resp.data
            _check_response(attachment_response, "id")

            attachment_id_val = attachment_response["id"]
            attachment_name = attachment_response.get("name") or ""
            content_type = attachment_response.get("contentType") or "application/octet-stream"
            size = attachment_response.get("size", 0)
            is_inline = attachment_response.get("isInline", False)

            content = ""
            content_available = False
            content_error_msg = None

            if include_content:
                try:
                    content_url = f"{GRAPH_API_BASE}/me/messages/{message_id}/attachments/{attachment_id}/$value"
                    _token = context.auth.get("credentials", {}).get("access_token", "")
                    content_bytes = await _fetch_binary(content_url, _token)
                    content = base64.b64encode(content_bytes).decode("utf-8")
                    content_available = True

                except Exception as content_error:
                    if "contentBytes" in attachment_response:
                        content = attachment_response["contentBytes"]
                        content_available = True
                    else:
                        content = ""
                        content_available = False
                        content_error_msg = f"Content retrieval failed: {str(content_error)}"

            if content_available and content:
                return ActionResult(
                    data={
                        "file": {
                            "content": content,
                            "name": attachment_name,
                            "contentType": content_type,
                        },
                        "metadata": {
                            "id": attachment_id_val,
                            "name": attachment_name,
                            "size": size,
                            "contentType": content_type,
                            "message_id": message_id,
                            "is_inline": is_inline,
                        },
                    },
                    cost_usd=0.0,
                )
            else:
                return ActionResult(
                    data={
                        "file": {
                            "content": "",
                            "name": attachment_name,
                            "contentType": content_type,
                        },
                        "metadata": {
                            "id": attachment_id_val,
                            "name": attachment_name,
                            "size": size,
                            "contentType": content_type,
                            "message_id": message_id,
                            "is_inline": is_inline,
                        },
                        "content_error": content_error_msg or "Content not available",
                    },
                    cost_usd=0.0,
                )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("search_emails")
class SearchEmailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            query = inputs["query"]
            limit = inputs.get("limit", 25)
            enable_top_results = inputs.get("enable_top_results", False)

            search_request = {
                "entityTypes": ["message"],
                "query": {"queryString": query},
                "from": 0,
                "size": min(limit, 1000),
            }

            if enable_top_results:
                search_request["enableTopResults"] = True

            resp = await context.fetch(
                "https://graph.microsoft.com/v1.0/search/query",
                method="POST",
                json={"requests": [search_request]},
            )
            response = resp.data

            messages = []
            total_results = 0

            if response.get("value") and len(response["value"]) > 0:
                search_result = response["value"][0]
                hits = search_result.get("hitsContainers", [])

                if hits:
                    hits_container = hits[0]
                    total_results = hits_container.get("total", 0)

                    for hit in hits_container.get("hits", []):
                        message_data = hit.get("resource", {})

                        sender = {}
                        if message_data.get("from"):
                            sender = {
                                "emailAddress": message_data["from"].get("emailAddress", {}),
                                "name": message_data["from"].get("emailAddress", {}).get("name", ""),
                            }

                        messages.append(
                            {
                                "message_id": message_data.get("id") or "",
                                "subject": message_data.get("subject") or "",
                                "sender": sender,
                                "received_datetime": message_data.get("receivedDateTime") or "",
                                "body_preview": message_data.get("bodyPreview") or "",
                                "has_attachments": message_data.get("hasAttachments", False),
                            }
                        )

            return ActionResult(
                data={
                    "query": query,
                    "total_results": total_results,
                    "messages": messages,
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("search_sharepoint_sites")
class SearchSharePointSitesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            search_query = inputs["query"]

            params = {"search": search_query}

            if inputs.get("order_by_created"):
                params["$orderby"] = "createdDateTime desc"

            resp = await context.fetch(f"{GRAPH_API_BASE}/sites", params=params)
            response = resp.data

            sites = []
            for site in response.get("value", []):
                sites.append(
                    {
                        "id": site.get("id") or "",
                        "name": site.get("name") or "",
                        "display_name": site.get("displayName") or "",
                        "description": site.get("description") or "",
                        "web_url": site.get("webUrl") or "",
                        "created_datetime": site.get("createdDateTime") or "",
                        "last_modified_datetime": site.get("lastModifiedDateTime") or "",
                    }
                )

            return ActionResult(
                data={
                    "query": search_query,
                    "sites": sites,
                    "total_sites": len(sites),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("get_sharepoint_site_details")
class GetSharePointSiteDetailsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]

            resp = await context.fetch(f"{GRAPH_API_BASE}/sites/{site_id}")
            response = resp.data

            site_details = {
                "id": response.get("id") or "",
                "display_name": response.get("displayName") or "",
                "name": response.get("name") or "",
                "description": response.get("description") or "",
                "web_url": response.get("webUrl") or "",
                "created_datetime": response.get("createdDateTime") or "",
                "last_modified_datetime": response.get("lastModifiedDateTime") or "",
                "is_personal_site": response.get("isPersonalSite", False),
            }

            if "siteCollection" in response:
                site_details["site_collection"] = response["siteCollection"]

            return ActionResult(data={"site": site_details}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("list_sharepoint_libraries")
class ListSharePointLibrariesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]

            params = {}
            if inputs.get("limit"):
                params["$top"] = inputs["limit"]
            if inputs.get("select_fields"):
                valid_drive_fields = {
                    "id",
                    "name",
                    "description",
                    "driveType",
                    "webUrl",
                    "createdDateTime",
                    "lastModifiedDateTime",
                    "createdBy",
                    "lastModifiedBy",
                    "owner",
                    "quota",
                    "sharepointIds",
                    "system",
                }
                requested_fields = [f.strip() for f in inputs["select_fields"].split(",")]
                valid_fields = [f for f in requested_fields if f in valid_drive_fields]

                if valid_fields:
                    params["$select"] = ",".join(valid_fields)

            resp = await context.fetch(f"{GRAPH_API_BASE}/sites/{site_id}/drives", params=params)
            response = resp.data

            libraries = []
            for drive in response.get("value", []):
                library_data = {
                    "id": drive.get("id", ""),
                    "name": drive.get("name", ""),
                    "description": drive.get("description", ""),
                    "drive_type": drive.get("driveType", ""),
                    "web_url": drive.get("webUrl", ""),
                    "created_datetime": drive.get("createdDateTime", ""),
                    "last_modified_datetime": drive.get("lastModifiedDateTime", ""),
                }

                if "quota" in drive:
                    library_data["quota"] = {
                        "total": drive["quota"].get("total", 0),
                        "remaining": drive["quota"].get("remaining", 0),
                        "used": drive["quota"].get("used", 0),
                        "deleted": drive["quota"].get("deleted", 0),
                        "state": drive["quota"].get("state", ""),
                    }

                if "owner" in drive and "user" in drive["owner"]:
                    library_data["owner"] = {
                        "display_name": drive["owner"]["user"].get("displayName", ""),
                        "email": drive["owner"]["user"].get("email", ""),
                    }

                libraries.append(library_data)

            return ActionResult(
                data={
                    "site_id": site_id,
                    "libraries": libraries,
                    "total_libraries": len(libraries),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("search_sharepoint_documents")
class SearchSharePointDocumentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]
            search_query = inputs["query"]
            limit = inputs.get("limit", 10)

            resp = await context.fetch(f"{GRAPH_API_BASE}/sites/{site_id}/drives")
            drives_response = resp.data

            drives = drives_response.get("value", [])
            if not drives:
                return ActionResult(
                    data={
                        "site_id": site_id,
                        "query": search_query,
                        "files": [],
                        "total_files": 0,
                        "drives_searched": 0,
                        "message": "No document libraries found in this site",
                    },
                    cost_usd=0.0,
                )

            encoded_query = urllib.parse.quote(search_query)
            all_files = []
            drives_searched = 0
            search_errors = []

            for drive in drives:
                try:
                    drive_id = drive["id"]
                    drive_name = drive.get("name", "Unknown")
                    drives_searched += 1

                    params = {
                        "$top": limit,
                        "$select": "id,name,size,lastModifiedDateTime,webUrl,folder,file",
                    }
                    api_url = f"{GRAPH_API_BASE}/drives/{drive_id}/root/search(q='{encoded_query}')"
                    resp2 = await context.fetch(api_url, params=params)
                    drive_response = resp2.data

                    for item in drive_response.get("value", []):
                        file_item = {
                            "id": item["id"],
                            "name": item["name"],
                            "size": item.get("size", 0),
                            "lastModifiedDateTime": item["lastModifiedDateTime"],
                            "webUrl": item["webUrl"],
                            "drive_id": drive_id,
                            "drive_name": drive_name,
                        }
                        if "folder" in item:
                            file_item["folder"] = item["folder"]
                        if "file" in item:
                            file_item["file"] = item["file"]
                        all_files.append(file_item)

                        if len(all_files) >= limit:
                            break

                except Exception as drive_error:
                    search_errors.append(f"Drive '{drive.get('name', drive.get('id'))}': {str(drive_error)}")
                    continue

                if len(all_files) >= limit:
                    break

            if len(all_files) > limit:
                all_files = all_files[:limit]

            result = {
                "site_id": site_id,
                "query": search_query,
                "files": all_files,
                "total_files": len(all_files),
                "drives_searched": drives_searched,
                "total_drives": len(drives),
            }

            if search_errors:
                result["search_errors"] = search_errors

            return ActionResult(data=result, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("read_sharepoint_document")
class ReadSharePointDocumentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]
            file_id = inputs["file_id"]
            drive_id = inputs.get("drive_id")

            metadata_params = {"$select": "id,name,size,mimeType,file,webUrl"}

            if drive_id:
                metadata_url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file_id}"
            else:
                metadata_url = f"{GRAPH_API_BASE}/sites/{site_id}/drive/items/{file_id}"

            resp = await context.fetch(metadata_url, params=metadata_params)
            metadata_response = resp.data
            _check_response(metadata_response, "id", "name")

            file_name = metadata_response["name"]
            file_size = metadata_response.get("size", 0)
            mime_type = metadata_response.get("mimeType", "")
            web_url = metadata_response.get("webUrl", "")

            content = None
            content_type = "application/octet-stream"
            content_available = False
            content_info = ""

            try:
                _token = context.auth.get("credentials", {}).get("access_token", "")
                if any(ext in file_name.lower() for ext in [".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"]):
                    if drive_id:
                        content_url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file_id}/content?format=pdf"
                    else:
                        content_url = f"{GRAPH_API_BASE}/sites/{site_id}/drive/items/{file_id}/content?format=pdf"
                    content_bytes = await _fetch_binary(content_url, _token)
                    content = base64.b64encode(content_bytes).decode("utf-8")
                    content_type = "application/pdf"
                    content_available = True
                    content_info = "Office document converted to PDF and encoded for LLM processing"
                elif file_name.lower().endswith(".pdf"):
                    if drive_id:
                        content_url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file_id}/content"
                    else:
                        content_url = f"{GRAPH_API_BASE}/sites/{site_id}/drive/items/{file_id}/content"
                    content_bytes = await _fetch_binary(content_url, _token)
                    content = base64.b64encode(content_bytes).decode("utf-8")
                    content_type = "application/pdf"
                    content_available = True
                    content_info = "PDF content retrieved and encoded for LLM processing"
                else:
                    if drive_id:
                        content_url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{file_id}/content"
                    else:
                        content_url = f"{GRAPH_API_BASE}/sites/{site_id}/drive/items/{file_id}/content"
                    content_bytes = await _fetch_binary(content_url, _token)
                    content = base64.b64encode(content_bytes).decode("utf-8")
                    content_type = mime_type or "text/plain"
                    content_available = True
                    content_info = "Text content retrieved and encoded successfully"

            except Exception as content_error:
                content = None
                content_available = False
                content_info = f"Content retrieval failed: {str(content_error)}"

            if not mime_type:
                if file_name.lower().endswith(".pdf"):
                    mime_type = "application/pdf"
                elif any(ext in file_name.lower() for ext in [".docx", ".doc"]):
                    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif any(ext in file_name.lower() for ext in [".xlsx", ".xls"]):
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif any(ext in file_name.lower() for ext in [".pptx", ".ppt"]):
                    mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                else:
                    mime_type = "application/octet-stream"

            if content_available and content:
                return ActionResult(
                    data={
                        "file": {
                            "content": content,
                            "name": file_name,
                            "contentType": content_type,
                        },
                        "metadata": {
                            "id": file_id,
                            "name": file_name,
                            "size": file_size,
                            "mimeType": mime_type,
                            "webUrl": web_url,
                            "site_id": site_id,
                            "drive_id": drive_id or "",
                        },
                    },
                    cost_usd=0.0,
                )
            else:
                fallback_content_type = mime_type
                if file_name.lower().endswith(".pdf"):
                    fallback_content_type = "application/pdf"

                return ActionResult(
                    data={
                        "file": {
                            "content": "",
                            "name": file_name,
                            "contentType": fallback_content_type,
                        },
                        "metadata": {
                            "id": file_id,
                            "name": file_name,
                            "size": file_size,
                            "mimeType": mime_type,
                            "webUrl": web_url,
                            "site_id": site_id,
                            "drive_id": drive_id or "",
                        },
                        "content_error": content_info,
                    },
                    cost_usd=0.0,
                )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("list_sharepoint_pages")
class ListSharePointPagesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]

            params = {}

            if inputs.get("limit"):
                params["$top"] = inputs["limit"]
            if inputs.get("order_by"):
                params["$orderby"] = inputs["order_by"]
            if inputs.get("select_fields"):
                params["$select"] = inputs["select_fields"]
            else:
                params["$select"] = (
                    "id,name,webUrl,title,pageLayout,createdDateTime,lastModifiedDateTime,createdBy,lastModifiedBy"
                )

            resp = await context.fetch(
                f"{GRAPH_API_BASE}/sites/{site_id}/pages/microsoft.graph.sitePage",
                params=params,
            )
            response = resp.data

            pages = []
            for page in response.get("value", []):
                page_data = {
                    "id": page.get("id", ""),
                    "name": page.get("name", ""),
                    "title": page.get("title", ""),
                    "web_url": page.get("webUrl", ""),
                    "page_layout": page.get("pageLayout", ""),
                    "created_datetime": page.get("createdDateTime", ""),
                    "last_modified_datetime": page.get("lastModifiedDateTime", ""),
                }

                if "createdBy" in page and "user" in page["createdBy"]:
                    page_data["created_by"] = {
                        "display_name": page["createdBy"]["user"].get("displayName", ""),
                        "email": page["createdBy"]["user"].get("email", ""),
                    }

                if "lastModifiedBy" in page and "user" in page["lastModifiedBy"]:
                    page_data["last_modified_by"] = {
                        "display_name": page["lastModifiedBy"]["user"].get("displayName", ""),
                        "email": page["lastModifiedBy"]["user"].get("email", ""),
                    }

                pages.append(page_data)

            return ActionResult(
                data={
                    "site_id": site_id,
                    "pages": pages,
                    "total_pages": len(pages),
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("read_sharepoint_page_content")
class ReadSharePointPageContentAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]
            page_id = inputs["page_id"]
            include_content = inputs.get("include_content", True)

            params = {
                "$select": (
                    "id,name,webUrl,title,pageLayout,createdDateTime,lastModifiedDateTime,createdBy,lastModifiedBy"
                )
            }

            if include_content:
                params["$expand"] = "canvasLayout"

            resp = await context.fetch(
                f"{GRAPH_API_BASE}/sites/{site_id}/pages/{page_id}/microsoft.graph.sitePage",
                params=params,
            )
            response = resp.data

            page_data = {
                "id": response.get("id", ""),
                "name": response.get("name", ""),
                "title": response.get("title", ""),
                "web_url": response.get("webUrl", ""),
                "page_layout": response.get("pageLayout", ""),
                "created_datetime": response.get("createdDateTime", ""),
                "last_modified_datetime": response.get("lastModifiedDateTime", ""),
            }

            if "createdBy" in response and "user" in response["createdBy"]:
                page_data["created_by"] = {
                    "display_name": response["createdBy"]["user"].get("displayName", ""),
                    "email": response["createdBy"]["user"].get("email", ""),
                }

            if include_content and "canvasLayout" in response:
                page_data["content"] = response["canvasLayout"]

            return ActionResult(
                data={"site_id": site_id, "page": page_data},
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("list_sharepoint_subsites")
class ListSharePointSubsitesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            site_id = inputs["site_id"]

            limit = inputs.get("limit", 50)
            params = {"$top": limit}

            resp = await context.fetch(f"{GRAPH_API_BASE}/sites/{site_id}/sites", params=params)
            response = resp.data

            subsites = []
            for site in response.get("value", []):
                subsites.append(
                    {
                        "id": site.get("id", ""),
                        "name": site.get("name", ""),
                        "display_name": site.get("displayName", ""),
                        "description": site.get("description", ""),
                        "web_url": site.get("webUrl", ""),
                        "created_datetime": site.get("createdDateTime", ""),
                        "last_modified_datetime": site.get("lastModifiedDateTime", ""),
                        "is_personal_site": site.get("isPersonalSite", False),
                    }
                )

            return ActionResult(
                data={
                    "site_id": site_id,
                    "subsites": subsites,
                    "total_subsites": len(subsites),
                    "has_more": "@odata.nextLink" in response,
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("list_sharepoint_folder_contents")
class ListSharePointFolderContentsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            drive_id = inputs["drive_id"]
            folder_id = inputs.get("folder_id")
            limit = inputs.get("limit", 50)

            if folder_id:
                url = f"{GRAPH_API_BASE}/drives/{drive_id}/items/{folder_id}/children"
            else:
                url = f"{GRAPH_API_BASE}/drives/{drive_id}/root/children"

            params = {
                "$top": limit,
                "$select": (
                    "id,name,size,lastModifiedDateTime,webUrl,folder,file,createdDateTime,createdBy,lastModifiedBy"
                ),
            }

            resp = await context.fetch(url, params=params)
            response = resp.data

            items = []
            for item in response.get("value", []):
                item_data = {
                    "id": item.get("id", ""),
                    "name": item.get("name", ""),
                    "web_url": item.get("webUrl", ""),
                    "size": item.get("size", 0),
                    "created_datetime": item.get("createdDateTime", ""),
                    "last_modified_datetime": item.get("lastModifiedDateTime", ""),
                    "is_folder": "folder" in item,
                    "drive_id": drive_id,
                }

                if "folder" in item:
                    item_data["child_count"] = item["folder"].get("childCount", 0)

                if "file" in item:
                    item_data["mime_type"] = item["file"].get("mimeType", "")

                if "createdBy" in item and "user" in item.get("createdBy", {}):
                    item_data["created_by"] = item["createdBy"]["user"].get("displayName", "")

                if "lastModifiedBy" in item and "user" in item.get("lastModifiedBy", {}):
                    item_data["last_modified_by"] = item["lastModifiedBy"]["user"].get("displayName", "")

                items.append(item_data)

            return ActionResult(
                data={
                    "drive_id": drive_id,
                    "folder_id": folder_id or "root",
                    "items": items,
                    "total_items": len(items),
                    "has_more": "@odata.nextLink" in response,
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


# ---- Meeting Scheduling & Room Management Handlers ----


@microsoft365.action("find_meeting_times")
class FindMeetingTimesAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            attendees_emails = inputs["attendees"]
            duration_minutes = inputs.get("duration_minutes", 60)
            max_candidates = min(inputs.get("max_candidates", 10), 20)
            is_organizer_optional = inputs.get("is_organizer_optional", False)
            minimum_attendee_percentage = inputs.get("minimum_attendee_percentage", 100)

            attendees = []
            for email in attendees_emails:
                attendees.append({"type": "required", "emailAddress": {"address": email}})

            start_dt = inputs.get("start_datetime")
            end_dt = inputs.get("end_datetime")

            if not start_dt:
                start_parsed = datetime.now(timezone.utc)
                start_dt = start_parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                clean_dt = start_dt.replace("Z", "")
                if "." in clean_dt:
                    base, frac = clean_dt.split(".")
                    clean_dt = f"{base}.{frac[:6]}"
                start_parsed = datetime.fromisoformat(clean_dt)

            if not end_dt:
                end_parsed = start_parsed + timedelta(days=7)
                end_dt = end_parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                clean_dt = end_dt.replace("Z", "")
                if "." in clean_dt:
                    base, frac = clean_dt.split(".")
                    clean_dt = f"{base}.{frac[:6]}"
                datetime.fromisoformat(clean_dt)

            time_constraint = {
                "timeslots": [
                    {
                        "start": {
                            "dateTime": start_dt.replace("Z", ""),
                            "timeZone": "UTC",
                        },
                        "end": {"dateTime": end_dt.replace("Z", ""), "timeZone": "UTC"},
                    }
                ]
            }

            body = {
                "attendees": attendees,
                "meetingDuration": f"PT{duration_minutes}M",
                "maxCandidates": max_candidates,
                "isOrganizerOptional": is_organizer_optional,
                "minimumAttendeePercentage": minimum_attendee_percentage,
            }

            body["timeConstraint"] = time_constraint

            location_email = inputs.get("location_constraint")
            if location_email:
                body["locationConstraint"] = {
                    "isRequired": True,
                    "suggestLocation": False,
                    "locations": [
                        {
                            "resolveAvailability": True,
                            "locationEmailAddress": location_email,
                        }
                    ],
                }

            resp = await context.fetch(f"{GRAPH_API_BASE}/me/findMeetingTimes", method="POST", json=body)
            response = resp.data

            suggestions = []
            for suggestion in response.get("meetingTimeSuggestions", []):
                time_slot = suggestion.get("meetingTimeSlot", {})
                start_info = time_slot.get("start", {})
                end_info = time_slot.get("end", {})

                attendee_avail = []
                for att in suggestion.get("attendeeAvailability", []):
                    att_email = att.get("attendee", {}).get("emailAddress", {}).get("address", "")
                    attendee_avail.append(
                        {
                            "email": att_email,
                            "availability": att.get("availability", "unknown"),
                        }
                    )

                locations = []
                for loc in suggestion.get("locations", []):
                    locations.append(
                        {
                            "displayName": loc.get("displayName", ""),
                            "locationEmailAddress": loc.get("locationEmailAddress", ""),
                        }
                    )

                suggestions.append(
                    {
                        "start": start_info.get("dateTime", ""),
                        "end": end_info.get("dateTime", ""),
                        "confidence": suggestion.get("confidence", 0),
                        "organizer_availability": suggestion.get("organizerAvailability", "unknown"),
                        "attendee_availability": attendee_avail,
                        "suggested_locations": locations,
                    }
                )

            result_data: Dict[str, Any] = {"meeting_time_suggestions": suggestions}

            empty_reason = response.get("emptySuggestionsReason", "")
            if empty_reason:
                result_data["empty_suggestions_reason"] = empty_reason

            return ActionResult(data=result_data, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("get_schedule")
class GetScheduleAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            schedules_list = inputs["schedules"]
            start_dt = inputs["start_datetime"]
            end_dt = inputs["end_datetime"]
            interval = inputs.get("availability_view_interval", 30)

            body = {
                "schedules": schedules_list,
                "startTime": {"dateTime": start_dt.replace("Z", ""), "timeZone": "UTC"},
                "endTime": {"dateTime": end_dt.replace("Z", ""), "timeZone": "UTC"},
                "availabilityViewInterval": interval,
            }

            resp = await context.fetch(f"{GRAPH_API_BASE}/me/calendar/getSchedule", method="POST", json=body)
            response = resp.data

            schedules = []
            for schedule in response.get("value", []):
                schedule_data = {
                    "email": schedule.get("scheduleId", ""),
                    "availability_view": schedule.get("availabilityView", ""),
                }

                items = []
                for item in schedule.get("scheduleItems", []):
                    start_info = item.get("start", {})
                    end_info = item.get("end", {})
                    items.append(
                        {
                            "status": item.get("status", "unknown"),
                            "start": start_info.get("dateTime", ""),
                            "end": end_info.get("dateTime", ""),
                            "subject": item.get("subject", ""),
                            "location": item.get("location", ""),
                            "is_private": item.get("isPrivate", False),
                        }
                    )
                schedule_data["schedule_items"] = items

                working_hours = schedule.get("workingHours", {})
                if working_hours:
                    schedule_data["working_hours"] = {
                        "start_time": working_hours.get("startTime", ""),
                        "end_time": working_hours.get("endTime", ""),
                        "days_of_week": working_hours.get("daysOfWeek", []),
                        "timezone": working_hours.get("timeZone", {}).get("name", "")
                        if isinstance(working_hours.get("timeZone"), dict)
                        else working_hours.get("timeZone", ""),
                    }

                error_info = schedule.get("error", None)
                if error_info:
                    schedule_data["error"] = error_info.get("message", str(error_info))

                schedules.append(schedule_data)

            return ActionResult(data={"schedules": schedules}, cost_usd=0.0)

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("list_rooms")
class ListRoomsAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            list_type = inputs.get("list_type", "rooms")
            limit = inputs.get("limit", 100)

            if list_type == "room_lists":
                url = f"{GRAPH_API_BASE}/places/microsoft.graph.roomList"
                params = {"$top": limit}
                all_items = []
                next_url = url
                is_first = True
                while next_url and len(all_items) < limit:
                    resp = await context.fetch(next_url, params=params if is_first else None)
                    is_first = False
                    response = resp.data
                    all_items.extend(response.get("value", []))
                    next_url = response.get("@odata.nextLink")
                all_items = all_items[:limit]

                rooms = []
                for room_list in all_items:
                    rooms.append(
                        {
                            "id": room_list.get("id", ""),
                            "display_name": room_list.get("displayName", ""),
                            "email_address": room_list.get("emailAddress", ""),
                            "phone": room_list.get("phone", ""),
                        }
                    )

            elif list_type == "rooms_in_list":
                room_list_email = inputs.get("room_list_email")
                if not room_list_email:
                    return ActionError(message="room_list_email is required when list_type is 'rooms_in_list'")
                url = f"{GRAPH_API_BASE}/places/{room_list_email}/microsoft.graph.roomList/rooms"
                params = {"$top": limit}
                all_items = []
                next_url = url
                is_first = True
                while next_url and len(all_items) < limit:
                    resp = await context.fetch(next_url, params=params if is_first else None)
                    is_first = False
                    response = resp.data
                    all_items.extend(response.get("value", []))
                    next_url = response.get("@odata.nextLink")
                all_items = all_items[:limit]

                rooms = []
                for room in all_items:
                    rooms.append(
                        {
                            "id": room.get("id", ""),
                            "display_name": room.get("displayName", ""),
                            "email_address": room.get("emailAddress", ""),
                            "capacity": room.get("capacity", None),
                            "building": room.get("building", ""),
                            "floor_number": room.get("floorNumber", None),
                            "floor_label": room.get("floorLabel", ""),
                            "is_wheelchair_accessible": room.get("isWheelChairAccessible", None),
                            "audio_device_name": room.get("audioDeviceName", ""),
                            "video_device_name": room.get("videoDeviceName", ""),
                            "display_device_name": room.get("displayDeviceName", ""),
                            "phone": room.get("phone", ""),
                        }
                    )

            else:
                url = f"{GRAPH_API_BASE}/places/microsoft.graph.room"
                params = {"$top": limit}
                all_items = []
                next_url = url
                is_first = True
                while next_url and len(all_items) < limit:
                    resp = await context.fetch(next_url, params=params if is_first else None)
                    is_first = False
                    response = resp.data
                    all_items.extend(response.get("value", []))
                    next_url = response.get("@odata.nextLink")
                all_items = all_items[:limit]

                rooms = []
                for room in all_items:
                    rooms.append(
                        {
                            "id": room.get("id", ""),
                            "display_name": room.get("displayName", ""),
                            "email_address": room.get("emailAddress", ""),
                            "capacity": room.get("capacity", None),
                            "building": room.get("building", ""),
                            "floor_number": room.get("floorNumber", None),
                            "floor_label": room.get("floorLabel", ""),
                            "is_wheelchair_accessible": room.get("isWheelChairAccessible", None),
                            "audio_device_name": room.get("audioDeviceName", ""),
                            "video_device_name": room.get("videoDeviceName", ""),
                            "display_device_name": room.get("displayDeviceName", ""),
                            "phone": room.get("phone", ""),
                        }
                    )

            return ActionResult(
                data={"rooms": rooms, "total_count": len(rooms)},
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))


@microsoft365.action("check_room_availability")
class CheckRoomAvailabilityAction(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext) -> ActionResult:
        try:
            room_emails = inputs["room_emails"]
            start_dt = inputs["start_datetime"]
            end_dt = inputs["end_datetime"]

            body = {
                "schedules": room_emails,
                "startTime": {"dateTime": start_dt.replace("Z", ""), "timeZone": "UTC"},
                "endTime": {"dateTime": end_dt.replace("Z", ""), "timeZone": "UTC"},
                "availabilityViewInterval": 15,
            }

            resp = await context.fetch(f"{GRAPH_API_BASE}/me/calendar/getSchedule", method="POST", json=body)
            response = resp.data

            rooms = []
            available_rooms = []
            unavailable_rooms = []

            for schedule in response.get("value", []):
                email = schedule.get("scheduleId", "")
                schedule_items = schedule.get("scheduleItems", [])

                conflicts = []
                for item in schedule_items:
                    status = item.get("status", "")
                    if status in (
                        "busy",
                        "tentative",
                        "oof",
                        "workingElsewhere",
                        "unknown",
                    ):
                        start_info = item.get("start", {})
                        end_info = item.get("end", {})
                        conflicts.append(
                            {
                                "status": status,
                                "start": start_info.get("dateTime", ""),
                                "end": end_info.get("dateTime", ""),
                                "subject": item.get("subject", ""),
                            }
                        )

                is_available = len(conflicts) == 0

                room_data = {
                    "email": email,
                    "is_available": is_available,
                    "conflicts": conflicts,
                }

                error_info = schedule.get("error", None)
                if error_info:
                    room_data["error"] = error_info.get("message", str(error_info))
                    room_data["is_available"] = False

                rooms.append(room_data)

                if is_available and not error_info:
                    available_rooms.append(email)
                else:
                    unavailable_rooms.append(email)

            return ActionResult(
                data={
                    "rooms": rooms,
                    "available_rooms": available_rooms,
                    "unavailable_rooms": unavailable_rooms,
                },
                cost_usd=0.0,
            )

        except Exception as e:
            return ActionError(message=str(e))
